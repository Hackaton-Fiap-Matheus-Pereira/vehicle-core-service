#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORE_URL="${CORE_URL:-http://localhost:8000}"
SALES_URL="${SALES_URL:-http://localhost:8001}"

if [[ -z "${WEBHOOK_SECRET:-}" && -f "${ROOT_DIR}/.env" ]]; then
  WEBHOOK_SECRET="$(sed -n 's/^WEBHOOK_SECRET=//p' "${ROOT_DIR}/.env" | tail -n 1)"
fi

if [[ -z "${WEBHOOK_SECRET:-}" || "${WEBHOOK_SECRET}" == CHANGE_ME* ]]; then
  echo "Defina WEBHOOK_SECRET no ambiente ou em .env antes de executar." >&2
  exit 1
fi

for command_name in curl; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Dependência ausente: ${command_name}" >&2
    exit 1
  fi
done

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo "Python 3 é necessário para validar as respostas JSON." >&2
  exit 1
fi

wait_for_health() {
  local name="$1"
  local url="$2"
  for _ in $(seq 1 30); do
    if curl -fsS --max-time 3 "${url}/health/ready" >/dev/null; then
      echo "[ok] ${name} está pronto"
      return 0
    fi
    sleep 1
  done
  echo "[erro] ${name} não ficou pronto em 30 segundos" >&2
  return 1
}

json_value() {
  local key="$1"
  "${PYTHON_BIN}" -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "${key}"
}

assert_vehicle_in_list() {
  local vehicle_id="$1"
  "${PYTHON_BIN}" -c '
import json, sys
payload = json.load(sys.stdin)
items = payload.get("items", [])
vehicle_id = sys.argv[1]
if not any(item.get("id") == vehicle_id for item in items):
    raise SystemExit(f"veículo {vehicle_id} não encontrado na lista")
prices = [float(item["price"]) for item in items]
if prices != sorted(prices):
    raise SystemExit("a lista não está ordenada por preço crescente")
' "${vehicle_id}"
}

wait_for_vehicle_list() {
  local endpoint="$1"
  local vehicle_id="$2"
  local token="$3"
  local response
  for _ in $(seq 1 20); do
    response="$(curl -fsS --max-time 5 \
      -H "Authorization: Bearer ${token}" \
      "${endpoint}?limit=100&offset=0")"
    if printf '%s' "${response}" | assert_vehicle_in_list "${vehicle_id}" 2>/dev/null; then
      printf '%s' "${response}"
      return 0
    fi
    sleep 1
  done
  echo "Veículo ${vehicle_id} não apareceu em ${endpoint}" >&2
  return 1
}

assert_vehicle_absent() {
  local endpoint="$1"
  local vehicle_id="$2"
  local token="$3"
  local response
  response="$(curl -fsS --max-time 5 \
    -H "Authorization: Bearer ${token}" \
    "${endpoint}?limit=100&offset=0")"
  printf '%s' "${response}" | "${PYTHON_BIN}" -c '
import json, sys
payload = json.load(sys.stdin)
vehicle_id = sys.argv[1]
if any(item.get("id") == vehicle_id for item in payload.get("items", [])):
    raise SystemExit(f"veículo {vehicle_id} ainda aparece entre os disponíveis")
' "${vehicle_id}"
}

wait_for_health "Core" "${CORE_URL}"
wait_for_health "Sales" "${SALES_URL}"

RUN_ID="$("${PYTHON_BIN}" -c 'import uuid; print(uuid.uuid4().hex[:12])')"
EMAIL="demo-${RUN_ID}@example.com"
PASSWORD="DemoPass123!"

echo "[1/7] Registrando usuário de demonstração"
curl -fsS --max-time 10 \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\",\"full_name\":\"Usuário da Demonstração\"}" \
  "${CORE_URL}/api/v1/auth/register" >/dev/null

echo "[2/7] Autenticando sem exibir o JWT"
LOGIN_RESPONSE="$(curl -fsS --max-time 10 \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}" \
  "${CORE_URL}/api/v1/auth/login")"
TOKEN="$(printf '%s' "${LOGIN_RESPONSE}" | json_value access_token)"

echo "[3/7] Cadastrando veículo no Core"
VEHICLE_RESPONSE="$(curl -fsS --max-time 10 \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"brand":"Honda","model":"Civic Touring","year":2022,"color":"Prata","price":105900.00}' \
  "${CORE_URL}/api/v1/vehicles")"
VEHICLE_ID="$(printf '%s' "${VEHICLE_RESPONSE}" | json_value id)"
echo "[ok] veículo criado: ${VEHICLE_ID}"

echo "[4/7] Validando lista de disponíveis e ordenação por preço"
wait_for_vehicle_list "${SALES_URL}/api/v1/vehicles/available" "${VEHICLE_ID}" "${TOKEN}" >/dev/null
echo "[ok] veículo sincronizado no Sales"

echo "[5/7] Criando compra idempotente"
IDEMPOTENCY_KEY="$("${PYTHON_BIN}" -c 'import uuid; print(uuid.uuid4())')"
PURCHASE_DATE="$("${PYTHON_BIN}" -c 'from datetime import date; print(date.today().isoformat())')"
PURCHASE_RESPONSE="$(curl -fsS --max-time 10 \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Idempotency-Key: ${IDEMPOTENCY_KEY}" \
  -d "{\"vehicle_id\":\"${VEHICLE_ID}\",\"buyer_cpf\":\"52998224725\",\"purchase_date\":\"${PURCHASE_DATE}\"}" \
  "${SALES_URL}/api/v1/purchases")"
PAYMENT_CODE="$(printf '%s' "${PURCHASE_RESPONSE}" | json_value payment_code)"
echo "[ok] compra pendente; código de pagamento: ${PAYMENT_CODE}"

echo "[6/7] Confirmando pagamento pelo webhook externo do Core"
EVENT_ID="$("${PYTHON_BIN}" -c 'import uuid; print(uuid.uuid4())')"
OCCURRED_AT="$("${PYTHON_BIN}" -c 'from datetime import datetime,timezone; print(datetime.now(timezone.utc).isoformat().replace("+00:00","Z"))')"
curl -fsS --max-time 10 \
  -H 'Content-Type: application/json' \
  -H "X-Webhook-Secret: ${WEBHOOK_SECRET}" \
  -d "{\"event_id\":\"${EVENT_ID}\",\"payment_code\":\"${PAYMENT_CODE}\",\"status\":\"PAID\",\"occurred_at\":\"${OCCURRED_AT}\"}" \
  "${CORE_URL}/api/v1/payments/webhook" >/dev/null

echo "[7/7] Validando lista de vendidos e ordenação por preço"
wait_for_vehicle_list "${SALES_URL}/api/v1/vehicles/sold" "${VEHICLE_ID}" "${TOKEN}" >/dev/null
assert_vehicle_absent "${SALES_URL}/api/v1/vehicles/available" "${VEHICLE_ID}" "${TOKEN}"

echo "Fluxo ponta a ponta concluído com sucesso."
echo "Veículo: ${VEHICLE_ID}"
echo "Pagamento: ${PAYMENT_CODE}"


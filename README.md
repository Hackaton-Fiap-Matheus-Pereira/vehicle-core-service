# Vehicle Core Service

Serviço principal do Tech Challenge SOAT - Fase 4. Ele mantém o cadastro canônico dos
veículos, autentica usuários e recebe o webhook externo de pagamento. As operações de compra
e as listagens de veículos disponíveis ou vendidos pertencem exclusivamente ao serviço de
vendas, que mantém seu próprio banco.

## Responsabilidades

- Cadastro, consulta individual e edição dos dados canônicos do veículo.
- Autenticação JSON com JWT e senhas protegidas por Argon2id.
- Sincronização HTTP da projeção do veículo com o serviço de vendas.
- Registro explícito do estado da sincronização (`PENDING`, `SYNCED` ou `FAILED`) e retry
  autenticado.
- Recepção do webhook de pagamento, protegido por segredo, e encaminhamento ao serviço de
  vendas.
- Recepção, pelo canal interno, de mudanças de estado do veículo feitas pelo serviço de vendas.
- Health checks de liveness e readiness.

O core não expõe `GET /api/v1/vehicles` como coleção. As listagens ordenadas por preço são
responsabilidade do serviço de vendas, conforme a separação exigida no desafio.

## Tecnologias

Python 3.12, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2 assíncrono, `aiomysql`,
MySQL 8.4, Alembic, PyJWT, Argon2, HTTPX, Pytest, Ruff e Docker.

## Modelo canônico

O veículo contém `id`, `brand`, `model`, `year`, `color`, `price`, `status`, `sync_status`,
`source_version`, usuário criador e timestamps. Os estados de negócio são:

- `AVAILABLE`: disponível para compra.
- `RESERVED`: reservado enquanto o pagamento é processado.
- `SOLD`: venda concluída.

`source_version` começa em 1 e aumenta a cada alteração canônica. O serviço de vendas pode
descartar projeções antigas de forma determinística.

## Contratos HTTP

### API pública

| Método | Caminho | Proteção | Descrição |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/register` | Pública | Cria usuário a partir de JSON. |
| `POST` | `/api/v1/auth/login` | Pública | Retorna JWT bearer. |
| `POST` | `/api/v1/vehicles` | JWT | Cadastra veículo e tenta sincronizar a projeção. |
| `GET` | `/api/v1/vehicles/{id}` | JWT | Consulta canônica individual. |
| `PATCH` | `/api/v1/vehicles/{id}` | JWT | Edita marca, modelo, ano, cor e/ou preço. |
| `POST` | `/api/v1/vehicles/{id}/sync/retry` | JWT | Repete uma sincronização pendente/falha. |
| `POST` | `/api/v1/payments/webhook` | `X-Webhook-Secret` | Encaminha evento ao sales. |
| `GET` | `/health/live` | Pública | Verifica o processo. |
| `GET` | `/health/ready` | Pública | Verifica a conexão com o banco. |

O webhook aceita exatamente:

```json
{
  "event_id": "c1038244-a36e-4a86-af81-aad5c55b1d06",
  "payment_code": "PAY-123",
  "status": "PAID",
  "occurred_at": "2026-10-15T12:00:00Z"
}
```

`status` pode ser `PAID` ou `CANCELED`. `event_id` permite que o serviço de vendas faça o
processamento idempotente.

### Integração entre serviços

Todas as chamadas internas usam o header `X-Service-Token`.

Core para sales:

- `PUT /internal/v1/vehicles/{vehicle_id}` com
  `{brand, model, year, color, price, status, source_version}`.
- `POST /internal/v1/payments` com
  `{event_id, payment_code, status, occurred_at}`.

Sales para core:

- `PUT /internal/v1/vehicles/{vehicle_id}/status` com `{status}`.

O cadastro ou a edição permanecem gravados se o sales estiver indisponível; nesse caso o core
responde com `sync_status=FAILED`. O endpoint de retry retorna `503` enquanto o downstream
continuar indisponível. Erros seguem o envelope:

```json
{
  "error": {
    "code": "SALES_SERVICE_UNAVAILABLE",
    "message": "O serviço de vendas está indisponível"
  }
}
```

## Variáveis de ambiente

Copie `.env.example` para `.env` e substitua todos os segredos. Os valores de desenvolvimento
são recusados quando `APP_ENV` não é `development` nem `test`.

| Variável | Finalidade |
| --- | --- |
| `DATABASE_URL` | URL SQLAlchemy, normalmente `mysql+aiomysql://...`. |
| `JWT_SECRET` | Assinatura dos tokens JWT. |
| `JWT_ALGORITHM` | Algoritmo JWT; padrão `HS256`. |
| `JWT_EXPIRE_MINUTES` | Validade do access token. |
| `SALES_SERVICE_URL` | URL base do serviço de vendas. |
| `SALES_SERVICE_TIMEOUT_SECONDS` | Timeout das integrações HTTP. |
| `SERVICE_TOKEN` | Segredo compartilhado entre core e sales. |
| `WEBHOOK_SECRET` | Segredo compartilhado com o processador de pagamentos. |

## Execução local

Requisitos: Python 3.12 e MySQL 8.4 disponível.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

No PowerShell, ative o ambiente com `.venv\Scripts\Activate.ps1` e copie o arquivo com
`Copy-Item .env.example .env`. A documentação OpenAPI ficará em `http://localhost:8000/docs`.

Um MySQL isolado pode ser iniciado para desenvolvimento com:

```bash
docker run --name vehicle-core-mysql \
  -e MYSQL_DATABASE=vehicle_core \
  -e MYSQL_USER=vehicle_core \
  -e MYSQL_PASSWORD=vehicle_core \
  -e MYSQL_ROOT_PASSWORD=root-local-only \
  -p 3306:3306 -d mysql:8.4
```

Se executar a API fora de uma rede Docker, ajuste o host de `DATABASE_URL` para `localhost`.

## Testes e qualidade

Os testes usam SQLite assíncrono em memória, HTTPX com `ASGITransport` e doubles das
integrações externas. Assim, não dependem de MySQL ou do sales para executar.

```bash
ruff check .
pytest
```

O `pytest` falha se a cobertura total ficar abaixo de 80%.

## Docker

```bash
docker build -t vehicle-core-service:local .
docker run --rm --env-file .env -p 8000:8000 vehicle-core-service:local
```

A imagem executa como usuário não-root. O entrypoint aplica `alembic upgrade head` antes de
iniciar o Uvicorn; portanto o banco precisa estar acessível.

Para subir a plataforma completa, mantenha `vehicle-core-service` e `vehicle-sales-service`
como diretórios irmãos e execute neste repositório:

```bash
cp compose.env.example .env
# substitua os valores CHANGE_ME
docker compose up --build --wait
```

O Compose inicia duas APIs e duas instâncias MySQL 8.4 segregadas. Kind, Kubernetes e
Terraform estão no diretório `infra/` e são opcionais para o desenvolvimento local.

## CI/CD

O workflow `.github/workflows/ci-cd.yml` executa Ruff e os testes em Pull Requests e pushes na
`main`. Após um merge na `main`, ele:

1. constrói a imagem;
2. publica as tags do commit e `latest` no GitHub Container Registry;
3. executa `alembic upgrade head` em um Job temporário usando os mesmos ConfigMap e Secret do
   serviço;
4. atualiza o container `api` do `Deployment/vehicle-core-service` com `kubectl`;
5. aguarda o rollout.

Para habilitar o deploy, configure a variável de repositório `ENABLE_K8S_DEPLOY=true` e o
secret `KUBE_CONFIG_B64`, contendo o kubeconfig em Base64. `KUBE_NAMESPACE` é opcional e
assume `vehicle-core`. Sem essa variável, CI, testes e publicação no GHCR continuam funcionando
e apenas o job de deploy é ignorado.

Na distribuição completa, este repositório também recebe `docker-compose.yml`, `infra/`,

## Entrega acadêmica
Projeto desenvolvido para o Tech Challenge da Pós-Tech.
`docs/` e `scripts/`, que concentram Compose, Kind, Kubernetes, Terraform e o roteiro E2E.
O código de vendas continua em repositório separado, como exige o enunciado.

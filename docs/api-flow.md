# Fluxo de API

## Endpoints públicos

| Serviço | Método e rota | Finalidade |
|---|---|---|
| Core | `POST /api/v1/auth/register` | Criar usuário |
| Core | `POST /api/v1/auth/login` | Obter JWT |
| Core | `POST /api/v1/vehicles` | Cadastrar veículo |
| Core | `GET /api/v1/vehicles/{id}` | Consultar veículo |
| Core | `PATCH /api/v1/vehicles/{id}` | Editar veículo |
| Core | `POST /api/v1/payments/webhook` | Receber pagamento |
| Sales | `GET /api/v1/vehicles/available` | Listar disponíveis por preço |
| Sales | `GET /api/v1/vehicles/sold` | Listar vendidos por preço |
| Sales | `POST /api/v1/purchases` | Iniciar compra |
| Sales | `GET /api/v1/purchases/{payment_code}` | Consultar compra |

Cadastro e edição no Core usam `Authorization: Bearer <JWT>`. As vitrines e a compra no Sales
são públicas neste escopo acadêmico. O webhook externo usa `X-Webhook-Secret`, e o cabeçalho
`Idempotency-Key` é recomendado na compra.

## Contrato interno

Toda chamada interna usa `X-Service-Token`.

### Sincronizar veículo do Core para Sales

```http
PUT /internal/v1/vehicles/{vehicle_id}
```

```json
{
  "brand": "Honda",
  "model": "Civic",
  "year": 2022,
  "color": "Prata",
  "price": 105900.00,
  "status": "AVAILABLE",
  "source_version": 1
}
```

### Encaminhar pagamento do Core para Sales

```http
POST /internal/v1/payments
```

```json
{
  "event_id": "a7e0b7cb-7adf-4f6f-b60a-51e985ee52b0",
  "payment_code": "PAY-EXAMPLE",
  "status": "PAID",
  "occurred_at": "2026-10-15T12:00:00Z"
}
```

Os valores válidos de pagamento são `PAID` e `CANCELED`.

### Atualizar estado do Sales no Core

```http
PUT /internal/v1/vehicles/{vehicle_id}/status
```

```json
{
  "status": "SOLD"
}
```

Os estados do veículo são `AVAILABLE`, `RESERVED` e `SOLD`.

## Fluxo ponta a ponta

1. Registrar e autenticar o usuário no Core.
2. Cadastrar o veículo no Core.
3. Core persiste o cadastro e sincroniza uma projeção em Sales.
4. Consultar a lista disponível em Sales.
5. Criar a compra em Sales com CPF e data.
6. Sales reserva o veículo, gera `payment_code` e informa o Core.
7. Enviar o webhook assinado ao Core.
8. Core encaminha o evento para Sales.
9. Sales conclui ou cancela a compra e sincroniza o estado no Core.
10. Para pagamento aprovado, verificar o veículo na lista de vendidos.

## Idempotência e erros esperados

- repetir a mesma compra com a mesma `Idempotency-Key` deve retornar o mesmo resultado;
- repetir o mesmo `event_id` de pagamento não deve aplicar a transição duas vezes;
- tentar comprar veículo reservado ou vendido deve retornar conflito;
- token interno ou segredo de webhook inválido deve retornar acesso negado;
- falha temporária entre serviços deve produzir estado de sincronização recuperável, nunca acesso direto ao banco remoto.


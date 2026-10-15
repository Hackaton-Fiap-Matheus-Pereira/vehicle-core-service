# Arquitetura da solução

## Visão geral

```mermaid
flowchart LR
    Client[Cliente / Frontend]
    Payment[Processador de pagamento]

    subgraph CoreNS[Namespace vehicle-core]
        Core[Core API\nFastAPI :8000]
        CoreDB[(MySQL 8.4\nCore)]
        Core -->|SQLAlchemy assíncrono| CoreDB
    end

    subgraph SalesNS[Namespace vehicle-sales]
        Sales[Sales API\nFastAPI :8000]
        SalesDB[(MySQL 8.4\nSales)]
        Sales -->|SQLAlchemy assíncrono| SalesDB
    end

    Client -->|JWT: cadastro e edição| Core
    Client -->|JWT: listagens e compra| Sales
    Payment -->|X-Webhook-Secret| Core
    Core -->|HTTP + X-Service-Token| Sales
    Sales -->|HTTP + X-Service-Token| Core

    GHCR[(GitHub Container Registry)] --> Core
    GHCR --> Sales
```

## Responsabilidades

### Core

- registra e autentica usuários com JWT e Argon2;
- mantém o cadastro canônico do veículo;
- recebe o webhook externo de pagamento;
- publica alterações do veículo para Sales;
- recebe de Sales mudanças de estado do catálogo.

### Sales

- mantém uma projeção local dos veículos vendáveis;
- lista disponíveis e vendidos por preço crescente;
- reserva um veículo e cria o código de pagamento;
- processa eventos de pagamento idempotentes;
- informa ao Core a mudança para `RESERVED`, `AVAILABLE` ou `SOLD`.

## Segregação de dados

O Core e o Sales usam instâncias MySQL, credenciais, volumes e redes diferentes. A aplicação Core não recebe a URL do banco Sales, e vice-versa. A única integração permitida entre domínios é HTTP.

No Compose:

- `core-data` é privada e contém somente Core, sua migração e `core-db`;
- `sales-data` é privada e contém somente Sales, sua migração e `sales-db`;
- `integration` contém apenas as duas APIs.

No Kubernetes, os domínios ficam em namespaces diferentes. NetworkPolicies descrevem a mesma intenção, mas sua aplicação depende de um CNI com suporte à política de rede; o Kind padrão pode exigir Calico ou Cilium para efetivamente bloqueá-la.

## Consistência entre serviços

Não há transação distribuída. Cada alteração tem versão de origem, identificadores idempotentes e estados explícitos de sincronização. Chamadas HTTP usam timeout; falhas devem poder ser repetidas sem duplicar compra ou pagamento.

```mermaid
sequenceDiagram
    participant U as Usuário
    participant C as Core API
    participant CDB as Core MySQL
    participant S as Sales API
    participant SDB as Sales MySQL

    U->>C: POST /api/v1/vehicles
    C->>CDB: grava veículo e source_version
    C->>S: PUT /internal/v1/vehicles/{id}
    S->>SDB: upsert idempotente da projeção
    S-->>C: projeção sincronizada
    C-->>U: veículo criado

    U->>S: POST /api/v1/purchases
    S->>SDB: reserva e cria payment_code
    S->>C: PUT /internal/v1/vehicles/{id}/status
    C->>CDB: marca RESERVED
    S-->>U: compra pendente

    U->>C: POST /api/v1/payments/webhook
    C->>S: POST /internal/v1/payments
    S->>SDB: marca PAID e veículo SOLD
    S->>C: PUT /internal/v1/vehicles/{id}/status
    C->>CDB: marca SOLD
```

## Implantação

Há dois caminhos mutuamente exclusivos:

1. manifests em `infra/kubernetes`, aplicados na ordem numérica;
2. Terraform em `infra/terraform`, que cria os mesmos objetos.

As imagens são publicadas no GHCR. Em uma entrega real, cada rollout deve usar tag imutável ou digest do commit aprovado. Os Jobs Alembic executam antes dos Deployments; os Deployments sobrescrevem o entrypoint da imagem para evitar que cada réplica tente migrar o banco novamente.

## Observabilidade operacional

- `/health/live`: processo ativo, sem depender de serviços remotos;
- `/health/ready`: prontidão da instância e de seu próprio banco;
- logs enviados para stdout/stderr;
- request ID deve ser propagado entre APIs;
- CPF, senhas, JWT, tokens e segredos de webhook não devem aparecer nos logs.


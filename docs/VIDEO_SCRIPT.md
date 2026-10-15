# Roteiro sugerido para o vídeo de entrega

## 1. Contexto e arquitetura

- Mostre os dois repositórios e seus READMEs.
- Abra o diagrama de `docs/architecture.md`.
- Explique que existem duas APIs e duas instâncias MySQL independentes.
- Mostre que a integração é HTTP com `X-Service-Token`.

## 2. Qualidade e CI/CD

- Abra um Pull Request real em cada repositório.
- Mostre os checks de Ruff, Pytest, cobertura mínima de 80%, build e Terraform.
- Mostre a proteção da branch principal contra push direto.
- Faça ou mostre o merge e o workflow disparado por `push` na branch principal.
- Mostre as imagens no GHCR com a tag do commit.

## 3. Infraestrutura

- Mostre a criação do Kind e o contexto `kind-tech-challenge`.
- Mostre `terraform plan/apply` **ou** os manifests; não aplique os dois.
- Execute `kubectl get pods,deploy,sts,svc,pvc,hpa -A`.
- Mostre dois StatefulSets/PVCs e os Jobs Alembic concluídos.
- Mostre o SHA ou digest das imagens dos Deployments.
- Mostre os endpoints locais `8000` e `8001` saudáveis.

## 4. Teste ponta a ponta

- Execute `scripts/e2e-demo.ps1` ou `scripts/e2e-demo.sh`.
- Mostre cadastro e login sem revelar senha ou JWT.
- Cadastre um veículo.
- Liste veículos disponíveis em ordem crescente de preço.
- Efetue a compra com CPF e obtenha o código de pagamento.
- Envie o webhook `PAID` ao Core.
- Mostre o veículo na lista de vendidos e fora da lista disponível.
- Mostre logs correlacionados das duas APIs, ocultando dados sensíveis.

## 5. Testes e cobertura

- Execute os testes dos dois serviços.
- Mostre todos os testes passando.
- Mostre cobertura total igual ou superior a 80% em cada serviço.

## 6. Entrega

- Confirme que o PDF final contém links acessíveis para os dois repositórios e para o vídeo.
- Verifique o acesso aos links em uma janela anônima ou com uma conta sem privilégios.


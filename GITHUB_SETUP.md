# Publicação dos dois repositórios no GitHub

O trabalho pede dois repositórios. Use os diretórios `vehicle-core-service` e
`vehicle-sales-service` separadamente. Na distribuição final, o Core também recebe
`docker-compose.yml`, `infra/`, `docs/` e `scripts/`, que concentram a infraestrutura da solução.

## 1. Criar os repositórios

Crie no GitHub dois repositórios vazios, por exemplo:

- `vehicle-core-service`
- `vehicle-sales-service`

Não marque a opção de criar README, pois os arquivos já estão prontos.

## 2. Enviar cada diretório

Execute dentro de cada diretório, trocando `SEU_USUARIO`:

```bash
git init -b main
git add .
git commit -m "feat: entrega Tech Challenge Fase 4"
git remote add origin https://github.com/SEU_USUARIO/NOME_DO_REPOSITORIO.git
git push -u origin main
```

## 3. Configurar CI/CD

O GitHub Actions já usa `GITHUB_TOKEN` para publicar no GHCR. Para ativar também o deploy em
um cluster Kubernetes, crie:

- variável `ENABLE_K8S_DEPLOY` com valor `true`;
- secret `KUBE_CONFIG_B64` com o kubeconfig codificado em Base64;
- variável opcional `KUBE_NAMESPACE` (`vehicle-core` ou `vehicle-sales`).

Sem essas configurações, lint, testes, cobertura, build e publicação no GHCR funcionam; o job
de deploy fica marcado como ignorado.

## 4. Pull Requests

Em `Settings > Branches`, proteja a branch `main`, exija Pull Request e o job `Ruff e testes`.
Depois faça ao menos um PR real em cada repositório para gerar a evidência solicitada no PDF.

# Operação e implantação

## API e worker

A API FastAPI pode ser executada em Heroku ou outro PaaS que exponha um processo web. O
worker de relatórios deve ser executado separadamente em um ambiente que permita iniciar
containers Docker. A API não monta o socket Docker do host.

O worker usa a mesma fila transacional no PostgreSQL e deve receber uma credencial de banco
com permissões mínimas. Em uma implantação maior, substitua essa fila por um broker ou por
um serviço de execução autenticado; essa troca preserva o contrato do caso de uso.

Antes do processo web, execute `alembic upgrade head`. O deploy deve falhar se a migração não
puder ser aplicada. O endpoint `/readyz` valida a conexão do banco, a fila no PostgreSQL e o
heartbeat recente do worker; `/healthz` valida apenas que o processo HTTP está vivo. O endpoint
`/metrics` expõe métricas sem conteúdo de cliente e `/api/v1/operations/alerts` mostra alertas
operacionais para o administrador da organização.

## Sandbox

Construa a imagem com:

```bash
docker build -f backend/sandbox.Dockerfile -t report-manager-sandbox:local .
```

O executor usa rede `none`, filesystem raiz somente leitura, usuário não privilegiado,
limites de CPU/memória/PIDs e um workspace temporário. A imagem não recebe credenciais de
fonte nem chaves de LLM. `RestrictedPython` valida o código antes do isolamento operacional
do Docker.

## Segredos

Em produção, use `vault://...` com `VaultSecretManager` e injete apenas o token do Vault no
processo. Nunca grave API keys, senhas de banco ou certificados no PostgreSQL. O
`EnvSecretManager` é limitado a ambiente local/testes.

## Retenção

A retenção padrão é configurável no `.env` e está definida em três anos. A rotina do worker
remove conteúdo binário expirado e minimiza diagnósticos/payloads antigos, preservando metadados
de auditoria, versões de relatório e o histórico necessário para rastreabilidade. O contrato
`ArtifactStore` usa `ARTIFACT_STORAGE_BACKEND=postgres` no MVP; a futura troca por S3 deve
manter `storage_key`, checksum, expiração e o contrato de download.

Consulte [checklist-release.md](./checklist-release.md) antes de cada publicação.

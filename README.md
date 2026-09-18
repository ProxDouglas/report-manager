# Plataforma de Relatórios

Base inicial do MVP para criação, execução e versionamento de relatórios.

## Stack da fundação

- Backend: Python 3.12, FastAPI e Uvicorn.
- Frontend: React, Vite, TypeScript e Tailwind CSS.
- Desenvolvimento local: Docker Compose, PostgreSQL, API, worker auxiliar e frontend.
- Contratos e decisões: [Planejamento.md](./Planejamento.md) e [Tasks.md](./Tasks.md).

## Executar localmente com Docker

Este é o fluxo recomendado porque inicia PostgreSQL, API, worker e frontend com a mesma
configuração. A imagem do sandbox é construída separadamente; o worker do Compose não monta
o socket Docker do host. Para executar scripts Python no sandbox em desenvolvimento, use um
worker externo com runtime Docker, conforme `docs/operacao-deploy.md`.

Pré-requisitos: Docker com Docker Compose.

```bash
cp .env.example .env
```

Antes de iniciar, altere no `.env` pelo menos `SECRET_KEY` para um valor local forte. A
senha do operador será escolhida no comando de bootstrap abaixo. O PostgreSQL da plataforma é
publicado na porta `15432`, evitando conflito com outro PostgreSQL do host; dentro da
rede Docker ele continua disponível em `postgres:5432`.

Construa a imagem usada pelo executor de scripts analíticos:

```bash
docker build -f backend/sandbox.Dockerfile \
  -t report-manager-sandbox:local .
```

Essa imagem não é iniciada pelo Compose. O worker local processa fontes e relatórios que não
exigem script Python; execuções com `python_code` precisam de um worker externo autorizado a
usar Docker.

Inicie os serviços:

```bash
docker compose --env-file .env \
  -f infra/docker-compose.yml up --build -d
```

Verifique os serviços e os endpoints:

```bash
docker compose -f infra/docker-compose.yml ps
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

Para acompanhar os logs:

```bash
docker compose -f infra/docker-compose.yml logs -f api worker
```

Para parar a aplicação sem remover os dados do banco:

```bash
docker compose -f infra/docker-compose.yml down
```

Não use `down -v` durante o desenvolvimento, pois isso remove o volume do PostgreSQL.

Também é possível usar `make dev-up` depois de criar o `.env`.

## Executar sem Docker

Este modo é útil para desenvolver a API e o frontend, mas não executa o pipeline completo
de scripts analíticos: o worker usa Docker para o sandbox. Para execução de relatórios,
isolamento RestrictedPython + Docker e readiness completo, use o fluxo com Docker.

Pré-requisitos: Python 3.12, Node.js 22, PostgreSQL acessível e um banco exclusivo para
a plataforma. Não use o banco de outra aplicação, como `Painel_Homologacao`; crie um banco
e usuário próprios para evitar que as migrations alterem dados externos.

Instale as dependências:

```bash
make backend-install
make frontend-install
cp .env.example .env
```

Se o PostgreSQL estiver no host na porta `5432`, ajuste no `.env` a URL para o banco
exclusivo:

```env
DATABASE_URL=postgresql+psycopg://USUARIO:SENHA@localhost:5432/report_manager
CORS_ORIGINS=http://localhost:5173
```

Aplique as migrations:

```bash
make migrate
```

Em um terminal, inicie a API:

```bash
cd backend
../.venv/bin/uvicorn app.main:app --reload \
  --host 0.0.0.0 --port 8000
```

Em outro terminal, inicie o frontend:

```bash
cd frontend
npm run dev
```

O worker pode ser iniciado com:

```bash
cd backend
../.venv/bin/python -m worker.main
```

Entretanto, sem o daemon Docker disponível o worker não conseguirá executar o sandbox.

## Acessar o sistema

- Frontend: http://localhost:5173
- Swagger da API: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/api/v1/health
- Liveness: http://localhost:8000/healthz
- Readiness: http://localhost:8000/readyz

## Acessos locais

### PostgreSQL do Docker

Os valores de desenvolvimento do `.env.example` são:

```text
Host externo: localhost
Porta externa: 15432
Host interno: postgres
Porta interna: 5432
Banco: report_manager
Usuário: report_manager
Senha: report_manager
```

Esses valores são somente para desenvolvimento local. Não reutilize essa senha em produção.

### Usuário da aplicação

Não existe uma senha fixa de usuário da aplicação. O operador inicial deve ser criado uma
única vez pelo endpoint de bootstrap, escolhendo o e-mail e a senha:

```bash
curl -X POST http://localhost:8000/api/v1/auth/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email":"operator@example.com","display_name":"Operador","password":"EscolhaUmaSenhaForte#123"}'
```

Depois, use esse e-mail e essa senha no frontend. Se a API retornar `409`, o operador já
foi criado; nesse caso, use as credenciais definidas anteriormente. O endpoint de bootstrap
é bloqueado depois que o primeiro usuário existe ou quando `ALLOW_BOOTSTRAP=false`.

As variáveis `BOOTSTRAP_OPERATOR_EMAIL` e `BOOTSTRAP_OPERATOR_PASSWORD` no `.env.example`
servem como referência de configuração local, mas o usuário é criado pelo payload do
endpoint acima; elas não criam automaticamente uma conta.

## Executar verificações

```bash
make backend-install
make frontend-install
make test
make lint
make typecheck
make build
```

Os testes de componentes e fluxos do frontend rodam com `make test` (Vitest). Para o
smoke test em navegador real, deixe o Compose em execução e informe uma conta local:

```bash
E2E_EMAIL=operator@example.com E2E_PASSWORD='senha-local' \
  E2E_ORGANIZATION_LABEL='Minha organização' make frontend-e2e
```

O script valida login, seleção de organização, histórico de versões e a visualização de
relatórios prontos. Ele não publica dados nem usa credenciais de clientes.

Use `make migrate` para aplicar migrations fora do Compose e `make migrate-check` para verificar divergências. O worker busca execuções criadas no PostgreSQL e as processa sob demanda.

Para preparar a imagem de scripts Python, use `docker build -f backend/sandbox.Dockerfile -t report-manager-sandbox:local .`. O script recebe `data` e deve atribuir uma lista de objetos a `result`; o executor fornece os arquivos de entrada/saída. O worker não monta o socket do Docker no Compose; em produção, o executor deve ser um serviço/worker externo com runtime Docker. Veja [docs/operacao-deploy.md](./docs/operacao-deploy.md).

## Segredos

Não coloque API keys, senhas, certificados privados ou dados de cliente no repositório. O `.env.example` contém apenas exemplos. Em produção, use referências de um gerenciador de segredos, preferencialmente Vault, conforme `docs/decisoes-iniciais.md`.

## Qualidade e segurança

```bash
make lint
make typecheck
make test
make build
make security
```

O pipeline em `.github/workflows/ci.yml` valida backend, frontend, migrations, imagens,
nomes de arquivos sensíveis e dependências. O frontend de produção pode ser construído
com `frontend/Dockerfile.prod`; ele serve apenas os arquivos estáticos em uma porta não
privilegiada.

Para atualizar os tipos de contrato do frontend a partir da API FastAPI em execução:

```bash
cd frontend
OPENAPI_URL=http://localhost:8000/openapi.json npm run generate:api-types
```

O checklist de release está em [docs/checklist-release.md](./docs/checklist-release.md).

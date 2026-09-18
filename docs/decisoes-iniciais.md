# Decisões iniciais de desenvolvimento

## Resolvidas para a fundação

- Frontend: React sobre Vite, TypeScript e Tailwind CSS.
- Python: 3.12.x, com dependências pinadas no `backend/pyproject.toml` e nos requirements.
- Desenvolvimento local: Docker Compose com PostgreSQL, API FastAPI, worker auxiliar e frontend Vite.
- Limites iniciais: os valores estão no `.env.example` e são carregados por configuração tipada no backend.

## Ainda dependentes de decisão operacional

- Worker Docker em produção: a API pode ser publicada em um PaaS, mas o ambiente de produção precisa suportar a execução isolada de containers e comunicação autenticada com a API.
- Copilot: o adaptador depende do endpoint/API efetivamente contratado pelo cliente.
- SMTP: o `.env.example` possui valores de exemplo; o provedor e o remetente definitivos devem ser escolhidos por ambiente.

## Segredos locais

O Compose local não precisa de um Vault para iniciar a fundação. O backend aceita valores de desenvolvimento pelo `.env`, mas a produção deve fornecer referências como `vault://...` e usar um adaptador de gerenciador de segredos. Nenhuma API key de cliente deve ser colocada no repositório.

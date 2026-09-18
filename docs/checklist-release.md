# Checklist de release

## Antes da migração

- [ ] Confirmar a imagem e o tag que serão publicados.
- [ ] Configurar `DATABASE_URL` e executar `alembic upgrade head` em uma janela controlada.
- [ ] Executar `alembic check` e verificar o backup/restauração do PostgreSQL.
- [ ] Validar limites de upload, linhas, resultado, timeout, concorrência e retenção de três anos.

## Segredos e integrações

- [ ] Trocar `SECRET_KEY` e usar Vault (ou outro gerenciador aprovado) para `secret_ref`.
- [ ] Verificar referências das senhas de bancos, API keys de LLM, SMTP e webhook.
- [ ] Confirmar TLS dos bancos e que somente IPs públicos autorizados estão liberados no MVP.
- [ ] Confirmar remetente SMTP, domínio, destinatários autorizados e política de retry.

## Serviços

- [ ] Publicar a API no PaaS e validar `/healthz`.
- [ ] Iniciar o worker em um ambiente com Docker e a imagem `SANDBOX_IMAGE` disponível.
- [ ] Validar `/readyz`: banco, fila e heartbeat recente do worker.
- [ ] Conferir `/metrics` e o feed autenticado `/api/v1/operations/alerts`.
- [ ] Executar uma fonte sintética, publicar uma versão, executar, listar e baixar um artefato.
- [ ] Executar `make frontend-e2e` com uma conta de teste e registrar o resultado do navegador.

## Retorno

- [ ] Manter a imagem anterior disponível até o smoke test terminar.
- [ ] Se a aplicação falhar, interromper o novo worker, restaurar o processo web anterior e preservar o banco.
- [ ] Não fazer downgrade destrutivo de migration; aplicar apenas rollback compatível e aprovado.
- [ ] Registrar correlation ID, migration revision e decisão de retorno no incidente.

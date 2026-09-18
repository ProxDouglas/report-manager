# Tarefas de implementação — Plataforma de Relatórios

Documento de execução do MVP. As regras de negócio vêm de `Planejamento.md`. O arquivo de arquitetura anexado pelo usuário foi tratado como referência técnica; não substitui as decisões registradas no planejamento.

## Como usar este arquivo

- Marque uma tarefa como concluída somente quando os critérios de aceite estiverem atendidos e houver teste ou evidência verificável.
- `P0` bloqueia o MVP; `P1` é necessário para completar o MVP; `P2` é melhoria ou backlog.
- As dependências indicadas são lógicas, não significam que todas as tarefas anteriores precisem estar 100% concluídas para iniciar uma tarefa.
- Nenhuma tarefa deve colocar senha, API key, conteúdo sensível ou dado de cliente no repositório, log ou screenshot.

## Decisões atuais do MVP

- Backend em Python com FastAPI.
- Frontend com React sobre Vite, TypeScript e Tailwind CSS.
- PostgreSQL é o banco da plataforma e também armazena snapshots e artefatos binários (`bytea`) durante o MVP.
- Fontes iniciais: PostgreSQL, Oracle Database, Microsoft SQL Server, CSV, Excel (`.xls`/`.xlsx`) e JSON.
- Bancos de clientes: somente IP público no MVP, credenciais de leitura, timeout e TLS quando suportado.
- Execução sob demanda. A fila e os workers podem existir internamente, mas não haverá agendamento, recorrência ou processamento batch no MVP.
- Sandbox em duas camadas: validação com RestrictedPython e execução isolada com Docker.
- Os clientes fornecem as próprias API keys de LLM. A plataforma terá presets administráveis de provedor, modelo e nível de reasoning.
- Provedores previstos: OpenAI/ChatGPT, Anthropic/Claude, DeepSeek, Gemini e Copilot, por adaptadores independentes.
- Segredos em produção devem ser referenciados por `secret_ref`, preferencialmente no HashiCorp Vault. O `.env` é apenas configuração e bootstrap do ambiente.
- SMTP global por ambiente, com credencial protegida pelo gerenciador de segredos.
- Retenção padrão de três anos, configurável por `.env`.
- Autenticação própria, painel do operador para criar clientes e suspender licenças, usuário inicial com troca obrigatória de senha. Recuperação de senha, MFA, SSO e e-mail transacional ficam fora do MVP.
- Relatórios publicados são imutáveis. Alteração solicitada pelo cliente gera a próxima versão e as versões antigas continuam visualizáveis.
- A execução deve usar a versão publicada mais recente do relatório e registrar a versão exata da fonte usada.
- Compartilhamento público não faz parte do MVP. Downloads e destinos devem verificar autorização, organização, licença e validade do artefato.

## Status da implementação — 2026-09-18

O núcleo executável do MVP foi implementado em `backend/`, `frontend/` e `infra/`. A
implementação inclui autenticação por sessão, multi-organização, licenças, fontes de banco
e arquivos, catálogo sensível, versionamento de relatórios, grants, fila/worker, artefatos
em PostgreSQL, renderização, distribuição, BYOK, RestrictedPython + Docker, retenção e
pipeline de CI.

Evidências verificadas em 2026-09-18:

- backend: `28 passed, 4 skipped` em testes unitários/contratuais;
- frontend: `8 passed` em Vitest, lint, typecheck e build de produção;
- PostgreSQL local: migração limpa, `alembic check` e testes de integração executados;
- navegador: smoke E2E concluído com login, troca de organização, versionamento, execução,
  listagem, visualização e download de artefato;
- sandbox: validação RestrictedPython, execução Docker sem rede e testes de escape;
- qualidade: Ruff, ESLint, mypy, TypeScript e `git diff --check` sem erros.

Continuam deliberadamente abertos somente decisões ou melhorias que não podem ser concluídas
sem contrato/escopo adicional: o contrato real do Copilot (DEC-004), RLS nativo do PostgreSQL
caso seja exigido além do isolamento no service layer, ambientes externos reais de Oracle e
SQL Server para execução opcional dos testes, e o backlog pós-MVP da seção 15.

## Pendências estratégicas antes do desenvolvimento

- [x] DEC-001 [P0] Confirmar se o frontend será React sobre Vite. Decisão adotada: React + TypeScript + Tailwind.
- [x] DEC-002 [P0] Definir a versão mínima suportada do Python e a política de atualização das dependências. Decisão adotada: Python 3.12.x, com versões diretas pinadas e atualização deliberada.
- [x] DEC-003 [P0] Definir o ambiente de execução do worker Docker em produção quando a API estiver no Heroku ou em outro PaaS. Decisão adotada: API no PaaS e worker/sandbox em ambiente externo com runtime Docker e PostgreSQL compartilhado.
- [ ] DEC-004 [P1] Confirmar se o Copilot será integrado por um endpoint/API contratada pelo cliente ou por outro provedor compatível; criar o adaptador somente após identificar o contrato.
- [x] DEC-005 [P1] Definir limites iniciais de usuários, linhas, tamanho de upload, tempo e concorrência por organização. Valores iniciais registrados no `.env.example` e validados pelo backend.
- [x] DEC-006 [P1] Confirmar provedores de e-mail SMTP permitidos e política de remetente por ambiente. Decisão adotada: SMTP global por ambiente, configurado por `.env`, com senha via `SecretManager`.

## 1. Fundação do repositório e ambiente local

### 1.1 Estrutura inicial

- [x] T001 [P0] Criar a estrutura `backend/`, `frontend/`, `infra/`, `docs/` e `tests/` sem misturar código de domínio com arquivos de infraestrutura.
- [x] T002 [P0] Criar o projeto Python do backend com dependências mínimas: FastAPI, servidor ASGI, Pydantic, SQLAlchemy, driver PostgreSQL, Alembic e ferramenta de testes.
- [x] T003 [P0] Criar o projeto frontend com Vite, TypeScript, Tailwind CSS e React.
- [x] T004 [P0] Fixar versões das dependências em arquivos de lock adequados ao gerenciador escolhido.
- [x] T005 [P0] Configurar `.editorconfig`, formatação, lint e validação de tipos para backend e frontend.
- [x] T006 [P0] Configurar hooks ou pipeline de verificação para impedir commit de `.env`, chaves, certificados privados e arquivos de cliente.
- [x] T007 [P1] Criar `README.md` técnico com comandos de instalação, execução, testes, migração e variáveis obrigatórias.

### 1.2 Ambiente local

- [x] T008 [P0] Criar ambiente local com PostgreSQL e serviço auxiliar do worker usando Docker Compose.
- [x] T009 [P0] Criar `.env.example` sem valores secretos, incluindo banco, JWT/sessão, retenção, limites de execução, SMTP e Vault.
- [x] T010 [P0] Implementar carregamento e validação tipada das configurações do backend na inicialização.
- [x] T011 [P1] Criar comando único para subir API, worker, frontend e dependências locais.
- [x] T012 [P1] Documentar como executar um Vault de desenvolvimento ou um `EnvSecretManager` somente local.

## 2. Backend — base FastAPI

### 2.1 Arquitetura interna

- [x] T013 [P0] Criar módulos separados para `identity`, `licensing`, `sources`, `catalog`, `reports`, `executions`, `llm`, `distribution` e `audit`.
- [x] T014 [P0] Separar domínio, casos de uso, portas/interfaces, infraestrutura e endpoints HTTP.
- [x] T015 [P0] Definir o contexto de organização em toda requisição autenticada e impedir acesso direto de endpoints a tabelas de outra organização.
- [x] T016 [P0] Definir DTOs de entrada e saída com Pydantic, sem expor entidades ORM diretamente.
- [x] T017 [P0] Criar tratamento único de erros de domínio, validação, autenticação, autorização e falhas de conectores.
- [x] T018 [P1] Adicionar versionamento de API e prefixo `/api/v1`.
- [x] T019 [P1] Criar documentação OpenAPI com exemplos sem dados reais e descrição das permissões necessárias.

### 2.2 Banco e migrações

- [x] T020 [P0] Configurar pool de conexões PostgreSQL com limites, timeout e encerramento seguro.
- [x] T021 [P0] Implementar Alembic e criar a migration inicial com UUID, `timestamptz`, `jsonb`, enums e índices previstos em `Planejamento.md`.
- [x] T022 [P0] Criar tabelas de organização, usuário, membership, papel, licença, eventos de auditoria e isolamento por `organization_id`.
- [x] T023 [P0] Criar tabelas de fontes, versões de fontes, catálogo, campos, métricas e permissões de acesso.
- [x] T024 [P0] Criar tabelas de relatórios, versões, grants, execuções, tentativas, versões de fontes usadas e artefatos.
- [x] T025 [P0] Criar tabelas de configuração de LLM, presets de modelos, invocações, destinos e eventos outbox.
- [x] T026 [P0] Criar constraints para impedir duas versões publicadas concorrentes, referências entre organizações e artefatos disponíveis sem conteúdo.
- [x] T027 [P1] Criar índices para listagem por organização, relatório, versão, status, data de execução e expiração.
- [x] T028 [P1] Criar comando de migração para banco vazio e comando de verificação de schema no CI.

## 3. Identidade, autenticação, autorização e licença

### 3.1 Autenticação própria

- [x] T029 [P0] Implementar hash seguro de senha com algoritmo configurado e comparação resistente a timing attack.
- [x] T030 [P0] Implementar login, logout/invalidação de sessão ou refresh token, conforme decisão de sessão adotada.
- [x] T031 [P0] Implementar `must_change_password` para o usuário padrão criado junto com o cliente.
- [x] T032 [P0] Implementar alteração de senha autenticada e bloquear operações da aplicação enquanto a troca obrigatória não for feita, exceto logout e alteração de senha.
- [x] T033 [P0] Não implementar recuperação de senha, MFA, SSO ou disparo de e-mail transacional no MVP; retornar mensagem explícita de recurso indisponível.
- [x] T034 [P1] Aplicar política mínima de senha, expiração opcional configurável e limite de tentativas de login.
- [x] T035 [P1] Evitar que mensagens de login revelem se um usuário existe.

### 3.2 Organização, papéis e permissões

- [x] T036 [P0] Implementar contexto de organização selecionada e validar membership em todas as operações.
- [x] T037 [P0] Implementar papéis iniciais: operador da plataforma, administrador da organização, criador de relatórios e visualizador.
- [x] T038 [P0] Implementar matriz de permissões para fontes, catálogo, relatórios, execuções, exportações, LLM, destinos e auditoria.
- [x] T039 [P0] Impedir que um usuário conceda a outro acesso maior que o próprio acesso.
- [x] T040 [P0] Adicionar testes de isolamento tentando consultar, alterar, baixar e executar recursos de outra organização.

### 3.3 Licenças e painel do operador

- [x] T041 [P0] Implementar criação de organização pelo operador da plataforma.
- [x] T042 [P0] Criar licença associada à organização com estados ativa, suspensa, expirada e cancelada.
- [x] T043 [P0] Criar o usuário administrador padrão ao criar uma organização e exigir troca da senha inicial.
- [x] T044 [P0] Bloquear criação de fontes, publicação, execução, exportação e distribuição quando a licença não estiver ativa.
- [x] T045 [P0] Implementar suspensão e reativação de licença com auditoria obrigatória.
- [x] T046 [P1] Criar endpoint de consulta do estado da licença para o frontend sem expor dados internos do operador.

## 4. Segredos, dados sensíveis e auditoria

- [x] T047 [P0] Definir a interface `SecretManager` com operações mínimas de obter, criar/atualizar, remover e verificar referência.
- [x] T048 [P0] Implementar `EnvSecretManager` somente para desenvolvimento local e testes.
- [x] T049 [P1] Implementar adaptador `VaultSecretManager` sem persistir valores secretos no PostgreSQL.
- [x] T050 [P1] Manter no banco apenas `secret_ref`, metadados não sensíveis e, quando necessário, hash/fingerprint não reversível.
- [x] T051 [P0] Implementar a política de classificação de dados definida em `backend/SKILLS-SERVICE/skill-dados-sensiveis.md`.
- [x] T052 [P0] Detectar e mascarar CPF, CNPJ, senhas, tokens, API keys, strings de conexão e outros padrões definidos pela skill antes de logs, prompts e mensagens de erro.
- [x] T053 [P0] Permitir classificar campo como público, interno, confidencial ou restrito no catálogo.
- [x] T054 [P0] Bloquear envio de dados restritos ao LLM por padrão; exigir configuração explícita e autorização aplicável.
- [x] T055 [P0] Registrar auditoria para login, troca de senha, criação/suspensão de licença, leitura de fonte, alteração/publicação de relatório, execução, download e distribuição.
- [x] T056 [P1] Garantir que auditoria não grave segredo, senha, conteúdo bruto ou payload completo de cliente.
- [x] T057 [P1] Criar testes automatizados para mascaramento, bloqueio de prompt e persistência da trilha de auditoria.

## 5. Fontes de dados e conectores

### 5.1 Contrato comum

- [x] T058 [P0] Definir a interface `SourceConnector` para testar conexão, observar schema, coletar dados autorizados e informar capacidades.
- [x] T059 [P0] Definir limite comum de timeout, linhas, bytes, colunas, profundidade e tempo de leitura.
- [x] T060 [P0] Implementar execução sempre em modo somente leitura no MVP; rejeitar comandos de escrita, DDL, DML e múltiplas instruções não autorizadas.
- [x] T061 [P0] Validar licença, membership, grant da fonte e status da versão antes de qualquer conexão externa.
- [x] T062 [P0] Registrar versão da fonte, instante da coleta, checksum quando aplicável, schema observado e conector usado.
- [x] T063 [P1] Padronizar erros de conexão, autenticação, timeout, schema inválido, limite excedido e acesso negado.

### 5.2 Bancos relacionais

- [x] T064 [P0] Implementar conector PostgreSQL com usuário de leitura, parâmetros seguros e consulta de catálogo.
- [x] T065 [P0] Implementar conector Oracle Database com parâmetros seguros e consulta de catálogo compatível.
- [x] T066 [P0] Implementar conector Microsoft SQL Server com parâmetros seguros e consulta de catálogo compatível.
- [x] T067 [P0] Permitir somente endereços/IPs públicos autorizados no MVP e documentar que VPN, túnel, agente e rede privada ficam no backlog.
- [x] T068 [P0] Ativar TLS quando suportado e tornar validação de certificado uma configuração explícita, sem desabilitação silenciosa.
- [x] T069 [P0] Criar teste de conexão sem retornar dados de negócio na resposta.
- [x] T070 [P0] Validar que consultas de relatório são somente leitura, possuem limite e não permitem interpolação insegura de identificadores ou valores.
- [x] T071 [P1] Implementar allowlist de schemas/tabelas/colunas selecionados pelo administrador da organização.

### 5.3 Arquivos CSV e Excel

- [x] T072 [P0] Criar upload controlado de CSV com limite de tamanho, encoding, delimitador, cabeçalho e formato de data configuráveis.
- [x] T073 [P0] Criar upload controlado de Excel `.xls` e `.xlsx` com seleção de planilha e linha de cabeçalho.
- [x] T074 [P0] Validar extensão, MIME, assinatura do arquivo, tamanho e conteúdo antes de processar.
- [x] T075 [P0] Impedir path traversal, nomes de arquivo não sanitizados e carregamento ilimitado em memória.
- [x] T076 [P0] Gerar snapshot da fonte e entrada de catálogo para colunas, tipos inferidos, quantidade de linhas e checksum.
- [x] T077 [P1] Definir comportamento para colunas inconsistentes, células vazias, fórmulas, datas inválidas e planilhas protegidas.

### 5.4 JSON

- [x] T078 [P0] Implementar upload e validação de JSON com limite de tamanho e profundidade.
- [x] T079 [P0] Implementar `root_path`, raiz array/objeto, achatamento por notação de ponto e política de arrays aninhados.
- [x] T080 [P0] Implementar as estratégias de conflito de tipo e campos ausentes previstas no planejamento.
- [x] T081 [P0] Rejeitar JSON inválido, raiz incompatível, profundidade excedida e estrutura que ultrapasse os limites do ambiente.
- [x] T082 [P0] Armazenar arquivo original e snapshot validado no PostgreSQL, associados à versão da fonte.
- [x] T083 [P1] Criar testes com objetos aninhados, arrays internos, campos ausentes, conflitos de tipo e arquivo malformado.

### 5.5 Versões, catálogo e dados sensíveis

- [x] T084 [P0] Criar nova versão para cada upload ou mudança relevante de configuração da fonte.
- [x] T085 [P0] Marcar uma única versão como mais recente válida por fonte, preservando versões anteriores para auditoria e execuções históricas.
- [x] T086 [P0] Implementar catálogo de objetos, campos, tipos, descrições e métricas selecionáveis.
- [x] T087 [P0] Permitir confirmação/ajuste manual da classificação sensível detectada automaticamente.
- [x] T088 [P1] Exibir diferenças de schema entre versões da fonte sem apagar o histórico.
- [x] T089 [P1] Criar endpoint para listar apenas as fontes e versões que o usuário pode usar.

## 6. Relatórios, versionamento e permissões

- [x] T090 [P0] Criar comando de criação de relatório manual com nome, objetivo, fontes, campos, métricas, filtros, parâmetros e formatos.
- [x] T091 [P0] Criar `ReportVersion` imutável após publicação.
- [x] T092 [P0] Ao alterar um relatório publicado, criar sempre a próxima versão em estado rascunho; nunca sobrescrever a versão publicada.
- [x] T093 [P0] Permitir somente uma versão publicada/ativa por relatório e indicar qual é a versão mais recente publicada.
- [x] T094 [P0] Fazer execução sempre resolver a versão publicada mais recente no instante de criação da execução.
- [x] T095 [P0] Registrar na execução a versão resolvida, para que o resultado histórico não mude quando uma versão nova for publicada.
- [x] T096 [P0] Manter visualização de todas as versões e execuções antigas permitidas ao usuário.
- [x] T097 [P0] Implementar grants de relatório por usuário, papel ou organização, sem compartilhamento público.
- [x] T098 [P1] Validar que campos, fontes e métricas da versão continuam autorizados e disponíveis antes da publicação.
- [x] T099 [P1] Exibir diff entre duas versões de relatório, incluindo definição, fontes, filtros e formato.
- [x] T100 [P1] Criar endpoint para duplicar uma versão como novo rascunho sem perder a origem histórica.

## 7. Geração assistida por IA e presets de modelos

### 7.1 Configuração BYOK

- [x] T101 [P0] Criar entidade/configuração de LLM por organização com `provider`, `model_preset_id`, reasoning, limites e `secret_ref`.
- [x] T102 [P0] Criar interface `LlmProviderAdapter` e um adaptador separado para cada provedor efetivamente contratado.
- [x] T103 [P0] Validar API key por chamada de teste sem expor a chave no frontend, log ou resposta.
- [x] T104 [P0] Permitir selecionar somente presets ativos e compatíveis com o provedor configurado.
- [x] T105 [P0] Persistir snapshot da capacidade do modelo na configuração e na invocação da IA.
- [x] T106 [P1] Tratar rate limit, timeout, indisponibilidade, resposta inválida e erro de autenticação com mensagens normalizadas.
- [x] T107 [P1] Não implementar fallback automático para outro modelo/provedor no MVP.

### 7.2 Catálogo de presets

- [x] T108 [P0] Criar CRUD restrito ao operador para presets com provedor, identificador, nome, reasoning, capacidades, limites e status.
- [x] T109 [P0] Impedir novas configurações com preset inativo, preservando as configurações e execuções históricas.
- [x] T110 [P0] Implementar data de última validação e ação de testar novamente a capacidade do preset.
- [x] T111 [P1] Permitir atualizar o catálogo sem novo deploy do frontend/backend.
- [x] T112 [P1] Exibir no frontend apenas níveis de reasoning suportados pelo preset escolhido.

### 7.3 Solicitação em linguagem natural

- [x] T113 [P0] Criar caso de uso que recebe a solicitação, contexto autorizado do catálogo e configuração de LLM.
- [x] T114 [P0] Enviar ao modelo somente metadados, instruções e dados mínimos necessários; aplicar classificação e mascaramento antes do prompt.
- [x] T115 [P0] Validar a resposta da IA contra um schema estruturado de definição de relatório.
- [x] T116 [P0] Exigir confirmação do usuário antes de salvar/publicar ou executar a definição proposta pela IA.
- [x] T117 [P1] Registrar prompt técnico reduzido, modelo, reasoning, versão de capacidade, custo/metadados e resultado da invocação sem dados sensíveis.

## 8. Pipeline de execução e sandbox

### 8.1 Orquestração

- [x] T118 [P0] Criar caso de uso de execução sob demanda que valida licença, permissão, versão publicada e parâmetros.
- [x] T119 [P0] Usar fila interna e worker para não bloquear a requisição HTTP, mantendo o escopo do MVP sem batch, recorrência ou agendamento.
- [x] T120 [P0] Registrar estados `CRIADA`, `EM_EXECUCAO`, `SUCESSO`, `FALHA`, `CANCELADA` e `EXPIRADA` conforme o modelo de domínio.
- [x] T121 [P0] Criar tentativa idempotente por execução e limitar retentativas conforme configuração.
- [x] T122 [P0] Associar cada execução às versões exatas das fontes coletadas e à versão do relatório utilizada.
- [x] T123 [P0] Aplicar limites de tempo, CPU, memória, linhas, bytes, rede e tamanho de resultado.
- [x] T124 [P1] Implementar cancelamento cooperativo e limpeza de recursos após timeout/falha.

### 8.2 RestrictedPython + Docker

- [x] T125 [P0] Implementar `PythonPolicyValidator` para validar o código/expressão gerado antes da execução.
- [x] T126 [P0] Bloquear imports, builtins, filesystem, subprocessos, rede e APIs não permitidas pela política.
- [x] T127 [P0] Implementar `SandboxExecutor` com executor Docker externo à API.
- [x] T128 [P0] Executar imagem mínima, não privilegiada, sem acesso ao socket Docker do host e sem filesystem do host montado.
- [x] T129 [P0] Configurar rede desabilitada por padrão (`SANDBOX_NETWORK_MODE=none`).
- [x] T130 [P0] Passar ao sandbox somente snapshot/contrato de dados autorizado, nunca credenciais de fonte ou API keys.
- [x] T131 [P0] Limpar container, arquivos temporários e variáveis sensíveis após cada tentativa.
- [x] T132 [P0] Testar escape de sandbox, acesso à rede, leitura do host, uso de subprocesso, exfiltração e consumo excessivo.
- [x] T133 [P1] Documentar que RestrictedPython é validação de política e Docker é a barreira de isolamento operacional.

### 8.3 Resultados e artefatos

- [x] T134 [P0] Implementar `PostgresArtifactStore` usando `bytea` para snapshots e arquivos gerados no MVP.
- [x] T135 [P0] Criar referência lógica `storage_key` mesmo quando o conteúdo estiver no PostgreSQL, preparando migração futura para S3/object storage.
- [x] T136 [P0] Persistir checksum, content type, tamanho, criação, expiração e associação com execução/versão.
- [x] T137 [P0] Fazer o resultado de uma execução bem-sucedida aparecer na lista de relatórios prontos.
- [x] T138 [P0] Não listar execução em andamento ou com resultado inválido como relatório pronto.
- [x] T139 [P0] Implementar download autorizado e temporário para CSV, XLSX e PDF; nunca retornar a chave física de armazenamento futuro.
- [x] T140 [P1] Implementar limpeza transacional de artefatos expirados e registrar a operação na auditoria.

## 9. Exportação e distribuição

- [x] T141 [P0] Criar renderer de tabela para visualização em tela.
- [x] T142 [P0] Implementar exportação CSV com encoding e separador documentados.
- [x] T143 [P0] Implementar exportação XLSX com tipos de célula e nomes de colunas preservados.
- [x] T144 [P0] Implementar exportação PDF com template, paginação e identificação da versão do relatório.
- [x] T145 [P0] Criar cadastro de destinos de e-mail e webhook por organização, com permissões e validação.
- [x] T146 [P0] Configurar SMTP global por `.env` e obter a senha apenas pelo `SecretManager`.
- [x] T147 [P0] Enviar e-mail apenas para destinatários autorizados, com referência/arquivo permitido e auditoria do envio.
- [x] T148 [P0] Implementar webhook com URL, método, timeout, tentativas limitadas e assinatura de requisição.
- [x] T149 [P1] Evitar incluir dados restritos no assunto, headers, logs ou payload do webhook.
- [x] T150 [P1] Manter compartilhamento público, links permanentes e SMTP por organização fora do MVP.

## 10. Frontend — Vite, TypeScript e Tailwind

### 10.1 Fundação da aplicação

- [x] T151 [P0] Criar shell da aplicação com layout autenticado, navegação por organização e tratamento de sessão expirada.
- [x] T152 [P0] Configurar TypeScript em modo estrito, ESLint, formatter e aliases de importação.
- [x] T153 [P0] Configurar Tailwind com tokens de cor, espaçamento, tipografia, estados de erro/sucesso e componentes acessíveis.
- [x] T154 [P0] Criar cliente HTTP tipado com tratamento único de erros, loading, retry seguro e cancelamento.
- [x] T155 [P0] Gerar ou manter tipos TypeScript alinhados ao contrato OpenAPI sem duplicar modelos manualmente.
- [x] T156 [P1] Implementar gerenciamento de cache/estado de servidor com hook reutilizável próprio no MVP, incluindo TTL, loading, cancelamento e invalidação.
- [x] T157 [P1] Criar componentes reutilizáveis para tabela, paginação, filtros, modal, formulário, alerta, badge de status e confirmação.
- [x] T158 [P1] Garantir navegação por teclado, labels, foco visível, contraste e mensagens de validação acessíveis.

### 10.2 Autenticação e administração

- [x] T159 [P0] Criar tela de login e estados de erro sem revelar se usuário existe.
- [x] T160 [P0] Criar tela de troca obrigatória de senha.
- [x] T161 [P0] Criar painel do operador para listar/criar organizações, visualizar licença e suspender/reativar cliente.
- [x] T162 [P0] Criar fluxo de criação de cliente com usuário administrador padrão e aviso de troca de senha.
- [x] T163 [P0] Criar telas da organização para usuários, memberships, papéis e permissões.
- [x] T164 [P1] Ocultar ações e rotas conforme permissão sem tratar a interface como única barreira de segurança.

### 10.3 Fontes e catálogo

- [x] T165 [P0] Criar listagem de fontes com tipo, status, última versão válida, última validação e proprietário.
- [x] T166 [P0] Criar formulário de fonte PostgreSQL, Oracle e SQL Server com campos de conexão e aviso de leitura/IP público.
- [x] T167 [P0] Criar upload e configuração de CSV, Excel e JSON, incluindo preview controlado.
- [x] T168 [P0] Criar ação de testar conexão/upload sem exibir credenciais ou conteúdo excessivo.
- [x] T169 [P0] Criar tela de versões da fonte e catálogo de objetos/campos.
- [x] T170 [P0] Criar tela para revisar classificação sensível e seleção de objetos/campos permitidos.
- [x] T171 [P1] Exibir diferenças de schema entre versões com mensagens claras de impacto.

### 10.4 Relatórios e versionamento

- [x] T172 [P0] Criar listagem de relatórios com versão publicada mais recente, status, última execução e arquivos disponíveis.
- [x] T173 [P0] Criar editor manual de definição de relatório com fontes, campos, métricas, filtros e formatos.
- [x] T174 [P0] Criar fluxo de solicitação em linguagem natural com preview da proposta da IA.
- [x] T175 [P0] Exigir confirmação explícita antes de salvar/publicar/solicitar execução da proposta.
- [x] T176 [P0] Criar tela de histórico de versões com comparação e acesso às versões antigas.
- [x] T177 [P0] Criar ação de editar que gera próxima versão, mantendo a versão anterior somente leitura.
- [x] T178 [P0] Criar publicação de versão com validações de campos, fontes, permissões e licença.
- [x] T179 [P1] Criar tela de grants do relatório por usuário/papel e deixar compartilhamento público indisponível.

### 10.5 Execuções, relatórios prontos e distribuição

- [x] T180 [P0] Criar ação de executar relatório sob demanda com confirmação e parâmetros.
- [x] T181 [P0] Criar acompanhamento de execução com estados, tentativa, erro resumido e atualização sem bloquear a tela.
- [x] T182 [P0] Criar tela/listagem de relatórios prontos, mostrando versão utilizada, data, status e artefatos.
- [x] T183 [P0] Criar visualização em tela com paginação/limite e indicação da fonte/versão usada.
- [x] T184 [P0] Criar ações de baixar CSV, XLSX e PDF com autorização do backend.
- [x] T185 [P0] Criar configuração de destinatários SMTP e webhook sem permitir alteração da credencial global.
- [x] T186 [P1] Mostrar aviso quando o artefato estiver expirado ou quando a licença não permitir exportação.

### 10.6 LLM e configurações operacionais

- [x] T187 [P0] Criar tela de configuração BYOK por organização com segredo mascarado.
- [x] T188 [P0] Criar tela do operador para gerenciar presets, capacidades, reasoning e status ativo.
- [x] T189 [P0] Filtrar dinamicamente os níveis de reasoning compatíveis com o preset selecionado.
- [x] T190 [P1] Exibir data de validação, aviso de preset desativado e impacto sobre novas configurações.
- [x] T191 [P1] Criar tela de auditoria com filtros por usuário, ação, recurso, status e período permitido.

## 11. Observabilidade, testes e qualidade

### 11.1 Testes backend

- [x] T192 [P0] Criar testes unitários para entidades, regras de versão, licença, permissões, classificação e limites.
- [x] T193 [P0] Criar testes de integração com PostgreSQL para migrations, constraints, isolamento no service layer e transações; RLS nativo fica fora do MVP até definir o papel/GUC da conexão.
- [x] T194 [P0] Criar testes de contrato para endpoints FastAPI e schemas OpenAPI.
- [x] T195 [P0] Criar testes de conectores com bancos reais de teste ou containers compatíveis; nunca usar banco de cliente.
- [x] T196 [P0] Criar testes de pipeline com execução válida, falha, timeout, cancelamento, retry e idempotência.
- [x] T197 [P0] Criar testes de segurança do sandbox e dos downloads.
- [x] T198 [P1] Criar testes de propriedades para parser de CSV, Excel e JSON dentro dos limites configurados.

### 11.2 Testes frontend e ponta a ponta

- [x] T199 [P0] Criar testes de componentes para formulários, permissões, tabelas, estados de erro e download.
- [x] T200 [P0] Criar testes de fluxo para login, troca de senha e seleção de organização.
- [x] T201 [P0] Criar testes de fluxo para criar fonte, validar, consultar catálogo e revisar dados sensíveis.
- [x] T202 [P0] Criar testes de fluxo para criar relatório, publicar versão, editar gerando próxima versão e visualizar versões antigas.
- [x] T203 [P0] Criar teste ponta a ponta de execução, listagem de relatório pronto e download de artefato.
- [x] T204 [P1] Criar teste de tentativa de acesso cross-tenant pelo frontend e confirmar bloqueio no backend.

### 11.3 Logs, métricas e diagnóstico

- [x] T205 [P0] Implementar logs estruturados com correlation ID, organization ID não sensível, usuário técnico e execution ID.
- [x] T206 [P0] Redigir segredos, CPF, CNPJ, tokens, SQL com valores e conteúdo de arquivo dos logs.
- [x] T207 [P1] Expor health check da API e readiness check do banco, fila e worker.
- [x] T208 [P1] Criar métricas de duração, sucesso/falha, filas, retries, tamanho de artefato, uso de banco e retenção.
- [x] T209 [P1] Criar alertas para falha de worker, crescimento de `bytea`, filas paradas, expiração de licença e erro de SMTP.

## 12. Retenção e operação

- [x] T210 [P0] Implementar retenção padrão de três anos para versões, snapshots, artefatos, logs de execução e auditoria conforme `.env`.
- [x] T211 [P0] Calcular expiração por data, sem alterar artefatos de uma execução ainda em andamento.
- [x] T212 [P0] Criar rotina idempotente de retenção que exclua conteúdo `bytea` expirado e registre contagem/erros.
- [x] T213 [P0] Não excluir versão ou execução necessária para rastreabilidade antes de avaliar dependências e política legal/contratual.
- [x] T214 [P1] Criar relatório operacional do volume de PostgreSQL ocupado por snapshots e artefatos.
- [x] T215 [P1] Definir gatilho de migração para S3/object storage sem alterar o contrato de artefato.

## 13. CI/CD e implantação

- [x] T216 [P0] Criar pipeline de CI para lint, type check, testes, migrations e build do frontend.
- [x] T217 [P0] Executar verificação de dependências vulneráveis e secret scanning no CI.
- [x] T218 [P0] Criar imagem Docker do backend/worker com usuário não root e somente os arquivos necessários.
- [x] T219 [P0] Criar imagem/build de produção do frontend com variáveis públicas separadas de segredos.
- [x] T220 [P0] Documentar implantação da API FastAPI em Heroku ou PaaS equivalente e o worker Docker em ambiente que suporte Docker.
- [x] T221 [P0] Garantir que a API não dependa do Docker socket e que a comunicação com o worker seja autenticada.
- [x] T222 [P1] Configurar migração controlada de banco antes do deploy e rollback documentado para migrações compatíveis.
- [x] T223 [P1] Configurar frontend com URL de API por ambiente, CORS restrito e cookies/headers seguros.
- [x] T224 [P1] Criar checklist de release com migração, segredos, health checks, worker, SMTP, limites e plano de retorno.

## 14. Critérios de aceite do MVP completo

- [x] A organização A não consegue listar, consultar, executar ou baixar recursos da organização B.
- [x] O operador consegue criar um cliente, gerar o usuário padrão e suspender/reativar a licença.
- [x] O usuário padrão precisa trocar a senha antes de utilizar o restante do sistema.
- [x] É possível cadastrar e testar PostgreSQL, Oracle e SQL Server em modo somente leitura por IP público.
- [x] É possível importar CSV, Excel e JSON com validação, limites, snapshot e catálogo.
- [x] CPF, CNPJ, senha, token, API key e string de conexão não aparecem em logs, prompts ou respostas indevidas.
- [x] Um relatório publicado não é sobrescrito: uma alteração cria a próxima versão e a versão antiga continua consultável.
- [x] Uma execução sempre usa e registra a versão publicada mais recente resolvida no início da execução.
- [x] Uma execução sob demanda não bloqueia a API e produz estado, tentativa, erro ou artefato rastreável.
- [x] O usuário consegue listar relatórios prontos e visualizar/exportar CSV, XLSX e PDF quando autorizado.
- [x] O conteúdo binário do MVP fica no PostgreSQL e respeita limite e retenção de três anos configurados no `.env`.
- [x] A configuração de LLM usa API key do cliente por referência de segredo, preset ativo, modelo suportado e reasoning compatível.
- [x] A IA nunca publica ou executa uma definição sem confirmação do usuário.
- [x] O envio SMTP e webhook respeita destinatários, permissões, timeout, retry e auditoria.
- [x] O pipeline comprova validação RestrictedPython, isolamento Docker e rede desabilitada por padrão.
- [x] CI executa testes e impede publicação de segredo ou build quebrado.

## 15. Backlog pós-MVP

- [ ] B001 [P2] Migrar snapshots e artefatos para S3/object storage mantendo `storage_key` e o contrato `ArtifactStore`.
- [ ] B002 [P2] Adicionar JSONL, Parquet, APIs REST/GraphQL e planilhas online.
- [ ] B003 [P2] Adicionar VPN, túnel seguro, agente e conectividade privada para bancos.
- [ ] B004 [P2] Adicionar processamento batch, agendamento, recorrência e monitoramento de jobs.
- [ ] B005 [P2] Adicionar SSO, MFA, recuperação de senha e e-mail transacional.
- [ ] B006 [P2] Adicionar SMTP por organização com rotação e políticas próprias.
- [ ] B007 [P2] Adicionar compartilhamento externo controlado e links temporários para convidados.
- [ ] B008 [P2] Adicionar cobrança, planos, limites comerciais e medição de uso.
- [ ] B009 [P2] Adicionar gVisor, Kata Containers ou Firecracker quando o requisito de isolamento justificar a complexidade.
- [ ] B010 [P2] Adicionar colaboração em tempo real e recursos avançados de BI.

## Definition of Done

Uma tarefa só deve ser marcada como concluída quando:

1. o código está no módulo correto e segue as interfaces definidas;
2. existem testes proporcionais ao risco e eles passam localmente e no CI;
3. migrations, contratos OpenAPI ou componentes afetados foram atualizados;
4. logs, auditoria e mensagens não expõem dados sensíveis;
5. permissões, isolamento por organização e estado da licença foram verificados;
6. a documentação de operação foi atualizada quando a tarefa alterou configuração, deploy ou suporte;
7. o comportamento foi demonstrado com dados sintéticos, nunca com dados reais de cliente.

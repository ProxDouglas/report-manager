# Relatório Service

API de relatórios construída com FastAPI, Python 3.12+ e Uvicorn.

## Pré-requisitos

- Python 3.12 ou superior;
- acesso ao terminal;
- credenciais da OpenAI para as funcionalidades que utilizam LLM;
- driver ODBC do banco de dados, caso a aplicação utilize SQL Server.

Os comandos abaixo devem ser executados a partir da raiz do projeto, no diretório `relatorios-service`.

### Verificar o Python

Linux:

```bash
python3 --version
```

Windows (PowerShell):

```powershell
py --version
```

O projeto utiliza Python 3.12, conforme definido no arquivo `.python-version`.

## Configuração das variáveis de ambiente

Crie o arquivo `.env` na raiz do projeto a partir do exemplo.

Linux:

```bash
cp .env.example .env
```

Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

Edite o `.env` e informe os valores de acordo com o ambiente:

```env
OPENAI_API_KEY=sua-chave
LLM_MODEL=nome-do-modelo
OPENAI_BASE_URL=https://api.openai.com/v1
DATABASE_TYPE=postgres
DATABASE_URL=postgresql+psycopg://usuario:senha@localhost:5432/banco
APP_PORT=8000
```

`OPENAI_BASE_URL` é opcional. Para usar um provedor compatível com a API da
OpenAI, informe o domínio correspondente, por exemplo:

```env
OPENAI_API_KEY=sua-chave-do-deepseek
LLM_MODEL=deepseek-chat
OPENAI_BASE_URL=https://api.deepseek.com
```

Para o DeepSeek, o serviço utiliza o modo JSON compatível com a API do
provedor nas etapas que geram o plano e o SQL.

A aplicação utiliza um único banco por execução. Escolha o tipo e informe
somente a URL correspondente:

```env
# PostgreSQL
DATABASE_TYPE=postgres
DATABASE_URL=postgresql+psycopg://usuario:senha@localhost:5432/banco

# SQL Server
DATABASE_TYPE=sqlserver
DATABASE_URL=mssql+pyodbc://usuario:senha@servidor:1433/banco?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes

# Oracle
DATABASE_TYPE=oracle
DATABASE_URL=oracle+oracledb://usuario:senha@servidor:1521/?service_name=ORCL
```

Não é necessário configurar as três URLs. Para trocar de banco, altere
`DATABASE_TYPE` e `DATABASE_URL`, reinicie a aplicação e valide em
`GET /database/health`.

O arquivo `.env` contém credenciais e não deve ser versionado.

## Instalação com `uv`

O `uv` cria e gerencia o ambiente virtual, instala as dependências e utiliza o arquivo `uv.lock` para reproduzir as versões travadas.

### 1. Instalar o `uv`

Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Feche e abra o terminal novamente. Se o comando `uv` ainda não for encontrado, carregue o ambiente:

```bash
source "$HOME/.local/bin/env"
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Abra um novo PowerShell depois da instalação.

Confirme a instalação nos dois sistemas:

```text
uv --version
```

### 2. Criar o ambiente e instalar as dependências

Linux ou Windows:

```text
uv sync
```

Esse comando cria ou atualiza o ambiente `.venv`, instala o projeto e sincroniza as dependências conforme o `uv.lock`.

Se outro ambiente virtual estiver ativo, desative-o antes:

Linux:

```bash
deactivate
```

Windows (PowerShell):

```powershell
deactivate
```

Não é necessário ativar `.venv` manualmente para executar os comandos usando `uv run`.

### 3. Iniciar a aplicação

Linux ou Windows:

```text
uv run relatorios-service --reload
```

A porta padrão é `8000`. Altere `APP_PORT` no arquivo `.env` para escolher
outra porta. Para iniciar sem recarregamento automático, remova `--reload`.

## Instalação com `pip`

O fluxo com `pip` utiliza um ambiente virtual criado manualmente. O comando `pip install -e .` instala o projeto em modo editável e é necessário porque o código está dentro do diretório `src/`.

### Linux

Crie e ative o ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Atualize o `pip` e instale o projeto:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

O comando acima instala o projeto e as dependências declaradas no `pyproject.toml`.

### Windows (PowerShell)

Crie e ative o ambiente virtual:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Se o PowerShell bloquear a ativação por política de execução, execute, quando permitido pela política da máquina:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Depois, ative novamente o ambiente e instale o projeto:

```powershell
python -m pip install --upgrade pip
python -m pip install -e .
```

### Alternativa usando `requirements.txt`

O arquivo `requirements.txt` contém as dependências compiladas pelo `uv`. Caso seja necessário instalar exatamente a lista desse arquivo com `pip`, execute com o ambiente virtual ativo:

Linux:

```bash
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
```

Windows (PowerShell):

```powershell
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
```

O segundo comando instala o pacote local sem reinstalar as dependências. Use apenas uma das opções de instalação: `pip install -e .` ou a alternativa com `requirements.txt`.

### Iniciar a aplicação com `pip`

Com o ambiente virtual ativo, Linux ou Windows:

```text
relatorios-service --reload
```

Para sair do ambiente virtual:

```text
deactivate
```

## Diferenças entre Linux e Windows

| Tarefa | Linux | Windows (PowerShell) |
| --- | --- | --- |
| Executar o Python | `python3` | `py` ou `py -3.12` |
| Criar o ambiente | `python3 -m venv .venv` | `py -3.12 -m venv .venv` |
| Ativar o ambiente | `source .venv/bin/activate` | `.\\.venv\\Scripts\\Activate.ps1` |
| Copiar o `.env` | `cp .env.example .env` | `Copy-Item .env.example .env` |
| Caminho dos scripts | `.venv/bin/` | `.venv\\Scripts\\` |
| Variável temporária `VIRTUAL_ENV` | `unset VIRTUAL_ENV` | `Remove-Item Env:VIRTUAL_ENV` |

Os comandos `uv sync` e `uv run relatorios-service ...` funcionam nos dois sistemas. No Windows, o shell recomendado neste documento é o PowerShell.

## Acessar e testar a aplicação

Depois da inicialização, a API estará disponível em:

```text
http://127.0.0.1:8000
```

Documentação interativa:

```text
http://127.0.0.1:8000/docs
```

## Análise com texto, gráficos e exportação

O endpoint `POST /analytics/question` interpreta uma pergunta, consulta o
catálogo de métricas, lê a estrutura autorizada do banco, gera uma consulta
`SELECT`, valida a consulta, processa o resultado com Pandas e retorna texto,
dados e um gráfico Plotly.

Exemplo de corpo:

```json
{
  "question": "Compare a métrica mensal entre o Grupo Exemplo A e o Grupo Exemplo B em 2026",
  "export_formats": []
}
```

`chart_type` é opcional. Quando não é enviado, o tipo de cada série pode ser
definido pela pergunta e pelo `ChartSpec` produzido no plano.

O resultado contém um `report_id`, a resposta textual, os dados, o gráfico e os
links de download dos arquivos gerados:

```text
GET /reports/{report_id}/xlsx
GET /reports/{report_id}/csv
GET /reports/{report_id}/chart.json
GET /reports/{report_id}/chart.html
```

Quando houver dados suficientes para gerar um gráfico, `chart.json` contém a
estrutura Plotly e `chart.html` contém uma página HTML autocontida pronta para
abrir no navegador.

As métricas e suas regras ficam em três arquivos com finalidades diferentes:

```text
src/relatorios_service/resources/metrics.json          # local e privado
src/relatorios_service/resources/metrics.example.json  # exemplo versionado
docs/metric_catalog.md                                 # instruções
```

Antes de iniciar a aplicação em um clone novo, crie o arquivo privado a partir
do exemplo:

```bash
cp src/relatorios_service/resources/metrics.example.json \
  src/relatorios_service/resources/metrics.json
```

No PowerShell:

```powershell
Copy-Item src/relatorios_service/resources/metrics.example.json `
  src/relatorios_service/resources/metrics.json
```

O arquivo privado pode conter nomes de tabelas, colunas, relacionamentos e
regras específicas do banco. Ele está no `.gitignore` e não deve ser adicionado
ao commit. O exemplo público usa somente identificadores fictícios. Essa
separação protege o catálogo; referências físicas mantidas em prompts ou em
outros módulos também precisam ser revisadas para uma anonimização completa.

O catálogo enviado ao modelo funciona como uma allowlist: a LLM só pode
selecionar tabelas e colunas cadastradas, e a SQL é validada antes da execução.
`semantic_mappings` associa termos da pergunta a identificadores autorizados;
valores de filtros são mantidos separadamente em parâmetros nomeados e não
precisam ser listados no JSON.

A métrica `generic_analysis` pode combinar componentes e medidas, desde que as
fontes necessárias estejam explicitamente autorizadas. Medidas podem declarar
um parser para normalizar números, texto numérico ou JSON. Consulte
[docs/metric_catalog.md](docs/metric_catalog.md) para o contrato completo,
regras de privacidade e validação antes do commit.

## Evolução para análises mais livres

A aplicação deve permitir perguntas mais livres sem permitir que a LLM consulte
qualquer tabela do banco. Cada cliente terá um catálogo semântico próprio, com
as tabelas, colunas, relacionamentos e regras de negócio autorizados para sua
conexão.

Exemplo de configuração semântica por cliente:

```json
{
  "client": "cliente_a",
  "concept": "allocation",
  "table": "example_table",
  "columns": {
    "record_id": "id",
    "analysis_date": "record_date",
    "status": "status"
  },
  "allowed_dimensions": [
    "category",
    "date",
    "status"
  ]
}
```

Outro cliente pode usar tabelas e nomes diferentes, mantendo os mesmos
conceitos semânticos. O catálogo deve fazer essa tradução semântico-física
antes da geração do SQL.

As análises planejadas para a evolução do sistema incluem regras genéricas como:

- contar colaboradores distintos;
- verificar ausência com `NOT EXISTS`;
- agrupar por centro de custo, filial ou posto;
- comparar duas métricas;
- calcular déficit e percentual de cobertura;
- filtrar por dia, mês ou intervalo.

Exemplos de perguntas que deverão ser suportadas:

```text
Quais colaboradores não foram alocados no dia 17/09/2026?
Quantos colaboradores foram alocados por filial?
Qual posto de trabalho teve menor cobertura?
Compare demanda e alocação por centro de custo em setembro de 2026.
```

### Plano de evolução

1. Criar um catálogo semântico por cliente. Inicialmente ele pode ser mantido
   em JSON; posteriormente deve ser armazenado em tabelas próprias, com
   versionamento e auditoria.
2. Ampliar o plano de análise para aceitar mais medidas, dimensões, filtros,
   comparações e operações além da comparação de alocação e demanda em horas.
3. Permitir geração de SQL mais livre, limitada às tabelas cadastradas e
   validada antes da execução.

O fluxo esperado será:

```text
Cliente autenticado
    -> catálogo semântico do cliente
    -> introspecção das tabelas autorizadas
    -> plano de análise
    -> SQL somente leitura
    -> validação de tabelas, comandos e limites
    -> Pandas, gráfico e exportação
```

Mesmo com análises mais livres, a aplicação deve manter:

- usuário de banco somente leitura;
- lista de tabelas autorizadas por cliente;
- validação de SQL antes da execução;
- limite de linhas retornadas;
- limite de tempo de consulta;
- auditoria da pergunta, plano e SQL executado;
- proteção de dados sensíveis e controle de acesso por cliente.

RAG não substitui o catálogo semântico. Ele pode ser adicionado posteriormente
para recuperar políticas, manuais, glossários e regras documentais extensas.
Para tabelas, colunas e relacionamentos, o catálogo estruturado e a
introspecção do banco continuam sendo a fonte principal.

Teste rápido no Linux:

```bash
curl http://127.0.0.1:8000/health
```

Teste rápido no Windows (PowerShell):

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Resposta esperada:

```json
{"status":"ok"}
```

## Banco de dados e drivers

O pacote Python `pyodbc` não instala o driver ODBC do banco de dados. Para utilizar SQL Server, instale também o Microsoft ODBC Driver for SQL Server no sistema operacional.

No Linux, o driver deve ser instalado pelo gerenciador de pacotes da distribuição. No Windows, utilize o instalador oficial do Microsoft ODBC Driver e confirme que a arquitetura do driver (x64 ou x86) é compatível com o Python e com a aplicação.

As conexões PostgreSQL e Oracle também dependem de um banco acessível e das credenciais configuradas no `.env`.

## Comandos úteis

Verificar a instalação e a versão do FastAPI/Uvicorn:

```text
python -m pip show fastapi uvicorn
```

Atualizar o ambiente com `uv` após alterações no `pyproject.toml`:

```text
uv sync
```

Parar a aplicação em execução:

```text
Ctrl+C
```

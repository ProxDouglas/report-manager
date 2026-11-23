# Relatório Service

API de relatórios construída com FastAPI, Python 3.12+ e Uvicorn.

## Idiomas

A interface inicia em inglês e permite alternar entre English e Português no seletor do topo.
A preferência é salva no navegador. Novos pipelines usam o idioma selecionado nas
justificativas e limitações da IA; respostas já geradas preservam seu idioma original.
Os objetivos podem ser escritos em português ou inglês. Na API, `POST /pipelines`
aceita `language` com `en` (padrão) ou `pt-BR`. Nomes de colunas e identificadores
técnicos são preservados.

## Pré-requisitos

- Python 3.12 ou superior;
- acesso ao terminal;
- credenciais da OpenAI para as funcionalidades que utilizam LLM.

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
provedor na etapa que gera o plano do pipeline.

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

Abra `http://localhost:8000/` para usar a tela de testes dos pipelines: envie
vários CSVs com um prompt, escolha tratamento separado ou joins e selecione
execução supervisionada ou autônoma. A tela permite revisar etapas, delegar
decisões, consultar até 15 linhas e baixar o CSV de cada etapa executada. Também
é possível corrigir uma etapa concluída, exigindo nova aprovação dela e das
posteriores. Veja [Pipelines de CSV](docs/data_pipelines.md).

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

## Enviar CSV

O endpoint `POST /datasets` valida e guarda temporariamente um CSV. Ele retorna
um `dataset_id`, a quantidade de registros, uma prévia de até 20 linhas e o
perfil de cada coluna:

```bash
curl -X POST http://127.0.0.1:8000/datasets \
  -F "file=@dados.csv"
```

No momento, o armazenamento padrão é local, no diretório `datasets/`. O código
acessa esse armazenamento pela interface `DatasetRepository`, cuja
implementação pode ser substituída por armazenamento em blob ou banco de dados.
Os arquivos expiram após duas horas; a limpeza local roda na inicialização,
periodicamente e também durante novos uploads. O tamanho máximo padrão para
uploads é 25 MiB; CSVs aceitam até 100.000 linhas e 500 colunas.

Os campos `detected_type`, `null_count`, `null_percentage` e `invalid_count`
ajudam a revisar a inferência antes de usar os dados; `normalized_type` informa
o tipo efetivamente convertido. O processamento remove espaços ao redor dos
valores e trata campos vazios, `NULL`, `None`, `N/A`, `N/D` e `NaN` como nulos.
Não preenche nulos com zero. Colunas com nomes de identificador (como `id`,
`codigo`, `matricula`, `cpf`, `cnpj` e `cep`) permanecem texto, preservando
zeros à esquerda. Valores booleanos comuns em português e inglês são
normalizados; números aceitam decimal com vírgula e agrupamento brasileiro
quando o CSV usa `;`; datas ISO e `DD/MM/AAAA` são convertidas quando o formato
é consistente. Os formatos de data aceitos incluem `AAAA-MM-DD`,
`AAAA-MM-DD HH:MM:SS`, `AAAA-MM-DDTHH:MM:SS`, `AAAA/MM/DD`, `DD/MM/AAAA` e
`DD-MM-AAAA`.

Quando uma coluna majoritariamente numérica ou de data contém valores
inválidos, o resultado convertido marca esses valores como nulos e informa
`invalid_count` e até cinco exemplos com o número do registro. O CSV original
permanece no repositório temporário, sem alteração, para possibilitar
reprocessamento. Revise esses avisos antes de usar os dados: registros
inválidos não são descartados da tabela, mas não participam de agregações
numéricas ou temporais.

Para upload múltiplo e tratamento local planejado por LLM, consulte
[Pipelines de CSV](docs/data_pipelines.md). O fluxo permite tratar arquivos
separadamente ou gerar um novo dataset por joins, com decisões por etapa ou
autonomia completa. A LLM recebe somente nomes de colunas e metadados agregados.

## Fontes de dados e processamento

As operações de ELT são centralizadas nos pipelines: planejamento, transformação,
joins, agregações, geração de datasets e gráficos das saídas. As entradas atuais
são arquivos CSV; a prévia de arquivos também aceita os formatos suportados pelo
`FileReader`.

As conexões diretas com PostgreSQL, SQL Server e Oracle foram removidas, assim
como os endpoints `/database/health`, `/analytics/question` e `/reports/...`.
Não é necessário configurar banco externo, drivers ou catálogo de métricas para
executar a aplicação. Futuros conectores serão fontes de entrada dos pipelines,
sem um fluxo paralelo de transformação e análise.

O SQLite local permanece apenas para persistir o estado dos pipelines; os
arquivos de entrada e saída continuam no repositório local de datasets.

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

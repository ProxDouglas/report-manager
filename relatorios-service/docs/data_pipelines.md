# Pipelines de CSV

O backend recebe vários CSVs, calcula os perfis localmente e pede à LLM um
plano JSON. A execução usa operações pandas implementadas pela aplicação.
Nenhum Python, SQL, expressão ou comando retornado pelo modelo é executado.

## Tela de testes

Inicie a aplicação com `uv run relatorios-service --reload` no diretório
`relatorios-service` e abra `http://localhost:8000/` (ou a porta definida em
`APP_PORT`). A interface é servida pelo próprio FastAPI, sem outro processo de
frontend ou instalação de pacotes JavaScript.

1. Adicione os CSVs, arrastando ou selecionando vários arquivos.
2. Descreva o objetivo no campo de prompt, usando os aliases `tabela_1`,
   `tabela_2` etc. que aparecem ao lado dos arquivos. Os nomes de arquivos não
   são usados como aliases enviados ao modelo.
3. Escolha tratar os arquivos separadamente ou conectá-los por joins.
4. Selecione **Supervisionado** ou **Autônomo** e clique em **Gerar pipeline**.
5. Revise o plano e clique em **Executar pipeline**. No modo supervisionado,
   aprove, ajuste os parâmetros em JSON, delegue uma etapa ou delegue as restantes.
6. Abra **Ver resultado da etapa** em qualquer etapa concluída para consultar
   até 15 linhas tratadas e baixar o CSV completo, sem paginação.
7. Se precisar corrigir uma etapa concluída, abra **Corrigir etapa executada**,
   ajuste sua definição JSON preservando o `id` e salve. A etapa corrigida e
   todas as posteriores voltam a exigir aprovação; as anteriores são preservadas.
8. Baixe os resultados finais quando a execução terminar.

O prompt é enviado à LLM junto com os metadados permitidos. Não inclua dados
sensíveis ou registros nesse texto. O campo é opcional e aceita até 4.000 caracteres.
As células dos arquivos e as prévias retornadas pelo upload não são adicionadas
ao prompt. O modo escolhido na interface prevalece sobre instruções conflitantes.

A interface não persiste a execução no localStorage. Ao recarregar, a tela
abre vazia e permite anexar novos arquivos. **Novo pipeline** limpa a tela; não cancela uma execução no servidor.
Use **Cancelar execução** quando uma etapa estiver aguardando decisão.

## Privacidade

Além do prompt opcional digitado pelo usuário, o planejador recebe por padrão:

- Aliases das tabelas e nomes originais das colunas.
- Quantidade de registros, separador, tipos detectados e tipos sugeridos.
- Contagens e percentuais de nulos, quantidade de valores distintos, duplicados,
  valores incompatíveis com o tipo inferido e valores com espaços nas extremidades.
- Formatos de data de uma lista fixa e contagens de números com vírgula ou ponto.
- Máscaras estruturais e frequências calculadas localmente sobre todos os valores
  não nulos de cada coluna. `0` representa dígito, `A` representa letra e `?`
  substitui símbolos fora da lista de pontuação de formatos. Exemplos: `000.00`,
  `000.00 %` e `AA-000`. São enviadas as 10 máscaras mais frequentes, limitadas
  a 80 caracteres (`…` indica truncamento), e `other_format_count` conta os demais
  registros. Números e letras originais não são enviados. As máscaras não provam
  significado, escala ou convenção decimal; ambiguidades precisam de revisão.

Com `allow_data_sample: true`, até 5 linhas por arquivo também são enviadas ao LLM.
O padrão é `false`, sem envio de células. Não são enviados nomes de arquivos,
identificadores internos de datasets ou exemplos adicionais de erros. O perfil enviado é construído por uma lista explícita de campos permitidos;
não reutiliza os exemplos presentes na resposta de upload. A inferência do significado
das colunas usa seus nomes e continua sendo uma hipótese.

A LLM é chamada apenas no planejamento. Execução, decisões do usuário e relatórios
de etapas são locais. Falhas não causam tentativas de enviar dados ao modelo.
Os endpoints de upload e download podem retornar dados ao próprio cliente da API.
O fluxo de análise direta sobre bancos foi removido. Novas fontes de dados
deverão fornecer entradas aos pipelines, que centralizam as operações de ELT.

## 1. Enviar arquivos

```bash
curl -X POST http://127.0.0.1:8000/datasets/batch \
  -F 'files=@clientes.csv' \
  -F 'files=@pedidos.csv'
```

Retorna `datasets`, com a resposta de upload individual para cada arquivo.
Todos os arquivos são validados antes da gravação. Se uma gravação falhar,
o serviço tenta remover os arquivos já gravados naquele lote.
O endpoint existente `POST /datasets` continua aceitando um arquivo.

## 2. Criar um plano

```http
POST /pipelines
Content-Type: application/json

{
  "datasets": [
    {"alias": "clientes", "dataset_id": "IDENTIFICADOR_CLIENTES"},
    {"alias": "pedidos", "dataset_id": "IDENTIFICADOR_PEDIDOS"}
  ],
  "prompt": "Padronize os formatos e relacione pedidos a clientes por cliente_id.",
  "mode": "joined",
  "autonomy": "supervised",
  "allow_data_sample": false
}
```

Substitua os identificadores pelos valores de 32 caracteres hexadecimais retornados
no upload. Aliases devem começar por letra e conter somente letras ASCII, números
ou `_`, com no máximo 64 caracteres. Colunas preservam seus nomes originais.

`separate` exige uma saída por origem e proíbe joins. `joined` exige pelo menos
duas origens e uma saída que relacione todas elas. Joins com uma mesma origem
nos dois lados não são permitidos nesta versão.

A resposta contém `id`, `request`, `plan`, `status`, `next_step`,
`pending_decision`, `reports`, `outputs` e `error`. Criar um plano não executa etapas.
O plano usa os aliases originais ou o `id` de uma etapa anterior como entradas.
Cada etapa possui uma justificativa (`reason`). As saídas referenciam essas entradas.
Referências futuras, colunas inexistentes, operações desconhecidas e parâmetros
extras são rejeitados antes da execução.

## 3. Executar e decidir

```http
POST /pipelines/IDENTIFICADOR_PIPELINE/run
```

No modo `supervised`, a execução para **antes de cada etapa** e retorna
`status=awaiting_decision`. `pending_decision` pergunta se o usuário decide ou
delega ao sistema, informando o `step_id` e as ações disponíveis:

| Ação | Comportamento |
|---|---|
| `approve` | O usuário confirma a etapa proposta ou a ajusta usando `replacement`. |
| `delegate_step` | O sistema aplica a proposta da LLM apenas nesta etapa; a seguinte volta a perguntar. |
| `delegate_remaining` | Autoriza o sistema a decidir esta etapa e todas as seguintes. |
| `cancel` | Cancela sem executar a etapa pendente. |

```http
POST /pipelines/IDENTIFICADOR_PIPELINE/decisions
Content-Type: application/json

{"step_id": "normalizar_clientes", "action": "delegate_step"}
```

Para alterar a proposta, envie `action=approve` e `replacement` com a definição
completa da etapa, preservando seu `id`. Exemplo de conversão explicitamente
autorizada pelo usuário:

```json
{
  "step_id": "converter_valor",
  "action": "approve",
  "replacement": {
    "id": "converter_valor",
    "operation": "cast",
    "input": "valores_sem_nulos_textuais",
    "columns": ["valor"],
    "target": "number",
    "number_format": "brazilian",
    "errors": "null",
    "reason": "Converter os valores e marcar entradas incompatíveis como nulas."
  }
}
```

O novo plano completo é validado antes de aceitar o ajuste. Este endpoint ajusta
somente a etapa pendente. Uma decisão para outra etapa retorna `409`.
Chamadas simultâneas são serializadas pelo repositório local.

`autonomy=autonomous` na criação é a autorização explícita para executar todas
as etapas sem perguntas adicionais. Falhas de conversão, cardinalidade ou limites
interrompem inclusive a execução autônoma: o pipeline retorna ao modo assistido,
com mensagem sem valores brutos, permitindo ajustar a etapa ou cancelar.

`GET /pipelines/IDENTIFICADOR_PIPELINE` consulta o estado. Após cada decisão,
a execução avança até a próxima pergunta ou a conclusão. Repetir `run` em um
pipeline pendente, cancelado ou concluído apenas retorna seu estado.

## Consultar e corrigir etapas executadas

- `GET /pipelines/{id}/steps/{step_id}/preview`: retorna `step_id`, `columns`,
  `rows` (até 15 linhas) e `row_count` (total). As células da prévia são textos
  ou `null`, preservando identificadores e inteiros grandes no navegador.
- `GET /pipelines/{id}/steps/{step_id}/csv`: baixa todos os registros tratados
  pela etapa, em CSV UTF-8.
- `PUT /pipelines/{id}/steps/{step_id}`: recebe `replacement` (definição completa
  da etapa com o mesmo `id`) e `expected_revision` (campo `revision` do estado).

Os resultados são reconstruídos localmente a partir dos arquivos originais e do
prefixo executado, preservando os tipos entre operações, sem consultar a LLM.
A consulta segue a retenção dos arquivos e do pipeline. Etapas ainda não
executadas ou invalidadas retornam `409`; pipelines expirados retornam `404`.

A correção valida o plano completo antes de alterar o estado. Se aceita, incrementa
`revision`, mantém as etapas anteriores, remove os relatórios da etapa alterada
em diante, limpa as saídas finais do estado e deixa a etapa corrigida aguardando
decisão em modo supervisionado. Cada etapa seguinte exige nova aprovação;
a delegação continua disponível caso o usuário a autorize explicitamente.
Uma revisão desatualizada ou tentativa de corrigir um pipeline cancelado retorna
`409`. Um ajuste inválido preserva o estado anterior.

## Operações disponíveis

| Operação | Parâmetros específicos |
|---|---|
| `trim` | `input`, `columns`: remove espaços nas extremidades de texto. |
| `null_markers` | `input`, `columns`: converte vazio, NULL, None, N/A, N/D e NaN em nulos, ignorando caixa. |
| `cast` | `input`, `columns`, `target` (`text`, `integer`, `number`, `date`, `boolean`), `errors` (`fail`, `null`), `number_format` (`standard`, `brazilian`), `date_format`. |
| `drop_nulls` | `input`, `columns`: remove linhas com nulo em qualquer coluna selecionada. |
| `deduplicate` | `input`, `columns`, `keep` (`first`, `last`, `none`). |
| `fill_nulls` | `input`, `columns`, `strategy` (`mean`, `median`, `mode`, `zero`); valores calculados localmente. |
| `select` | `input`, `columns`: mantém somente as colunas selecionadas. |
| `join` | `left`, `right`, `left_on`, `right_on`, `how`, `cardinality`. |
| `filter` | `input`, `conditions` (`column`, `operator`, `values`), `match`: `all` (E) ou `any` (OU). Operadores: `eq`, `ne`, `in`, `not_in`, `gt`, `ge`, `lt`, `le`, `is_null`, `not_null`. |
| `split_explode` | `input`, `column`, `separator` literal, `strip` (padrão `true`): transforma itens em linhas, repetindo as demais colunas. |
| `aggregate` | `input`, `group_by` (vazio para totais globais), `metrics`: `function`, `column`, `alias`. Funções: `size`, `count`, `nunique`, `sum`, `mean`, `median`, `min`, `max`. |
| `bucket` | `input`, `column`, `output_column` nova, `edges`, `labels`, `scale`: `number`, `percent`, `fraction`, `percent_text`. |

`filter` não converte tipos. Valores dos filtros vêm do pedido ou de amostras
autorizadas. Nulos só passam por condições explícitas `is_null`/`not_null`.
Operadores de pertinência exigem ao menos um valor; comparações recebem um valor;
operadores de nulos não recebem valores.

`aggregate`: `size` conta linhas e não recebe coluna; `count` conta valores não
nulos; `nunique` conta distintos não nulos. As demais funções exigem coluna
numérica convertida explicitamente. Grupos nulos são preservados. Somas de grupos
inteiramente nulos permanecem nulas. Os aliases não podem colidir com agrupamentos.

`bucket` aceita qualquer intervalo numérico com limites finitos estritamente
crescentes e um rótulo único por faixa. Usa `[início, fim)`, incluindo o limite
final na última faixa. Nulos permanecem nulos; valores inválidos ou fora das
faixas interrompem a etapa. A coluna original é preservada. Escalas percentuais
exigem limites cobrindo 0–100: `percent` usa 0–100, `fraction` converte 0–1,
`percent_text` lê texto com `%` e ponto ou vírgula decimal. `number` mantém a
escala original, inclusive valores negativos. A escala não é inferida pela máscara.
Faixas sem limites de negócio explícitos devem ser revisadas no plano.

Exemplo: separar tipos de Pokémon por vírgula, filtrar `Ice`/`Normal`, agrupar por
tipo e calcular `size` com alias `quantidade`. Para contar percentuais por faixa,
use `bucket` com `edges: [0, 25, 50, 75, 100]` e quatro rótulos; depois `aggregate`
por essa nova coluna com métrica `size`. Faixas sem registros não são criadas
artificialmente. Para somar ou tirar média dos próprios percentuais textuais,
use antes `cast` numérico com `strip_percent: true` (preserva escala 0–100) e
`number_format: brazilian` quando houver vírgula decimal.

Todos exigem `id`, `operation` e `reason`. `cast` de data exige `date_format`
explícito: `%Y-%m-%d`, `%Y-%m-%d %H:%M:%S`, `%Y-%m-%dT%H:%M:%S`,
`%Y/%m/%d`, `%d/%m/%Y`, `%d/%m/%Y %H:%M:%S` ou `%d-%m-%Y`.
Por padrão, uma conversão incompatível falha; não substitui valores silenciosamente.
Conversão booleana reconhece true/false, sim/não/nao e yes/no.
Preenchimento por moda exige um único valor mais frequente; empates interrompem
a etapa. Média, mediana e zero exigem coluna numérica.

Os dados começam como texto, preservando espaços, marcadores de nulos e zeros
à esquerda. Limpeza e conversão são etapas explícitas. A inferência de tipos é
usada para o planejamento e não modifica os arquivos originais.

## Joins e limites

Joins aceitam chaves simples ou compostas, tipos `inner`, `left`, `right` e
`outer`, com cardinalidades `one_to_one`, `one_to_many`, `many_to_one` e
`many_to_many`. A aplicação verifica a unicidade correspondente à cardinalidade
declarada. Chaves nulas nunca se relacionam entre si. Colunas sobrepostas recebem
os sufixos `_left` e `_right`; colisões de nomes são rejeitadas.

Antes de materializar o join, a aplicação calcula sua quantidade de linhas
com base nas frequências das chaves. Resultados acima do limite são rejeitados,
inclusive em joins muitos-para-muitos. Chaves devem ter tipos compatíveis.
Sem evidência suficiente para escolher chaves com segurança, use o modo assistido
para revisar as sugestões. Não há garantia de correção semântica somente pelos nomes.

Limites padrão configuráveis:

| Variável | Padrão |
|---|---|
| `MAX_UPLOAD_FILES` | 10 arquivos por envio |
| `MAX_UPLOAD_BYTES` | 25 MiB por arquivo |
| `MAX_BATCH_UPLOAD_BYTES` | 100 MiB por envio |
| `MAX_DATASET_ROWS` | 100.000 linhas por entrada ou resultado de etapa |
| `MAX_DATASET_COLUMNS` | 500 colunas por entrada ou resultado de etapa |
| `DATASET_RETENTION_SECONDS` | 7.200 segundos |

O contrato do pipeline aceita no máximo 10 entradas e 30 etapas. O processamento
é síncrono e local; distribuições grandes exigem ajustar limites ao ambiente.

## Resultados e persistência

Ao concluir, `outputs` informa referência, `dataset_id`, quantidade de linhas e
colunas de cada novo dataset. Baixe com `GET /datasets/DATASET_ID/csv`.
As saídas são CSVs em UTF-8 com BOM. Os originais são preservados.
Resultados vazios podem ser baixados, mas o upload/leitor de entrada atual exige
ao menos um registro para criar outro pipeline a partir deles.

O estado é salvo em SQLite, em `DATASETS_DIRECTORY/.pipelines.sqlite3`, sem
registros brutos ou amostras. Decisões confirmadas e contagens de execução ficam
nos relatórios por etapa. Reiniciar a aplicação preserva pipelines pendentes.
O estado tem a mesma duração de retenção configurada para datasets, contada
desde a criação do pipeline. Os CSVs de entrada mantêm sua própria expiração:
se expirarem antes de uma retomada, a API retorna `404` e exige novo upload.

Na retomada, o executor reconstrói localmente as etapas já aprovadas a partir
dos originais. Isso evita checkpoints com dados brutos no estado e mantém os
tipos durante a execução; a LLM não é chamada novamente. A limpeza periódica
remove estados e arquivos expirados. Este armazenamento é local à instância;
réplicas sem volume compartilhado precisam de repositórios compartilhados.

## Gerar gráficos das saídas

Após concluir o pipeline, cada saída na interface permite selecionar eixo X,
série numérica e tipo (barras, linhas, pizza ou dispersão). O gráfico interativo
abre em outra aba e é gerado localmente, sem chamadas ao LLM.

`GET /pipelines/{id}/outputs/{reference}/chart?x=coluna_x&y=coluna_y&chart_type=bar`
retorna HTML completo com Plotly incluído. A série deve ser numérica e sem nulos.
Os registros são exibidos diretamente, sem agregação automática.

O plano também pode incluir `charts`, com `reference` de uma saída, `x`, `y` e
`chart_type` (`bar`, `line`, `pie`, `scatter`). As referências e colunas são
validadas antes da execução. A interface exibe o gráfico planejado ao concluir
uma saída não vazia e preenche seus controles. O endpoint aceita os parâmetros
omitidos quando há gráfico no plano. Dados vazios ou séries não numéricas/nulas
continuam sendo rejeitados na renderização.

`limitations` registra partes do pedido que o planejador não consegue atender
e é exibido na revisão. Não há verificação semântica automática garantindo que
um plano satisfaça integralmente qualquer pedido em linguagem natural.


### Extração de medidas sem conversão

O perfil local inclui `measurements`, com cobertura de reconhecimento, número máximo de
pares e contagens de unidades por posição, por formato numérico. Não envia os valores
individuais à LLM. O reconhecimento usa um catálogo controlado de unidades e aceita
unidades compostas como `kg/m³` e `unidades/m³`; unidades desconhecidas ou texto residual
não são descartados silenciosamente.

A operação `extract_measurements` recebe `column`, `pairs` (1 a 10), `number_format`
(`standard` ou `brazilian`) e `errors` (`fail` por padrão, ou `null` com justificativa).
Preserva a coluna original e cria `<column>_value_1`, `<column>_unit_1` etc.
Os valores são numéricos e as unidades mantêm sua escrita original. Pares ausentes
ficam nulos. Quantidade de pares excedente ou formato incompatível falha; com
`errors=null`, todos os componentes da célula incompatível ficam nulos.
Nomes existentes não são sobrescritos e o limite de colunas do pipeline é respeitado.

Exemplo: `135.5 kg (298.7 lbs)` gera `135.5`, `kg`, `298.7`, `lbs` em quatro
colunas adicionais. Nenhuma unidade ou escala é convertida. Normalizações e conversões
de medidas precisam ser solicitadas explicitamente. O planejamento deve filtrar ou
agrupar pela unidade quando houver unidades diferentes na mesma posição.

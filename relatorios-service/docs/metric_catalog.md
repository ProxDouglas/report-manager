# Catálogo de métricas

O arquivo `src/relatorios_service/resources/metrics.json` é a fonte estruturada
usada pela aplicação para interpretar perguntas e restringir tabelas, colunas e
regras de negócio.

Este arquivo deve ser atualizado quando o modelo real do banco for conhecido.
Os nomes atuais são exemplos:

## employee_terminations

- Tabela: `employee_terminations`
- Regra padrão: contar registros com `termination_type = 'DISMISSAL'`.
- Dimensões: mês, tipo de desligamento e motivo.

## medical_leave_events

- Tabela: `employee_leaves`
- Regra padrão: contar registros com `leave_type = 'MEDICAL_CERTIFICATE'`.
- Dimensões: mês, tipo de afastamento e motivo.

## Como cadastrar uma métrica

Adicione um objeto em `metrics.json` contendo:

- `key`: identificador estável;
- `label`: nome apresentado ao usuário;
- `description`: explicação da métrica;
- `business_rule`: regra de negócio explícita;
- `allowed_tables`: tabelas que podem ser consultadas;
- `known_columns`: vocabulário legado de colunas conhecidas para orientar o
  modelo; não é uma lista de valores de filtro;
- `allowed_dimensions`: dimensões permitidas para agrupamento;
- `allowed_measures`: medidas semânticas que podem aparecer no resultado;
- `measures`: definição da origem (`table` ou `tables`), parser, unidade e
  exemplo de cada medida;
- `semantic_mappings`: termos usados na pergunta associados à tabela e à
  coluna física, além do nome e tipo do parâmetro SQL (`text`, `date`,
  `number` ou `boolean`);
- `synonyms`: termos que o usuário pode utilizar;
- `allowed_columns`: colunas autorizadas por tabela. Toda tabela usada pela
  métrica precisa possuir uma lista, que é validada contra os identificadores
  da SQL final;
- `table_descriptions`: descrição semântica das tabelas;
- `source_mapping`: relação entre conceitos e tabelas de origem.

Na métrica `demand_restrictions`, `demanda` é a coluna da tabela
`configuracao`. Ela não deve ser cadastrada como tabela nem aparecer em
`FROM demanda` ou `JOIN demanda`.

## Análise genérica

A métrica `generic_analysis` permite perguntas que não correspondem a uma
métrica específica. Ela não libera o banco inteiro: a LLM só pode escolher
tabelas listadas em `allowed_tables`.

O plano gerado também possui o campo `tables`, com as tabelas necessárias para
a análise. A aplicação consulta a estrutura dessas tabelas e envia para a LLM:

- todas as colunas encontradas nas tabelas autorizadas;
- colunas semânticas sugeridas pelo catálogo;
- chave primária;
- chaves estrangeiras;
- tabela referenciada e suas colunas;
- descrição semântica da tabela.

Os joins não precisam ser cadastrados manualmente. A LLM pode combinar as
tabelas autorizadas usando as chaves retornadas pela introspecção do banco. O
SQL final continua sendo validado contra a lista de tabelas selecionadas e as
colunas cadastradas.

Para adicionar uma tabela ao escopo genérico, inclua-a em `allowed_tables`,
descreva suas colunas em `allowed_columns`, adicione os termos necessários em
`semantic_mappings` e informe sua finalidade em `table_descriptions`.

Os valores dos filtros não são permissões. Por exemplo, `Empresa Teste` não
precisa ser listado no catálogo. O mapeamento `empresa` para `empresa.descr`
é validado, e o valor é enviado separadamente em um parâmetro SQL nomeado.

## Alocação versus demanda em horas

A métrica `allocation_vs_demand` deve ser usada para comparações de horas.

- `allocation_hours`: soma de `distribuicao.hor_00` até `hor_23`;
- `demand_hours`: parser `weekly_24h_json` aplicado ao campo `restricao` de
  `restr_emp` ou `restr_fil`, conforme `configuracao.demanda`;
- `deficit_hours`: demanda menos alocação;
- `coverage_percent`: alocação dividida pela demanda vezes 100.

O SQL deve retornar `allocation_hours`, `demand_schedule` e `analysis_date`.
O normalizador interpreta o JSON, escolhe o vetor do dia da semana e produz
`demand_hours`. O significado de `restricao` como escala semanal é uma regra
específica deste banco e deve ser revisado se outro banco for conectado. As
tabelas de restrição não possuem data no catálogo atual; por isso, a demanda
não deve ser multiplicada pela quantidade de dias do período sem uma regra de
negócio explícita.

Markdown é usado para explicar o catálogo. A aplicação usa JSON para conseguir
validar automaticamente as consultas.

# Política de importação de arquivos

As importações são determinísticas e nunca executam fórmulas ou macros.

- CSV usa `encoding`, `delimiter`, `has_header` e `header_row`; cabeçalhos duplicados são rejeitados.
- Excel usa a primeira planilha por padrão, `sheet_name` e `header_row`; `.xls` usa `xlrd` e `.xlsx` usa `openpyxl` em modo somente leitura.
- Células vazias usam `empty_cell_strategy`: `NULL` (padrão), `EMPTY_STRING` ou `REJECT`.
- Colunas ausentes usam `column_consistency_strategy=PAD_MISSING_WITH_NULL` (padrão) ou `REJECT`.
- Fórmulas usam somente o valor cacheado pelo Excel (`formula_strategy=USE_CACHED_VALUE`). Se não houver cache, o valor fica nulo. `REJECT` bloqueia a planilha que contém fórmula.
- Planilhas protegidas são lidas sem desbloqueio por padrão (`protected_sheet_strategy=ALLOW_READ_ONLY`); `REJECT` impede a importação.
- Datas somente são convertidas quando o nome aparece em `date_columns`; `date_format` define o formato. Datas inválidas ficam como texto por padrão, podem virar nulo com `COERCE_NULL` ou causar rejeição com `REJECT`.
- Uma versão inválida nunca substitui a versão válida anterior. O arquivo original e o snapshot validado ficam associados à versão no PostgreSQL durante o MVP.

Macros, links externos, execução de fórmula e desbloqueio de planilha não fazem parte do MVP.

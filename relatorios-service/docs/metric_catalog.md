# Catálogo de métricas

O catálogo é a allowlist semântica usada pela aplicação para interpretar
perguntas e restringir as tabelas e colunas que podem aparecer na SQL.

## Separação entre exemplo público e catálogo privado

O repositório deve conter somente o arquivo fictício:

```text
src/relatorios_service/resources/metrics.example.json
```

O arquivo usado pela aplicação em cada ambiente é criado localmente:

```text
src/relatorios_service/resources/metrics.json
```

`metrics.json` é ignorado por `relatorios-service/.gitignore` porque pode
conter nomes de tabelas, colunas, relacionamentos e regras internas do banco.
O arquivo `metrics.example.json` usa apenas nomes e valores fictícios e pode ser
versionado como documentação do formato.

### Preparar um ambiente local

A partir de `relatorios-service`, faça uma cópia do exemplo:

```bash
cp src/relatorios_service/resources/metrics.example.json \
  src/relatorios_service/resources/metrics.json
```

Depois, edite somente a cópia local e substitua os valores fictícios pelas
informações necessárias do ambiente. No PowerShell, use:

```powershell
Copy-Item src/relatorios_service/resources/metrics.example.json `
  src/relatorios_service/resources/metrics.json
```

Confira se o arquivo está sendo ignorado antes de compartilhar as alterações:

```bash
git check-ignore -v src/relatorios_service/resources/metrics.json
git ls-files --error-unmatch src/relatorios_service/resources/metrics.json
```

O primeiro comando deve mostrar a regra do `.gitignore`. O segundo deve falhar
quando o arquivo não estiver versionado. O exemplo público, as instruções e as
alterações do código podem ser enviados normalmente.

Se o arquivo já tiver sido versionado em um clone existente, remova somente a
cópia do índice, preservando o arquivo local:

```bash
git rm --cached src/relatorios_service/resources/metrics.json
```

O `.gitignore` não remove uma cópia que já esteja em commits antigos. Se o
arquivo real já tiver sido publicado, a remoção do histórico deve ser avaliada
com a política do repositório antes do compartilhamento.

Esta separação protege o catálogo, mas não anonimiza referências físicas que
estejam em prompts, validadores ou outros módulos do código. Para ocultar
completamente o schema, revise esses pontos e mova os mapeamentos específicos
para a configuração privada antes de publicar o repositório.

## Como criar uma métrica

Comece copiando `metrics.example.json`. Cada item da lista raiz representa uma
métrica e deve conter:

- `key`: identificador estável usado no plano de análise;
- `label`: nome amigável exibido ao usuário;
- `description`: explicação curta do que é medido;
- `business_rule`: regra de negócio explícita, incluindo filtros obrigatórios;
- `tables`: allowlist das tabelas que a métrica pode consultar;
- `allowed_dimensions`: dimensões semânticas permitidas para agrupamento;
- `allowed_measures`: medidas semânticas permitidas no resultado;
- `measures`: origem, colunas, parser e unidade de cada medida;
- `semantic_mappings`: associação entre termos da pergunta e identificadores
  físicos, com os parâmetros usados nos filtros;
- `synonyms`: termos alternativos usados pelos usuários;
- `source_mapping`: relação entre conceitos de negócio e suas fontes.

### Allowlist de tabelas e colunas

Cada entrada de `tables` deve informar a descrição da tabela e o mapa de
`columns`. Cadastre somente as colunas necessárias para a métrica:

```json
"tables": {
  "example_table": {
    "description": "Tabela fictícia usada no exemplo.",
    "columns": {
      "id": {
        "description": "Identificador do registro.",
        "example_value": "EXAMPLE-001"
      },
      "record_date": {
        "description": "Data do registro.",
        "example_value": "2026-01-15"
      }
    }
  }
}
```

`example_value` documenta apenas o formato de um valor e deve ser sempre
fictício. Nunca use nomes de clientes, IDs reais, dados pessoais, credenciais,
strings de conexão ou amostras copiadas do banco.

As listas legadas `allowed_tables`, `allowed_columns` e `known_columns` são
derivadas em memória a partir de `tables`; não é necessário repeti-las no
arquivo.

### Medidas e parsers

Uma medida aponta para a tabela e coluna autorizadas e pode definir um parser:

```json
"measures": {
  "total_amount": {
    "table": "example_table",
    "column": "amount",
    "parser": "numeric",
    "unit": "currency"
  }
}
```

Os parsers disponíveis são `passthrough`, `numeric`, `numeric_text`,
`weekly_24h_json` e `comma_separated_24h`. Use somente um parser compatível
com o formato real retornado pela consulta. Formatos novos exigem código e
testes no normalizador.

### Mapeamentos semânticos e filtros

`semantic_mappings` traduz a linguagem da pergunta para a tabela e coluna
autorizadas. O valor informado pelo usuário fica separado do catálogo e deve
ser enviado como parâmetro nomeado:

```json
"semantic_mappings": {
  "record_status": {
    "table": "example_table",
    "column": "status",
    "aliases": ["situação", "status"],
    "parameter": "filter_status",
    "value_type": "text"
  }
}
```

Não cadastre no JSON uma lista de valores possíveis do banco. A autorização é
para identificadores estruturais; valores de filtros, datas e IDs são dados da
pergunta e devem continuar em parâmetros SQL.

## Métrica genérica

Uma métrica genérica pode atender perguntas que combinam mais de uma fonte,
mas não deve liberar o banco inteiro. O modelo só pode escolher tabelas e
colunas que estejam no bloco `tables`, e a SQL continua sendo validada antes da
execução.

Ao usar essa modalidade:

1. inclua apenas as tabelas necessárias;
2. descreva as colunas que o modelo pode conhecer;
3. cadastre os mapeamentos semânticos relevantes;
4. defina medidas e dimensões com nomes estáveis;
5. documente regras de negócio específicas em `business_rule`.

Relacionamentos e chaves podem ser confirmados pela introspecção privada do
banco durante a execução. Isso não significa que a estrutura inteira deva ser
copiada para o repositório.

## Validação antes do commit

Valide a sintaxe JSON e o schema do catálogo usando o arquivo privado local:

```bash
python -m json.tool src/relatorios_service/resources/metrics.json >/dev/null
uv run python -c "from relatorios_service.metric_catalog import MetricCatalog; MetricCatalog()"
git diff --check
```

Confirme também que os arquivos públicos não possuem nomes de tabelas, colunas
ou valores do ambiente real. O arquivo `metrics.example.json` deve continuar
sendo suficiente para que outra pessoa entenda o formato sem receber o schema
do banco.

Markdown documenta o contrato e o processo. O JSON privado é a fonte
operacional carregada por `MetricCatalog`.

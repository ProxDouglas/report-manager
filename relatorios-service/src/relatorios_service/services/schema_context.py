import json
from typing import Any

from relatorios_service.repositories.analytics_repository import (
    AnalyticsSession,
)
from relatorios_service.schemas import MetricDefinition


def build_schema_context(
    session: AnalyticsSession,
    metric: MetricDefinition,
    selected_tables: list[str],
) -> str:
    available_tables = set(session.table_names())
    missing_tables = [
        table
        for table in selected_tables
        if table not in available_tables
    ]

    if missing_tables:
        names = ", ".join(missing_tables)
        raise ValueError(
            f"As tabelas da métrica não foram encontradas: {names}. "
            "Atualize o catálogo de métricas."
        )

    missing_column_catalog = [
        table
        for table in selected_tables
        if table not in metric.allowed_columns
    ]
    if missing_column_catalog:
        names = ", ".join(missing_column_catalog)
        raise ValueError(
            f"As tabelas não possuem colunas autorizadas no catálogo: "
            f"{names}. Atualize tables.<tabela>.columns."
        )

    definitions = []
    for table in selected_tables:
        configured_columns = metric.allowed_columns.get(table)
        if configured_columns is None:
            raise ValueError(
                f"A tabela {table} não possui colunas autorizadas "
                "no catálogo."
            )

        table_schema = session.inspect_table(table, configured_columns)
        missing_columns = [
            column
            for column in configured_columns
            if column not in table_schema.columns
        ]

        if missing_columns:
            names = ", ".join(missing_columns)
            raise ValueError(
                f"As colunas autorizadas não existem em {table}: "
                f"{names}. Atualize o catálogo."
            )

        sample_rows = table_schema.sample_rows

        table_definition = metric.tables.get(table)
        column_definitions = {}
        if table_definition:
            column_definitions = table_definition.columns

        definitions.append(
            {
                "table": table,
                "description": metric.table_descriptions.get(table, ""),
                "columns": [
                    schema_column_context(
                        column_name,
                        table_schema.columns,
                        column_definitions,
                    )
                    for column_name in configured_columns
                ],
                "catalog_columns": configured_columns,
                "catalog_columns_enforced": True,
                "sample_rows": sample_rows,
                "primary_key": table_schema.primary_key,
                "foreign_keys": [
                    {
                        "columns": foreign_key.get(
                            "constrained_columns", []
                        ),
                        "referred_schema": foreign_key.get(
                            "referred_schema"
                        ),
                        "referred_table": foreign_key.get(
                            "referred_table"
                        ),
                        "referred_columns": foreign_key.get(
                            "referred_columns", []
                        ),
                    }
                    for foreign_key in table_schema.foreign_keys
                ],
            }
        )

    return json.dumps(definitions, ensure_ascii=False, indent=2, default=str)



def schema_column_context(
    column_name: str,
    database_columns: dict[str, str],
    catalog_columns: dict[str, Any],
) -> dict[str, Any]:
    definition = catalog_columns.get(column_name)
    context = {
        "name": column_name,
        "type": database_columns[column_name],
        "description": "",
    }

    if definition is not None:
        context["description"] = definition.description

        if definition.example_value is not None:
            context["example_value"] = definition.example_value

    return context

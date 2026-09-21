import json
from pathlib import Path

from relatorios_service.schemas import MetricDefinition


class MetricCatalog:
    def __init__(self, catalog_path: Path | None = None) -> None:
        default_path = Path(__file__).parent / "resources" / "metrics.json"
        path = catalog_path or default_path

        content = path.read_text(encoding="utf-8")
        raw_metrics = json.loads(content)
        self._metrics = {}

        for raw_metric in raw_metrics:
            metric = MetricDefinition.model_validate(raw_metric)
            self._validate_metric(metric)
            self._metrics[metric.key] = metric

    def get(self, key: str) -> MetricDefinition:
        metric = self._metrics.get(key)

        if not metric:
            available = ", ".join(sorted(self._metrics))
            raise ValueError(
                f"Métrica não cadastrada: {key}. Disponíveis: {available}"
            )

        return metric

    def _validate_metric(self, metric: MetricDefinition) -> None:
        allowed_tables = set(metric.allowed_tables)

        if metric.tables:
            empty_tables = [
                table
                for table, definition in metric.tables.items()
                if not definition.columns
            ]
            if empty_tables:
                names = ", ".join(sorted(empty_tables))
                raise ValueError(
                    f"As tabelas não possuem colunas cadastradas: {names}"
                )

        unknown_column_tables = set(metric.allowed_columns) - allowed_tables
        if unknown_column_tables:
            names = ", ".join(sorted(unknown_column_tables))
            raise ValueError(
                f"O catálogo de colunas usa tabelas não autorizadas: {names}"
            )

        for name, mapping in metric.semantic_mappings.items():
            if mapping.table not in allowed_tables:
                raise ValueError(
                    f"O mapeamento semântico {name} usa a tabela não "
                    f"autorizada: {mapping.table}"
                )

            configured_columns = metric.allowed_columns.get(mapping.table)
            if (
                configured_columns is not None
                and mapping.column not in configured_columns
            ):
                raise ValueError(
                    f"O mapeamento semântico {name} usa a coluna não "
                    f"autorizada: {mapping.table}.{mapping.column}"
                )

        for name, measure in metric.measures.items():
            measure_tables = list(measure.tables)
            if measure.table:
                measure_tables.append(measure.table)

            for table in measure_tables:
                if table not in allowed_tables:
                    raise ValueError(
                        f"A medida {name} usa a tabela não autorizada: "
                        f"{table}"
                    )

                configured_columns = metric.allowed_columns.get(table, [])
                measure_columns = list(measure.columns)
                if measure.column:
                    measure_columns.append(measure.column)

                unknown_columns = set(measure_columns) - set(
                    configured_columns
                )
                if unknown_columns:
                    names = ", ".join(sorted(unknown_columns))
                    raise ValueError(
                        f"A medida {name} usa colunas não autorizadas em "
                        f"{table}: {names}"
                    )

    def context(self) -> str:
        definitions = []

        for metric in self._metrics.values():
            tables = self._table_context(metric)
            definitions.append(
                {
                    "key": metric.key,
                    "label": metric.label,
                    "description": metric.description,
                    "business_rule": metric.business_rule,
                    "tables": tables,
                    "allowed_dimensions": metric.allowed_dimensions,
                    "allowed_measures": metric.allowed_measures,
                    "measures": {
                        key: definition.model_dump(mode="json")
                        for key, definition in metric.measures.items()
                    },
                    "semantic_mappings": {
                        key: definition.model_dump(mode="json")
                        for key, definition in metric.semantic_mappings.items()
                    },
                    "synonyms": metric.synonyms,
                    "source_mapping": metric.source_mapping,
                }
            )

        return json.dumps(definitions, ensure_ascii=False, indent=2)

    def _table_context(
        self,
        metric: MetricDefinition,
    ) -> dict[str, dict[str, object]]:
        if metric.tables:
            return {
                table: definition.model_dump(mode="json")
                for table, definition in metric.tables.items()
            }

        return {
            table: {
                "description": metric.table_descriptions.get(table, ""),
                "columns": {
                    column: {
                        "description": "",
                        "example_value": None,
                    }
                    for column in columns
                },
            }
            for table, columns in metric.allowed_columns.items()
        }

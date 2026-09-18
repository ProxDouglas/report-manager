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

    def context(self) -> str:
        definitions = []

        for metric in self._metrics.values():
            definitions.append(
                {
                    "key": metric.key,
                    "label": metric.label,
                    "description": metric.description,
                    "business_rule": metric.business_rule,
                    "allowed_tables": metric.allowed_tables,
                    "known_columns": metric.known_columns,
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
                    "allowed_columns": metric.allowed_columns,
                    "table_descriptions": metric.table_descriptions,
                    "source_mapping": metric.source_mapping,
                }
            )

        return json.dumps(definitions, ensure_ascii=False, indent=2)

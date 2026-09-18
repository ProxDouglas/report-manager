from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.core.errors import DomainError
from app.core.sensitive import scrub_mapping


def _compare(value: Any, operator: str, expected: Any) -> bool:
    if operator == "eq":
        return value == expected
    if operator == "ne":
        return value != expected
    if operator == "contains":
        return str(expected).lower() in str(value).lower()
    if operator == "in":
        return value in expected if isinstance(expected, list) else False
    try:
        if operator == "gt":
            return value > expected
        if operator == "gte":
            return value >= expected
        if operator == "lt":
            return value < expected
        if operator == "lte":
            return value <= expected
    except TypeError:
        return False
    raise DomainError(f"Operador de filtro não suportado: {operator}.", "invalid_report_definition")


def apply_filters(
    rows: list[dict[str, Any]], filters: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    filtered = rows
    for item in filters:
        field = str(item.get("field", ""))
        operator = str(item.get("operator", "eq"))
        expected = item.get("value")
        filtered = [row for row in filtered if _compare(row.get(field), operator, expected)]
    return filtered


def _number(value: Any) -> float:
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError) as exc:
        raise DomainError(
            "Métrica numérica contém valor incompatível.", "invalid_report_data"
        ) from exc


def _aggregate(values: list[Any], operation: str) -> Any:
    if operation == "count":
        return len(values)
    if not values:
        return 0
    numeric = [_number(value) for value in values]
    if operation == "sum":
        return sum(numeric)
    if operation == "avg":
        return sum(numeric) / len(numeric)
    if operation == "min":
        return min(numeric)
    if operation == "max":
        return max(numeric)
    raise DomainError(
        f"Operação de métrica não suportada: {operation}.", "invalid_report_definition"
    )


def analyze_rows(
    rows: list[dict[str, Any]], definition: dict[str, Any], max_rows: int
) -> list[dict[str, Any]]:
    filtered = apply_filters(
        rows, [item for item in definition.get("filters", []) if isinstance(item, dict)]
    )
    metrics = [item for item in definition.get("metrics", []) if isinstance(item, dict)]
    group_by = [str(item) for item in definition.get("group_by", [])]
    fields = [str(item) for item in definition.get("fields", [])]
    if not metrics:
        selected_rows = [
            {field: row.get(field) for field in fields} if fields else row for row in filtered
        ]
        return selected_rows[:max_rows]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    if group_by:
        for row in filtered:
            groups[tuple(row.get(field) for field in group_by)].append(row)
    else:
        groups[tuple()] = filtered
    result: list[dict[str, Any]] = []
    for group_key, group_rows in groups.items():
        item = {field: value for field, value in zip(group_by, group_key, strict=False)}
        for metric in metrics:
            field = str(metric.get("field", ""))
            name = str(metric.get("name") or f"{metric.get('operation', 'count')}_{field}")
            operation = str(metric.get("operation", "count")).lower()
            item[name] = _aggregate(
                [row.get(field) for row in group_rows if row.get(field) is not None], operation
            )
        result.append(item)
    return result[:max_rows]


def protect_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [scrub_mapping(row) for row in rows]

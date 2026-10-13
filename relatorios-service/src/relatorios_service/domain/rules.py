import re

from ..schemas import (
    AnalysisComponent,
    MetricDefinition,
)
from .measures import ALLOCATION_HOURS, DEMAND_HOURS

GENERIC_METRIC = "generic_analysis"



def validate_plan(
    component: AnalysisComponent,
    metric: MetricDefinition,
) -> None:
    if metric.key != GENERIC_METRIC:
        raise ValueError(
            "Esta versão de análise composta aceita somente a métrica "
            "generic_analysis."
        )

    unknown_dimensions = set(component.dimensions) - set(
        metric.allowed_dimensions
    )

    if unknown_dimensions:
        names = ", ".join(sorted(unknown_dimensions))
        raise ValueError(f"Dimensões não autorizadas: {names}")

    if metric.allowed_measures:
        unknown_measures = set(component.measures) - set(
            metric.allowed_measures
        )

        if unknown_measures:
            names = ", ".join(sorted(unknown_measures))
            raise ValueError(f"Medidas não autorizadas: {names}")


def generic_required_tables(
    component: AnalysisComponent,
) -> list[str]:
    required_tables: list[str] = []
    dimensions = set(component.dimensions)

    if ALLOCATION_HOURS in component.measures:
        required_tables.append("distribuicao")

    if "employee_count" in component.measures:
        required_tables.append("funcionario")

    employee_dimensions = {
        "employee",
        "workplace",
        "branch",
        "cost_center",
        "subfunction",
    }

    if dimensions & employee_dimensions:
        required_tables.append("funcionario")

    if DEMAND_HOURS in component.measures:
        required_tables.append("distribuicao")
        restriction_by_dimension = {
            "branch": "restr_fil",
            "cost_center": "restr_ccusto",
            "workplace": "restr_posto",
            "subfunction": "restr_subf",
        }
        restriction_table = next(
            (
                restriction_by_dimension[dimension]
                for dimension in restriction_by_dimension
                if dimension in dimensions
            ),
            None,
        )

        if restriction_table:
            required_tables.append(restriction_table)
        else:
            required_tables.extend(["restr_emp", "restr_fil"])

    company_filters = {
        "company",
        "company_id",
        "company_name",
    }

    if dimensions & company_filters or company_filters.intersection(
        component.filters
    ):
        required_tables.append("empresa")

    return required_tables


def resolve_tables(
    component: AnalysisComponent,
    metric: MetricDefinition,
) -> list[str]:
    selected_tables = list(
        dict.fromkeys(
            [
                *component.tables,
                *generic_required_tables(component),
            ]
        )
    )

    if not selected_tables:
        raise ValueError(
            "O componente não informa tabelas nem possui medidas ou "
            "dimensões capazes de determinar as tabelas necessárias."
        )

    allowed_tables = set(metric.allowed_tables)
    unknown_tables = set(selected_tables) - allowed_tables

    if unknown_tables:
        names = ", ".join(sorted(unknown_tables))
        raise ValueError(f"Tabelas não autorizadas: {names}")

    return selected_tables


def validate_sql_semantics(
    sql: str,
    metric: MetricDefinition,
    measures: list[str],
) -> None:
    if metric.key != GENERIC_METRIC:
        return

    normalized = sql.lower()
    if ALLOCATION_HOURS in measures:
        hourly_columns = [f"hor_{hour:02d}" for hour in range(24)]
        missing_hours = [
            column
            for column in hourly_columns
            if column not in normalized
        ]

        if "sum" not in normalized or missing_hours:
            raise ValueError(
                "allocation_hours deve somar hor_00 até hor_23 de "
                "distribuicao."
            )

    if DEMAND_HOURS not in measures:
        return

    required_tokens = [
        "demand_schedule",
        "analysis_date",
        "restricao",
    ]
    missing_tokens = [
        token
        for token in required_tokens
        if token not in normalized
    ]

    if not any(
        table in normalized
        for table in (
            "restr_emp",
            "restr_fil",
            "restr_ccusto",
            "restr_posto",
            "restr_subf",
        )
    ):
        missing_tokens.append("uma tabela de restrição autorizada")

    if missing_tokens:
        details = ", ".join(missing_tokens)
        raise ValueError(
            "demand_hours deve retornar a restrição bruta e a data "
            f"para normalização. Elementos ausentes: {details}."
        )

    restriction_count = re.search(
        r"count\s*\(\s*distinct[^)]*restr_id",
        normalized,
    )

    if restriction_count:
        raise ValueError(
            "Não conte restr_id como demanda; retorne restricao bruta "
            "para o parser da aplicação."
        )

    restriction_sum = re.search(
        r"sum\s*\([^)]*restricao",
        normalized,
    )

    if restriction_sum:
        raise ValueError(
            "Não agregue restricao no SQL; retorne o valor bruto para "
            "o parser semanal."
        )


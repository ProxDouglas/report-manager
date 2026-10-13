import pandas as pd

from ..schemas import (
    AnalysisComponent,
    AnalysisPlan,
    CompositionMode,
)

ALLOCATION_HOURS = "allocation_hours"
DEMAND_HOURS = "demand_hours"
DEFICIT_HOURS = "deficit_hours"
COVERAGE_PERCENT = "coverage_percent"



DERIVED_MEASURES = (DEFICIT_HOURS, COVERAGE_PERCENT)


def derive_measures(
    dataframe: pd.DataFrame,
    measures: list[str],
) -> pd.DataFrame:
    required_columns = {ALLOCATION_HOURS, DEMAND_HOURS}

    if not required_columns.issubset(measures):
        return dataframe

    if not required_columns.issubset(dataframe.columns):
        return dataframe

    result = dataframe.copy()
    allocation = pd.to_numeric(
        result[ALLOCATION_HOURS],
        errors="coerce",
    )
    demand = pd.to_numeric(
        result[DEMAND_HOURS],
        errors="coerce",
    )

    if DEFICIT_HOURS not in result.columns:
        result[DEFICIT_HOURS] = demand - allocation

    if COVERAGE_PERCENT not in result.columns:
        non_zero_demand = demand.where(demand != 0)
        result[COVERAGE_PERCENT] = allocation.div(
            non_zero_demand
        ).mul(100)

    return result


def derive_composed_measures(
    dataframe: pd.DataFrame,
    plan: AnalysisPlan,
) -> pd.DataFrame:
    if plan.composition.mode is CompositionMode.SERIES:
        return dataframe

    measures = plan_measures(plan)
    return derive_measures(dataframe, measures)


def plan_measures(plan: AnalysisPlan) -> list[str]:
    measures: list[str] = []

    for component in plan.components:
        for measure in component.measures:
            if measure not in measures:
                measures.append(measure)

    return measures


def validate_result(
    dataframe: pd.DataFrame,
    component: AnalysisComponent,
) -> None:
    required_columns = set(component.measures) - set(
        DERIVED_MEASURES
    )

    if not required_columns:
        return

    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        names = ", ".join(sorted(missing_columns))
        raise ValueError(
            f"O componente {component.id} exige as colunas numéricas: "
            f"{names}. Ajuste os aliases retornados pelo SQL."
        )


def normalize_measure_columns(
    dataframe: pd.DataFrame,
    measures: list[str],
) -> pd.DataFrame:
    if not measures:
        return dataframe

    columns_by_name = {
        str(column).lower(): column
        for column in dataframe.columns
    }
    renames = {}

    for measure in measures:
        existing_column = columns_by_name.get(measure.lower())

        if existing_column and existing_column != measure:
            renames[existing_column] = measure

    if not renames:
        return dataframe

    return dataframe.rename(columns=renames)


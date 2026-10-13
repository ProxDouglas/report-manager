import pandas as pd

from relatorios_service.domain.composition import SERIES_COLUMN
from relatorios_service.domain.measures import (
    ALLOCATION_HOURS,
    DEMAND_HOURS,
    plan_measures,
)
from relatorios_service.schemas import (
    AnalysisPlan,
    AnalysisRequest,
    ChartAxis,
    ChartSeries,
    ChartSpec,
    ChartType,
    CompositionMode,
)


def override_chart_type(
    chart_spec: ChartSpec,
    chart_type: ChartType,
) -> ChartSpec:
    if chart_type is ChartType.AUTO:
        return chart_spec

    series = [
        item.model_copy(update={"chart_type": chart_type})
        for item in chart_spec.series
    ]

    return chart_spec.model_copy(
        update={
            "chart_type": chart_type,
            "series": series,
        }
    )



def default_chart_spec(
    dataframe: pd.DataFrame,
    plan: AnalysisPlan,
    chart_type: ChartType,
) -> ChartSpec:
    dimensions = []

    for component in plan.components:
        for dimension in component.dimensions:
            if dimension in dataframe.columns and dimension not in dimensions:
                dimensions.append(dimension)

    x_column = chart_x_dimension(dimensions)
    color_column = None

    if plan.composition.mode is CompositionMode.SERIES:
        if SERIES_COLUMN in dataframe.columns:
            color_column = SERIES_COLUMN
    elif len(dimensions) > 1:
        other_dimensions = [
            dimension for dimension in dimensions if dimension != x_column
        ]
        color_column = other_dimensions[0]

    measures = chart_measure_columns(plan, dataframe)
    series = []

    for measure in measures:
        series_type = chart_type

        if chart_type is ChartType.AUTO:
            series_type = default_series_type(measure, measures)

        series.append(
            ChartSeries(
                column=measure,
                chart_type=series_type,
                axis=ChartAxis.PRIMARY,
            )
        )

    return ChartSpec(
        chart_type=chart_type,
        x=x_column,
        color=color_column,
        series=series,
    )



def chart_x_dimension(
    dimensions: list[str],
) -> str | None:
    temporal_dimensions = {"date", "month", "year"}

    for dimension in dimensions:
        if dimension in temporal_dimensions:
            return dimension

    if dimensions:
        return dimensions[0]

    return None



def chart_measure_columns(
    plan: AnalysisPlan,
    dataframe: pd.DataFrame,
) -> list[str]:
    measures = plan_measures(plan)
    candidates = list(measures)

    selected = [
        column
        for column in candidates
        if column in dataframe.columns
        and pd.api.types.is_numeric_dtype(dataframe[column])
    ]

    if selected:
        return list(dict.fromkeys(selected))

    return list(
        dataframe.select_dtypes(include="number").columns
    )



def default_series_type(
    measure: str,
    measures: list[str],
) -> ChartType:
    if {
        ALLOCATION_HOURS,
        DEMAND_HOURS,
    }.issubset(measures):
        if measure == ALLOCATION_HOURS:
            return ChartType.BAR

        if measure == DEMAND_HOURS:
            return ChartType.LINE

    return ChartType.AUTO



def plan_chart_spec(
    request: AnalysisRequest,
    plan: AnalysisPlan,
    dataframe: pd.DataFrame,
) -> ChartSpec:
    requested_type = request.chart_type

    if plan.chart is not None:
        chart_spec = plan.chart

        if requested_type is not None:
            chart_spec = override_chart_type(chart_spec, requested_type)

        return chart_spec

    chart_type = requested_type or ChartType.AUTO
    return default_chart_spec(dataframe, plan, chart_type)

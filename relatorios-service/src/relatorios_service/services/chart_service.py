from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..schemas import (
    ChartAxis,
    ChartSeries,
    ChartSpec,
    ChartType,
)
from relatorios_service.domain.composition import COMPONENT_COLUMN


class ChartBuilder:
    def build(
        self,
        dataframe: pd.DataFrame,
        chart_spec: ChartSpec,
    ) -> dict | None:
        if dataframe.empty or chart_spec.chart_type is ChartType.TABLE:
            return None

        x_column = chart_spec.x or self._first_dimension(dataframe)
        if x_column is None or x_column not in dataframe.columns:
            return None

        series = list(chart_spec.series)

        if not series:
            series = self._default_series(dataframe, chart_spec.chart_type)

        series = [
            self._apply_chart_type(item, chart_spec.chart_type)
            for item in series
            if item.column in dataframe.columns
            and item.chart_type is not ChartType.TABLE
        ]

        if not series:
            return None

        if any(item.chart_type is ChartType.PIE for item in series):
            return self._build_pie(dataframe, chart_spec, series, x_column)

        has_secondary_axis = any(
            item.axis is ChartAxis.SECONDARY for item in series
        )
        figure = make_subplots(
            specs=[[{"secondary_y": has_secondary_axis}]],
        )

        for item in series:
            chart_type = self._resolve_series_type(item, x_column)

            for group_label, group in self._series_groups(
                dataframe,
                chart_spec,
                item,
            ):
                trace = self._trace(
                    group,
                    x_column,
                    item,
                    chart_type,
                    self._trace_name(item, group_label),
                )
                figure.add_trace(
                    trace,
                    secondary_y=item.axis is ChartAxis.SECONDARY,
                )

        if not figure.data:
            return None

        if chart_spec.title:
            figure.update_layout(title=chart_spec.title)

        figure.update_layout(
            barmode="group",
            legend_title_text=chart_spec.color or "",
        )

        return json.loads(figure.to_json())

    def _build_pie(
        self,
        dataframe: pd.DataFrame,
        chart_spec: ChartSpec,
        series: list[ChartSeries],
        x_column: str,
    ) -> dict | None:
        if any(item.chart_type is not ChartType.PIE for item in series):
            raise ValueError(
                "Gráficos de pizza não podem ser combinados com outros tipos "
                "de série no mesmo gráfico."
            )

        pies = [
            go.Pie(
                labels=group[x_column],
                values=pd.to_numeric(group[item.column], errors="coerce"),
                name=self._trace_name(item, group_label),
            )
            for item in series
            for group_label, group in self._series_groups(
                dataframe,
                chart_spec,
                item,
            )
        ]

        if not pies:
            return None

        figure = make_subplots(
            rows=1,
            cols=len(pies),
            specs=[[{"type": "domain"} for _ in pies]],
            subplot_titles=[pie.name for pie in pies],
        )

        for column, pie in enumerate(pies, start=1):
            figure.add_trace(pie, row=1, col=column)

        if chart_spec.title:
            figure.update_layout(title=chart_spec.title)

        return json.loads(figure.to_json())

    def _series_groups(
        self,
        dataframe: pd.DataFrame,
        chart_spec: ChartSpec,
        series: ChartSeries,
    ) -> list[tuple[str | None, pd.DataFrame]]:
        color_column = None if series.component_id else chart_spec.color

        return self._group_data(
            self._series_dataframe(dataframe, series),
            color_column,
        )

    def _series_dataframe(
        self,
        dataframe: pd.DataFrame,
        series: ChartSeries,
    ) -> pd.DataFrame:
        if not series.component_id:
            return dataframe

        component_column = COMPONENT_COLUMN

        if component_column not in dataframe.columns:
            return dataframe

        return dataframe[
            dataframe[component_column].astype(str) == series.component_id
        ]

    def _apply_chart_type(
        self,
        series: ChartSeries,
        chart_type: ChartType,
    ) -> ChartSeries:
        if (
            chart_type is not ChartType.AUTO
            and series.chart_type is ChartType.AUTO
        ):
            return series.model_copy(update={"chart_type": chart_type})

        return series

    def _default_series(
        self,
        dataframe: pd.DataFrame,
        requested_type: ChartType,
    ) -> list[ChartSeries]:
        numeric_columns = list(
            dataframe.select_dtypes(include="number").columns
        )

        return [
            ChartSeries(column=column, chart_type=requested_type)
            for column in numeric_columns
        ]

    def _group_data(
        self,
        dataframe: pd.DataFrame,
        color_column: str | None,
    ) -> list[tuple[str | None, pd.DataFrame]]:
        if dataframe.empty:
            return []

        if not color_column or color_column not in dataframe.columns:
            return [(None, dataframe)]

        return [
            (str(label), group)
            for label, group in dataframe.groupby(
                color_column,
                dropna=False,
                sort=False,
            )
        ]

    def _resolve_series_type(
        self,
        series: ChartSeries,
        x_column: str,
    ) -> ChartType:
        if series.chart_type is not ChartType.AUTO:
            return series.chart_type

        temporal_names = ("date", "month", "year", "data", "mes", "ano")

        if any(name in x_column.lower() for name in temporal_names):
            return ChartType.LINE

        return ChartType.BAR

    def _trace(
        self,
        dataframe: pd.DataFrame,
        x_column: str,
        series: ChartSeries,
        chart_type: ChartType,
        trace_name: str,
    ) -> go.BaseTraceType:
        values = pd.to_numeric(dataframe[series.column], errors="coerce")

        if chart_type is ChartType.LINE:
            return go.Scatter(
                x=dataframe[x_column],
                y=values,
                mode="lines+markers",
                name=trace_name,
            )

        if chart_type is ChartType.SCATTER:
            return go.Scatter(
                x=dataframe[x_column],
                y=values,
                mode="markers",
                name=trace_name,
            )

        # AUTO já foi resolvido e PIE é tratado em _build_pie.
        return go.Bar(
            x=dataframe[x_column],
            y=values,
            name=trace_name,
        )

    def _trace_name(
        self,
        series: ChartSeries,
        group_label: str | None,
    ) -> str:
        label = series.label or series.component_id or series.column

        if group_label is None:
            return label

        return f"{label} - {group_label}"

    def _first_dimension(self, dataframe: pd.DataFrame) -> str | None:
        numeric_columns = set(
            dataframe.select_dtypes(include="number").columns
        )

        for column in dataframe.columns:
            if column not in numeric_columns:
                return column

        return None

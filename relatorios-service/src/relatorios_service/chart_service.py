from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from relatorios_service.schemas import (
    ChartAxis,
    ChartSeries,
    ChartSpec,
    ChartType,
)


class ChartBuilder:
    def build(
        self,
        dataframe: pd.DataFrame,
        requested_chart: ChartType | ChartSpec,
        measure_columns: list[str] | None = None,
    ) -> dict | None:
        if isinstance(requested_chart, ChartSpec):
            return self._build_spec(dataframe, requested_chart)

        return self._build_legacy(
            dataframe,
            requested_chart,
            measure_columns,
        )

    def _build_spec(
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

        has_secondary_axis = any(
            item.axis is ChartAxis.SECONDARY for item in series
        )
        figure = make_subplots(
            specs=[[{"secondary_y": has_secondary_axis}]],
        )

        for item in series:
            series_dataframe = self._series_dataframe(dataframe, item)
            color_column = chart_spec.color

            if item.component_id:
                color_column = None

            grouped_data = self._group_data(
                series_dataframe,
                color_column,
            )
            chart_type = self._resolve_series_type(
                dataframe,
                item,
                x_column,
            )

            for group_label, group in grouped_data:
                trace_name = self._trace_name(item, group_label)
                trace = self._trace(
                    group,
                    x_column,
                    item,
                    chart_type,
                    trace_name,
                )

                if trace is None:
                    continue

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

    def _series_dataframe(
        self,
        dataframe: pd.DataFrame,
        series: ChartSeries,
    ) -> pd.DataFrame:
        if not series.component_id:
            return dataframe

        component_column = "analysis_component"

        if component_column not in dataframe.columns:
            return dataframe.iloc[0:0]

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

    def _build_legacy(
        self,
        dataframe: pd.DataFrame,
        requested_type: ChartType,
        measure_columns: list[str] | None,
    ) -> dict | None:
        if dataframe.empty or requested_type is ChartType.TABLE:
            return None

        numeric_columns = list(
            dataframe.select_dtypes(include="number").columns
        )
        dimension_columns = [
            column
            for column in dataframe.columns
            if column not in numeric_columns
        ]

        if not numeric_columns or not dimension_columns:
            return None

        numeric_columns = self._selected_measures(
            numeric_columns,
            measure_columns,
        )

        chart_type = self._resolve_type(
            dataframe,
            requested_type,
            dimension_columns,
        )
        dimension = dimension_columns[0]

        if chart_type is ChartType.LINE:
            figure = px.line(dataframe, x=dimension, y=numeric_columns)
        elif chart_type is ChartType.PIE:
            figure = px.pie(
                dataframe,
                names=dimension,
                values=numeric_columns[0],
            )
        elif chart_type is ChartType.SCATTER:
            if len(numeric_columns) < 2:
                figure = px.bar(
                    dataframe,
                    x=dimension,
                    y=numeric_columns[0],
                )
            else:
                figure = px.scatter(
                    dataframe,
                    x=numeric_columns[0],
                    y=numeric_columns[1],
                )
        else:
            figure = px.bar(
                dataframe,
                x=dimension,
                y=numeric_columns,
                barmode="group",
            )

        return json.loads(figure.to_json())

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
        dataframe: pd.DataFrame,
        series: ChartSeries,
        x_column: str,
    ) -> ChartType:
        if series.chart_type is not ChartType.AUTO:
            return series.chart_type

        return self._resolve_type(
            dataframe,
            ChartType.AUTO,
            [x_column],
        )

    def _trace(
        self,
        dataframe: pd.DataFrame,
        x_column: str,
        series: ChartSeries,
        chart_type: ChartType,
        trace_name: str,
    ) -> go.BaseTraceType | None:
        values = pd.to_numeric(dataframe[series.column], errors="coerce")

        if chart_type is ChartType.LINE:
            return go.Scatter(
                x=dataframe[x_column],
                y=values,
                mode="lines+markers",
                name=trace_name,
            )

        if chart_type is ChartType.BAR:
            return go.Bar(
                x=dataframe[x_column],
                y=values,
                name=trace_name,
            )

        if chart_type is ChartType.SCATTER:
            return go.Scatter(
                x=dataframe[x_column],
                y=values,
                mode="markers",
                name=trace_name,
            )

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

    def _selected_measures(
        self,
        numeric_columns: list[str],
        measure_columns: list[str] | None,
    ) -> list[str]:
        if not measure_columns:
            return numeric_columns

        selected = [
            column
            for column in measure_columns
            if column in numeric_columns
        ]

        if selected:
            return selected

        return numeric_columns

    def _resolve_type(
        self,
        dataframe: pd.DataFrame,
        requested_type: ChartType,
        dimensions: list[str],
    ) -> ChartType:
        if requested_type is not ChartType.AUTO:
            return requested_type

        first_dimension = dimensions[0].lower()
        temporal_names = ("date", "month", "year", "data", "mes", "ano")

        if any(name in first_dimension for name in temporal_names):
            return ChartType.LINE

        return ChartType.BAR

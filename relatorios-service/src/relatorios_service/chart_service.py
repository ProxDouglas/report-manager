import json

import pandas as pd
import plotly.express as px

from relatorios_service.schemas import ChartType


class ChartBuilder:
    def build(
        self,
        dataframe: pd.DataFrame,
        requested_type: ChartType,
        measure_columns: list[str] | None = None,
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

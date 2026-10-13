import base64
import unittest

import numpy as np
import pandas as pd

from relatorios_service.schemas import (
    ChartAxis,
    ChartSeries,
    ChartSpec,
    ChartType,
)
from relatorios_service.services.chart_service import ChartBuilder


def numeric_values(trace: dict, key: str = "y") -> list:
    # O Plotly pode serializar arrays numéricos como {"dtype", "bdata"} (base64).
    value = trace[key]
    if isinstance(value, dict):
        raw = base64.b64decode(value["bdata"])
        return np.frombuffer(raw, dtype=value["dtype"]).tolist()
    return list(value)


class ChartBuilderSpecTests(unittest.TestCase):
    def setUp(self):
        self.builder = ChartBuilder()
        self.dataframe = pd.DataFrame(
            {
                "month": ["2026-01", "2026-02"],
                "allocation_hours": [10.0, 20.0],
                "demand_hours": [12.0, 18.0],
            }
        )

    def test_empty_dataframe_returns_none(self):
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            x="month",
            series=[ChartSeries(column="allocation_hours")],
        )

        result = self.builder.build(
            pd.DataFrame(columns=["month", "allocation_hours"]),
            spec,
        )

        self.assertIsNone(result)

    def test_table_type_returns_none(self):
        spec = ChartSpec(chart_type=ChartType.TABLE, x="month")

        self.assertIsNone(self.builder.build(self.dataframe, spec))

    def test_missing_x_column_returns_none(self):
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            x="inexistente",
            series=[ChartSeries(column="allocation_hours")],
        )

        self.assertIsNone(self.builder.build(self.dataframe, spec))

    def test_series_missing_from_dataframe_returns_none(self):
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            x="month",
            series=[ChartSeries(column="inexistente")],
        )

        self.assertIsNone(self.builder.build(self.dataframe, spec))

    def test_line_type_renders_scatter_with_lines_and_markers(self):
        spec = ChartSpec(
            chart_type=ChartType.LINE,
            x="month",
            series=[ChartSeries(column="allocation_hours")],
        )

        trace = self.builder.build(self.dataframe, spec)["data"][0]

        self.assertEqual(trace["type"], "scatter")
        self.assertEqual(trace["mode"], "lines+markers")
        self.assertEqual(trace["name"], "allocation_hours")
        self.assertEqual(numeric_values(trace), [10.0, 20.0])

    def test_bar_type_renders_bar_trace(self):
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            x="month",
            series=[ChartSeries(column="allocation_hours")],
        )

        trace = self.builder.build(self.dataframe, spec)["data"][0]

        self.assertEqual(trace["type"], "bar")
        self.assertEqual(numeric_values(trace), [10.0, 20.0])

    def test_scatter_type_renders_markers_only(self):
        spec = ChartSpec(
            chart_type=ChartType.SCATTER,
            x="month",
            series=[ChartSeries(column="allocation_hours")],
        )

        trace = self.builder.build(self.dataframe, spec)["data"][0]

        self.assertEqual(trace["type"], "scatter")
        self.assertEqual(trace["mode"], "markers")

    def test_auto_type_resolves_temporal_x_to_line(self):
        spec = ChartSpec(
            chart_type=ChartType.AUTO,
            x="month",
            series=[ChartSeries(column="allocation_hours")],
        )

        trace = self.builder.build(self.dataframe, spec)["data"][0]

        self.assertEqual(trace["type"], "scatter")
        self.assertEqual(trace["mode"], "lines+markers")

    def test_auto_type_resolves_non_temporal_x_to_bar(self):
        dataframe = pd.DataFrame(
            {
                "workplace": ["P1", "P2"],
                "allocation_hours": [1.0, 2.0],
            }
        )
        spec = ChartSpec(
            chart_type=ChartType.AUTO,
            x="workplace",
            series=[ChartSeries(column="allocation_hours")],
        )

        trace = self.builder.build(dataframe, spec)["data"][0]

        self.assertEqual(trace["type"], "bar")

    def test_component_series_uses_only_rows_of_that_component(self):
        dataframe = pd.DataFrame(
            {
                "month": ["2026-01", "2026-01"],
                "analysis_component": ["c1", "c2"],
                "allocation_hours": [1.0, 5.0],
            }
        )
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            x="month",
            series=[
                ChartSeries(
                    column="allocation_hours",
                    component_id="c2",
                    label="Posto B",
                ),
            ],
        )

        trace = self.builder.build(dataframe, spec)["data"][0]

        self.assertEqual(numeric_values(trace), [5.0])
        self.assertEqual(trace["name"], "Posto B")

    def test_component_series_uses_untagged_single_component_dataframe(self):
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            x="month",
            series=[
                ChartSeries(
                    column="allocation_hours",
                    chart_type=ChartType.BAR,
                    label="Horas alocadas",
                    component_id="component_1",
                ),
                ChartSeries(
                    column="demand_hours",
                    chart_type=ChartType.BAR,
                    label="Horas de demanda",
                    component_id="component_1",
                ),
            ],
        )

        figure = self.builder.build(self.dataframe, spec)

        self.assertEqual(
            [trace["name"] for trace in figure["data"]],
            ["Horas alocadas", "Horas de demanda"],
        )
        self.assertEqual(
            numeric_values(figure["data"][0]),
            [10.0, 20.0],
        )
        self.assertEqual(
            numeric_values(figure["data"][1]),
            [12.0, 18.0],
        )

    def test_color_column_creates_one_trace_per_group(self):
        dataframe = pd.DataFrame(
            {
                "month": ["2026-01", "2026-02", "2026-01", "2026-02"],
                "branch": ["Norte", "Norte", "Sul", "Sul"],
                "allocation_hours": [1.0, 2.0, 3.0, 4.0],
            }
        )
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            x="month",
            color="branch",
            series=[ChartSeries(column="allocation_hours")],
        )

        figure = self.builder.build(dataframe, spec)

        self.assertEqual(
            [trace["name"] for trace in figure["data"]],
            ["allocation_hours - Norte", "allocation_hours - Sul"],
        )

    def test_secondary_axis_series_are_drawn_on_y2(self):
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            x="month",
            series=[
                ChartSeries(column="allocation_hours"),
                ChartSeries(
                    column="demand_hours",
                    chart_type=ChartType.LINE,
                    axis=ChartAxis.SECONDARY,
                ),
            ],
        )

        traces = self.builder.build(self.dataframe, spec)["data"]

        self.assertEqual(traces[0].get("yaxis", "y"), "y")
        self.assertEqual(traces[1]["yaxis"], "y2")

    def test_default_series_uses_all_numeric_columns_when_none_are_given(self):
        spec = ChartSpec(chart_type=ChartType.BAR, x="month")

        figure = self.builder.build(self.dataframe, spec)

        self.assertEqual(
            [trace["name"] for trace in figure["data"]],
            ["allocation_hours", "demand_hours"],
        )

    def test_title_is_applied_to_layout(self):
        spec = ChartSpec(
            chart_type=ChartType.BAR,
            x="month",
            title="Alocação",
            series=[ChartSeries(column="allocation_hours")],
        )

        figure = self.builder.build(self.dataframe, spec)

        self.assertEqual(figure["layout"]["title"]["text"], "Alocação")

    def test_pie_type_renders_pie_trace_with_labels_and_values(self):
        spec = ChartSpec(
            chart_type=ChartType.PIE,
            x="month",
            series=[ChartSeries(column="allocation_hours")],
        )

        trace = self.builder.build(self.dataframe, spec)["data"][0]

        self.assertEqual(trace["type"], "pie")
        self.assertEqual(trace["labels"], ["2026-01", "2026-02"])
        self.assertEqual(numeric_values(trace, "values"), [10.0, 20.0])

    def test_pie_series_are_drawn_side_by_side(self):
        spec = ChartSpec(
            chart_type=ChartType.PIE,
            x="month",
            series=[
                ChartSeries(column="allocation_hours"),
                ChartSeries(column="demand_hours"),
            ],
        )

        traces = self.builder.build(self.dataframe, spec)["data"]

        self.assertEqual([trace["type"] for trace in traces], ["pie", "pie"])
        self.assertEqual(
            [trace["name"] for trace in traces],
            ["allocation_hours", "demand_hours"],
        )
        self.assertNotEqual(
            traces[0]["domain"]["x"],
            traces[1]["domain"]["x"],
        )

    def test_pie_color_creates_one_pie_per_group(self):
        dataframe = pd.DataFrame(
            {
                "month": ["2026-01", "2026-02", "2026-01", "2026-02"],
                "branch": ["Norte", "Norte", "Sul", "Sul"],
                "allocation_hours": [1.0, 2.0, 3.0, 4.0],
            }
        )
        spec = ChartSpec(
            chart_type=ChartType.PIE,
            x="month",
            color="branch",
            series=[ChartSeries(column="allocation_hours")],
        )

        traces = self.builder.build(dataframe, spec)["data"]

        self.assertEqual([trace["type"] for trace in traces], ["pie", "pie"])
        self.assertEqual(
            [trace["name"] for trace in traces],
            ["allocation_hours - Norte", "allocation_hours - Sul"],
        )

    def test_pie_cannot_be_mixed_with_other_series_types(self):
        spec = ChartSpec(
            chart_type=ChartType.AUTO,
            x="month",
            series=[
                ChartSeries(
                    column="allocation_hours",
                    chart_type=ChartType.PIE,
                ),
                ChartSeries(
                    column="demand_hours",
                    chart_type=ChartType.BAR,
                ),
            ],
        )

        with self.assertRaisesRegex(ValueError, "pizza"):
            self.builder.build(self.dataframe, spec)


if __name__ == "__main__":
    unittest.main()

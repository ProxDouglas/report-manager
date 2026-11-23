import unittest
from unittest.mock import patch

import pandas as pd
from pydantic import ValidationError

from relatorios_service.pipeline_schemas import PipelineMode, PipelinePlan
from relatorios_service.services.dataset_profiler import ValueFormatProfiler
from relatorios_service.services.pipeline_executor import PipelineExecutionError, PipelineExecutor


class PipelineAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.executor = PipelineExecutor(max_rows=10)

    def plan(self, steps, **parameters):
        return PipelinePlan.model_validate({
            "steps": [dict(id=f"step_{i}", reason="Objetivo solicitado.", **step)
                      for i, step in enumerate(steps)],
            "outputs": [f"step_{len(steps) - 1}"], **parameters,
        })

    def run_plan(self, frame, steps):
        plan = self.plan(steps)
        frames = {"source": frame}
        self.executor.validate_plan(plan, frames, PipelineMode.SEPARATE)
        for step in plan.steps:
            frames[step.id] = self.executor.execute(step, frames)
        return frames[plan.outputs[0]]

    def test_combined_types_are_split_filtered_and_counted(self):
        frame = pd.DataFrame({"Pokemon": ["A", "B", "C", "D"],
                              "Type": ["Grass, Ice", "Normal, Ice", "Normal", "Psychic"]})
        result = self.run_plan(frame, [
            dict(operation="split_explode", input="source", column="Type", separator=","),
            dict(operation="filter", input="step_0", conditions=[
                dict(column="Type", operator="in", values=["Ice", "Normal"]),
            ]),
            dict(operation="aggregate", input="step_1", group_by=["Type"], metrics=[
                dict(function="size", alias="count"),
            ]),
        ])
        self.assertEqual(dict(zip(result.Type, result['count'])), {"Ice": 2, "Normal": 2})
        self.assertEqual(len(frame), 4)

    def test_percentage_boundaries_all_scales_and_arbitrary_ranges(self):
        cases = [
            ("percent", [0, 25, 99, 100, None], [0, 25, 100]),
            ("fraction", [0, .25, .99, 1, None], [0, 25, 100]),
            ("percent_text", ["0%", "25,0 %", "99%", "100%", None], [0, 25, 100]),
            ("number", [-20, -5, 39, 40, None], [-20, -5, 40]),
        ]
        for scale, values, edges in cases:
            with self.subTest(scale=scale):
                result = self.run_plan(pd.DataFrame({"value": values}), [
                    dict(operation="bucket", input="source", column="value", output_column="range",
                         scale=scale, edges=edges, labels=["low", "high"]),
                    dict(operation="aggregate", input="step_0", group_by=["range"], metrics=[
                        dict(function="size", alias="count"),
                    ]),
                ])
                self.assertEqual(result['count'].tolist(), [1, 3, 1])
                self.assertTrue(pd.isna(result.range.iloc[-1]))

    def test_invalid_bucket_values_fail_instead_of_becoming_null(self):
        for values in [["invalid"], [101], [-1], [float("inf")], [True]]:
            with self.subTest(values=values), self.assertRaises(PipelineExecutionError):
                self.run_plan(pd.DataFrame({"value": values}), [
                    dict(operation="bucket", input="source", column="value", output_column="range",
                         scale="percent", edges=[0, 100], labels=["all"]),
                ])

    def test_aggregations_and_null_groups(self):
        metrics = [dict(function=fn, column="value", alias=fn)
                   for fn in ["count", "nunique", "sum", "mean", "median", "min", "max"]]
        metrics.append(dict(function="size", alias="rows"))
        result = self.run_plan(pd.DataFrame({"group": ["A", "A", None], "value": [2., 4., None]}), [
            dict(operation="aggregate", input="source", group_by=["group"], metrics=metrics),
        ])
        self.assertEqual(result.iloc[0].tolist(), ["A", 2, 2, 6, 3, 3, 2, 4, 2])
        self.assertTrue(pd.isna(result['sum'].iloc[1]))
        self.assertEqual(result['rows'].iloc[1], 1)
        global_result = self.run_plan(pd.DataFrame({"value": [2., 4., None]}), [
            dict(operation="aggregate", input="source", metrics=metrics),
        ])
        self.assertEqual(global_result['rows'].tolist(), [3])
        self.assertEqual(global_result['sum'].tolist(), [6])

    def test_filters_all_any_and_null_semantics(self):
        frame = pd.DataFrame({"x": pd.Series([1, 2, None], dtype="Int64")})
        for match, expected in [("all", []), ("any", [2, pd.NA])]:
            result = self.run_plan(frame, [dict(operation="filter", input="source", match=match, conditions=[
                dict(column="x", operator="gt", values=[1]), dict(column="x", operator="is_null"),
            ])])
            self.assertEqual(result.x.tolist(), expected)
        result = self.run_plan(frame, [dict(operation="filter", input="source", conditions=[
            dict(column="x", operator="not_in", values=[1]),
        ])])
        self.assertEqual(result.x.tolist(), [2])

    def test_expansion_is_bounded_before_materializing_lists(self):
        plan = self.plan([dict(operation="split_explode", input="source", column="x", separator=".")])
        with patch.object(pd.DataFrame, "explode") as explode:
            with self.assertRaises(PipelineExecutionError):
                self.executor.execute(plan.steps[0], {"source": pd.DataFrame({"x": ["." * 20]})})
            explode.assert_not_called()

    def test_numeric_aggregation_requires_explicit_cast(self):
        with self.assertRaises(PipelineExecutionError):
            self.run_plan(pd.DataFrame({"value": ["2", "4"]}), [
                dict(operation="aggregate", input="source", metrics=[dict(function="sum", column="value", alias="total")]),
            ])
        result = self.run_plan(pd.DataFrame({"value": ["25,5 %", "50,0%"]}), [
            dict(operation="cast", input="source", columns=["value"], target="number",
                 number_format="brazilian", strip_percent=True),
            dict(operation="aggregate", input="step_0", metrics=[dict(function="mean", column="value", alias="average")]),
        ])
        self.assertEqual(result.average.tolist(), [37.75])

    def test_invalid_ranges_and_parameters_are_rejected(self):
        for changes in [dict(edges=[0, 0, 100]), dict(edges=[0, float('inf')]),
                        dict(labels=["same", "same"], edges=[0, 50, 100]), dict(edges=[1, 100]),
                        dict(labels=["one", "two"])]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.plan([dict(operation="bucket", input="source", column="x", output_column="range",
                               **(dict(scale="percent", edges=[0, 100], labels=["all"]) | changes))])

    def test_schema_changes_and_planned_charts_are_validated(self):
        steps = [dict(operation="aggregate", input="source", group_by=["x"],
                      metrics=[dict(function="size", alias="count")])]
        for chart in [dict(reference="source", x="x", y="count"),
                      dict(reference="step_0", x="missing", y="count")]:
            with self.subTest(chart=chart), self.assertRaises(ValueError):
                self.executor.validate_plan(self.plan(steps, charts=[chart]),
                                            {"source": pd.DataFrame({"x": [1]})}, PipelineMode.SEPARATE)
        with self.assertRaises(ValueError):
            plan = self.plan([dict(operation="bucket", input="source", column="x", output_column="x",
                                   edges=[0, 10], labels=["all"])])
            self.executor.validate_plan(plan, {"source": pd.DataFrame({"x": [1]})}, PipelineMode.SEPARATE)

    def test_masks_scan_every_value_without_reproducing_cells(self):
        values = pd.Series(["SECRET-123", "123.45 %", "12", "AB12", "987.65 %", "Unicodeá_９"])
        masks, other = ValueFormatProfiler().summarize(values)
        self.assertEqual(masks["000.00 %"], 2)
        self.assertIn("AAAAAA-000", masks)
        self.assertIn("AA00", masks)
        self.assertNotIn("SECRET", str(masks))
        self.assertEqual(sum(masks.values()) + other, len(values))
        masks, other = ValueFormatProfiler().summarize(pd.Series(["x" * i for i in range(1, 100)]))
        self.assertLessEqual(len(masks), 10)
        self.assertLessEqual(max(map(len, masks)), 81)
        self.assertEqual(sum(masks.values()) + other, 99)

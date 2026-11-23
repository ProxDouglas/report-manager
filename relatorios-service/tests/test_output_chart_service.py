from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import pandas as pd
from fastapi import HTTPException

from relatorios_service.controllers.pipelines_controller import generate_output_chart
from relatorios_service.pipeline_schemas import PipelineStatus
from relatorios_service.schemas import ChartType
from relatorios_service.services.chart_service import ChartBuilder
from relatorios_service.services.output_chart_service import (
    OutputChartService, OutputChartValidationError,
)


class OutputChartServiceTests(unittest.TestCase):
    def setUp(self):
        self.state = SimpleNamespace(
            status=PipelineStatus.COMPLETED,
            outputs=[SimpleNamespace(reference="result", dataset_id="dataset", columns=["name", "count", "other"])],
            plan=SimpleNamespace(charts=[SimpleNamespace(
                reference="result", x="name", y="count", chart_type=ChartType.BAR,
            )]),
        )
        self.pipelines = Mock()
        self.pipelines.get.return_value = self.state
        self.profiler = Mock()
        self.profiler.load.return_value = (pd.DataFrame({"name": ["A"], "count": ["2"], "other": ["3"]}), ",")
        self.builder = Mock(wraps=ChartBuilder())
        self.service = OutputChartService(self.pipelines, self.profiler, self.builder)
        self.container = SimpleNamespace(output_chart_service=self.service)

    def test_uses_planned_chart_and_explicit_overrides(self):
        html = self.service.generate("pipeline", "result")
        self.assertIn("<html>", html)
        frame, spec = self.builder.build.call_args.args
        self.assertEqual(frame["count"].iloc[0], 2)
        self.assertEqual(spec.series[0].column, "count")
        self.service.generate("pipeline", "result", y="other", chart_type=ChartType.LINE)
        _, spec = self.builder.build.call_args.args
        self.assertEqual(spec.series[0].column, "other")
        self.assertEqual(spec.chart_type, ChartType.LINE)

    def test_defaults_to_bar_without_a_planned_chart(self):
        self.state.plan.charts = []
        self.service.generate("pipeline", "result", x="name", y="count")
        self.assertEqual(self.builder.build.call_args.args[1].chart_type, ChartType.BAR)

    def test_rejects_invalid_numeric_series(self):
        for values in (["invalid"], [None], []):
            with self.subTest(values=values):
                self.profiler.load.return_value = (pd.DataFrame({"name": ["A"] * len(values), "count": values}), ",")
                with self.assertRaises(OutputChartValidationError):
                    self.service.generate("pipeline", "result")
        self.builder.build.assert_not_called()

    def test_controller_preserves_conflict_not_found_and_validation_responses(self):
        self.state.status = PipelineStatus.READY
        with self.assertRaises(HTTPException) as caught:
            generate_output_chart("pipeline", "result", container=self.container)
        self.assertEqual(caught.exception.status_code, 409)
        self.state.status = PipelineStatus.COMPLETED
        for reference, parameters, status in [
            ("missing", {}, 404),
            ("result", {"x": "missing"}, 422),
            ("result", {"chart_type": ChartType.TABLE}, 422),
        ]:
            with self.subTest(reference=reference, parameters=parameters):
                with self.assertRaises(HTTPException) as caught:
                    generate_output_chart("pipeline", reference, container=self.container, **parameters)
                self.assertEqual(caught.exception.status_code, status)
        self.profiler.load.side_effect = FileNotFoundError("internal path")
        with self.assertRaises(HTTPException) as caught:
            generate_output_chart("pipeline", "result", container=self.container)
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(caught.exception.detail, "Dataset não encontrado ou expirado.")

import unittest

import pandas as pd

from relatorios_service.pipeline_schemas import NumberFormat, PipelineMode, PipelinePlan
from relatorios_service.services.dataset_profiler import DatasetProfiler
from relatorios_service.services.file_reader import FileReader
from relatorios_service.services.measurement_parser import MeasurementParser
from relatorios_service.services.pipeline_executor import PipelineExecutionError, PipelineExecutor


class MeasurementTests(unittest.TestCase):
    def plan(self, **parameters):
        return PipelinePlan.model_validate(dict(steps=[dict(
            id="extracted", input="source", reason="Separar componentes sem converter unidades.",
            operation="extract_measurements", column="Weight", pairs=2, **parameters,
        )], outputs=["extracted"]))

    def test_preserves_original_and_extracts_numeric_pairs_and_nulls(self):
        frame = pd.DataFrame({"Weight": ["135.5 kg (298.7 lbs)", "2 lb", None]})
        executor = PipelineExecutor()
        plan = self.plan()
        executor.validate_plan(plan, {"source": frame}, PipelineMode.SEPARATE)
        result = executor.execute(plan.steps[0], {"source": frame})
        self.assertEqual(result.Weight.tolist(), frame.Weight.tolist())
        self.assertEqual(result.Weight_value_1.iloc[0], 135.5)
        self.assertEqual(result.Weight_value_2.iloc[0], 298.7)
        self.assertEqual(result.Weight_unit_1.iloc[:2].tolist(), ["kg", "lb"])
        self.assertEqual(result.Weight_unit_2.iloc[0], "lbs")
        self.assertTrue(pd.isna(result.Weight_value_2.iloc[1]))
        self.assertTrue(result.iloc[2, 1:].isna().all())
        self.assertEqual(list(frame.columns), ["Weight"])
        self.assertEqual(str(result.Weight_value_1.dtype), "Float64")

    def test_units_and_compounds_are_preserved_without_conversion(self):
        parser = MeasurementParser()
        for text, value, unit in [
            ("1.75 m", 1.75, "m"), ("500 mL", 500, "mL"),
            ("20 unidades/m³", 20, "unidades/m³"), ("800 kg/m^3", 800, "kg/m^3"),
            ("3 kg/m3", 3, "kg/m3"), ("-2 °C", -2, "°C"), ("1e3 L", 1000, "L"),
        ]:
            with self.subTest(text=text):
                self.assertEqual(parser.parse(text), [(value, unit)])
        self.assertEqual(parser.parse("1.234,5 kg", NumberFormat.BRAZILIAN), [(1234.5, "kg")])
        self.assertIsNone(parser.parse("1.234,5 kg"))

    def test_unknown_or_partial_values_and_overflow_are_rejected(self):
        parser = MeasurementParser()
        for text in ["123", "abc 2 kg", "2 kg garbage", "2 unknown", "1e999 kg", "10 kg/mystery", "1,5 kg"]:
            with self.subTest(text=text):
                self.assertIsNone(parser.parse(text))
        frame = pd.DataFrame({"Weight": ["2 kg", "bad", "1 kg (2 lb) 3 g"]})
        executor = PipelineExecutor()
        with self.assertRaises(PipelineExecutionError):
            executor.execute(self.plan().steps[0], {"source": frame})
        result = executor.execute(self.plan(errors="null").steps[0], {"source": frame})
        self.assertEqual(result.Weight_value_1.iloc[0], 2)
        self.assertTrue(result.iloc[1:, 1:].isna().all().all())

    def test_generated_column_collisions_and_limits_are_rejected(self):
        frame = pd.DataFrame({"Weight": ["2 kg"], "Weight_value_1": [7]})
        with self.assertRaises(ValueError):
            PipelineExecutor().validate_plan(self.plan(), {"source": frame}, PipelineMode.SEPARATE)
        with self.assertRaises(ValueError):
            PipelineExecutor(max_columns=4).validate_plan(
                self.plan(), {"source": frame[["Weight"]]}, PipelineMode.SEPARATE,
            )

    def test_profile_reports_coverage_and_units_without_values(self):
        profiler = DatasetProfiler(FileReader(), None)
        dataset_profile = profiler.profile("source", pd.DataFrame({
            "Weight": ["135.5 kg (298.7 lbs)", "2 kg", "bad", None],
        }), ",")
        result = dataset_profile.columns[0].measurements
        profile = result[NumberFormat.STANDARD]
        self.assertEqual(profile.recognized_count, 2)
        self.assertEqual(profile.unrecognized_count, 1)
        self.assertEqual(profile.max_pairs, 2)
        self.assertEqual(profile.units_by_position, [{"kg": 2}, {"lbs": 1}])
        self.assertNotIn("135.5", profile.model_dump_json())

    def test_extracted_measurements_can_be_bucketed_and_counted_by_unit(self):
        plan = self.plan()
        definition = plan.model_dump(mode="json")
        definition["steps"].extend([
            dict(id="ranges", operation="bucket", input="extracted", reason="Faixas solicitadas.",
                 column="Weight_value_1", output_column="range", edges=[0, 10, 200], labels=["low", "high"]),
            dict(id="counts", operation="aggregate", input="ranges", reason="Contar por unidade e faixa.",
                 group_by=["Weight_unit_1", "range"], metrics=[dict(function="size", alias="total")]),
        ])
        definition["outputs"] = ["counts"]
        plan = PipelinePlan.model_validate(definition)
        executor = PipelineExecutor()
        frames = {"source": pd.DataFrame({"Weight": ["135.5 kg (298.7 lbs)", "2 kg", "2 lb"]})}
        executor.validate_plan(plan, frames, PipelineMode.SEPARATE)
        for step in plan.steps:
            frames[step.id] = executor.execute(step, frames)
        self.assertEqual(frames["counts"].total.tolist(), [1, 1, 1])


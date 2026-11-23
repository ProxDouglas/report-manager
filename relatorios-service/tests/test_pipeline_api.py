import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi.testclient import TestClient

from relatorios_service.services.chart_service import ChartBuilder
from relatorios_service.services.output_chart_service import OutputChartService
from relatorios_service.main import create_app
from relatorios_service.pipeline_schemas import PipelinePlan
from relatorios_service.repositories.dataset_repository import LocalDatasetRepository
from relatorios_service.repositories.pipeline_repository import LocalPipelineRepository
from relatorios_service.services.dataset_profiler import DatasetProfiler
from relatorios_service.services.dataset_service import DatasetService
from relatorios_service.services.file_reader import FileReader
from relatorios_service.services.pipeline_executor import PipelineExecutor
from relatorios_service.services.pipeline_service import PipelineService


class PipelineAPITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repository = LocalDatasetRepository(self.directory.name)
        reader = FileReader()
        planner = Mock()
        planner.create_plan.return_value = PipelinePlan.model_validate({
            "steps": [{"id": "clean", "operation": "trim", "input": "source", "columns": ["name"], "reason": "Espaços."}],
            "outputs": ["clean"],
        })
        self.container = SimpleNamespace(
            settings=SimpleNamespace(max_upload_files=2, max_upload_bytes=128, max_batch_upload_bytes=160),
            dataset_repository=self.repository,
            dataset_service=DatasetService(reader, self.repository),
            pipeline_service=PipelineService(
                self.repository, LocalPipelineRepository(Path(self.directory.name) / "state.sqlite3"),
                DatasetProfiler(reader, self.repository), planner, PipelineExecutor(),
            ),
        )
        self.container.output_chart_service = OutputChartService(
            self.container.pipeline_service.pipelines,
            self.container.pipeline_service.profiler, ChartBuilder(),
        )
        self.client = TestClient(create_app(self.container))

    def test_api_exposes_pipelines_without_direct_database_analysis(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        self.assertIn("/pipelines", paths)
        self.assertIn("/datasets", paths)
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        self.assertNotIn("/database/health", paths)
        self.assertNotIn("/analytics/question", paths)
        self.assertFalse(any(path.startswith("/reports/") for path in paths))

    def upload(self):
        response = self.client.post("/datasets", files={"file": ("names.csv", b"name\n Ana \n", "text/csv")})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["dataset_id"]

    def test_upload_plan_pause_decide_and_download(self):
        dataset_id = self.upload()
        response = self.client.post("/pipelines", json={"datasets": [{"alias": "source", "dataset_id": dataset_id}]})
        self.assertEqual(response.status_code, 201, response.text)
        pipeline_id = response.json()["id"]
        self.assertEqual(response.json()["status"], "ready")
        paused = self.client.post(f"/pipelines/{pipeline_id}/run")
        self.assertEqual(paused.status_code, 200)
        self.assertEqual(paused.json()["pending_decision"]["step_id"], "clean")
        decided = self.client.post(f"/pipelines/{pipeline_id}/decisions", json={"step_id": "clean", "action": "approve"})
        self.assertEqual(decided.status_code, 200, decided.text)
        self.assertEqual(decided.json()["status"], "completed")
        output_id = decided.json()["outputs"][0]["dataset_id"]
        download = self.client.get(f"/datasets/{output_id}/csv")
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.content.decode("utf-8-sig"), "name\nAna\n")
        self.assertEqual(self.client.get(f"/pipelines/{pipeline_id}").json()["outputs"], decided.json()["outputs"])
        repeated = self.client.post(f"/pipelines/{pipeline_id}/decisions", json={"step_id": "clean", "action": "approve"})
        self.assertEqual(repeated.status_code, 409)

    def test_batch_upload_and_validation_are_atomic(self):
        response = self.client.post("/datasets/batch", files=[
            ("files", ("a.csv", b"name\nAna\n")), ("files", ("b.csv", b"name\nBia\n")),
        ])
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(len(response.json()["datasets"]), 2)
        before = set(Path(self.directory.name).iterdir())
        response = self.client.post("/datasets/batch", files=[
            ("files", ("a.csv", b"name\nAna\n")), ("files", ("b.csv", b"name\n")),
        ])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(Path(self.directory.name).iterdir()), before)

    def test_batch_limits_file_count_per_file_and_total_size(self):
        cases = [
            ([("files", (f"{index}.csv", b"name\nAna\n")) for index in range(3)], 400),
            ([("files", ("a.csv", b"name\n" + b"a" * 130))], 413),
            ([("files", ("a.csv", b"name\n" + b"a" * 80)), ("files", ("b.csv", b"name\n" + b"b" * 80))], 413),
            ([("files", ("a.json", b"{}"))], 400),
        ]
        for files, expected in cases:
            with self.subTest(expected=expected):
                response = self.client.post("/datasets/batch", files=files)
                self.assertEqual(response.status_code, expected, response.text)

    def test_missing_sources_and_invalid_decisions(self):
        self.assertEqual(self.client.get("/pipelines/missing").status_code, 404)
        self.assertEqual(self.client.get("/datasets/invalid/csv").status_code, 400)
        response = self.client.post("/pipelines", json={"datasets": [{"alias": "source", "dataset_id": "0" * 32}]})
        self.assertEqual(response.status_code, 404)
        dataset_id = self.upload()
        response = self.client.post("/pipelines", json={"datasets": [{"alias": "source", "dataset_id": dataset_id}]})
        pipeline_id = response.json()["id"]
        response = self.client.post(f"/pipelines/{pipeline_id}/decisions", json={"step_id": "clean", "action": "approve"})
        self.assertEqual(response.status_code, 409)

    def test_lifespan_starts_and_stops_cleanup(self):
        with TestClient(create_app(self.container)) as client:
            self.assertIn("/pipelines", client.get("/openapi.json").json()["paths"])

    def test_studio_and_its_assets_are_served_without_exposing_configuration(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('lang="pt-BR"', response.text)
        for asset in ("app.js", "pipeline-api.js", "pipeline-view.js", "pipeline-step-view.js", "i18n.js", "translations.js", "styles.css"):
            response = self.client.get(f"/static/{asset}")
            self.assertEqual(response.status_code, 200, asset)
        response = self.client.get("/ui/config")
        self.assertEqual(response.json(), {
            "max_files": 2, "max_file_bytes": 128, "max_batch_bytes": 160,
        })

    def test_ui_assets_revalidate_and_load_the_current_api_version(self):
        page = self.client.get("/")
        self.assertEqual(page.headers["cache-control"], "no-cache")
        self.assertIn('/static/app.js?v=2', page.text)
        self.assertIn('/static/styles.css?v=2', page.text)
        script = self.client.get("/static/app.js?v=2")
        self.assertIn('./pipeline-api.js?v=2', script.text)
        api = self.client.get("/static/pipeline-api.js?v=2")
        self.assertIn("previewStep(id, stepId)", api.text)
        self.assertIn("reviseStep(id, stepId, revision)", api.text)
        for response in (script, api):
            self.assertEqual(response.headers["cache-control"], "no-cache")
        cached = self.client.get("/static/pipeline-api.js?v=2", headers={
            "If-None-Match": api.headers["etag"],
        })
        self.assertEqual(cached.status_code, 304)
        self.assertEqual(cached.headers["cache-control"], "no-cache")

    def test_step_result_preview_download_and_revision(self):
        response = self.client.post("/pipelines", json={
            "datasets": [{"alias": "source", "dataset_id": self.upload()}],
            "autonomy": "autonomous",
        })
        pipeline_id = response.json()["id"]
        step_url = f"/pipelines/{pipeline_id}/steps/clean"
        self.assertEqual(self.client.get(f"{step_url}/preview").status_code, 409)
        self.client.post(f"/pipelines/{pipeline_id}/run")
        preview = self.client.get(f"{step_url}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["rows"], [["Ana"]])
        csv = self.client.get(f"{step_url}/csv")
        self.assertEqual(csv.status_code, 200)
        self.assertIn("attachment", csv.headers["content-disposition"])
        self.assertEqual(csv.content.decode("utf-8-sig"), "name\nAna\n")
        replacement = response.json()["plan"]["steps"][0]
        revised = self.client.put(step_url, json={"replacement": replacement, "expected_revision": 0})
        self.assertEqual(revised.status_code, 200, revised.text)
        self.assertEqual(revised.json()["status"], "awaiting_decision")
        self.assertEqual(revised.json()["outputs"], [])
        self.assertEqual(self.client.get(f"{step_url}/csv").status_code, 409)
        self.assertEqual(self.client.put(step_url, json={
            "replacement": replacement, "expected_revision": 0,
        }).status_code, 409)

    def test_pipeline_rejects_unsupported_response_language(self):
        response = self.client.post("/pipelines", json={
            "datasets": [{"alias": "source", "dataset_id": self.upload()}],
            "language": "es",
        })
        self.assertEqual(response.status_code, 422)
        self.container.pipeline_service.planner.create_plan.assert_not_called()

    def test_user_prompt_reaches_the_planner_without_changing_source_profiles(self):
        dataset_id = self.upload()
        prompt = "Remova espaços da coluna name e preserve os registros."
        response = self.client.post("/pipelines", json={
            "datasets": [{"alias": "source", "dataset_id": dataset_id}],
            "prompt": prompt, "autonomy": "autonomous",
        })
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["request"]["prompt"], prompt)
        call = self.container.pipeline_service.planner.create_plan.call_args
        self.assertEqual(call.args[2], prompt)
        self.assertNotIn("Ana", str(call.args[0]))
        pipeline_id = response.json()["id"]
        result = self.client.post(f"/pipelines/{pipeline_id}/run")
        self.assertEqual(result.json()["status"], "completed")

    def test_oversized_prompt_is_rejected_before_planning(self):
        response = self.client.post("/pipelines", json={
            "datasets": [{"alias": "source", "dataset_id": "0" * 32}],
            "prompt": "a" * 4001,
        })
        self.assertEqual(response.status_code, 422)
        self.container.pipeline_service.planner.create_plan.assert_not_called()

    def test_completed_output_chart_and_invalid_columns(self):
        from fastapi import HTTPException
        from relatorios_service.controllers.pipelines_controller import generate_output_chart
        from relatorios_service.pipeline_schemas import PipelineRequest
        from relatorios_service.schemas import ChartType

        stored = self.container.dataset_service.store_csv("data.csv", b"name,value\nAna,10\nBia,20\n")
        state = self.container.pipeline_service.create(PipelineRequest(
            datasets=[{"alias": "source", "dataset_id": stored["dataset_id"]}],
            autonomy="autonomous",
        ))
        def chart(x="name", y="value"):
            return generate_output_chart(state.id, "clean", x, y, ChartType.BAR, self.container)

        with self.assertRaises(HTTPException) as pending:
            chart()
        self.assertEqual(pending.exception.status_code, 409)
        self.container.pipeline_service.run(state.id)
        response = chart()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Plotly.newPlot", response.body)
        for x, y in [("missing", "value"), ("name", "name")]:
            with self.assertRaises(HTTPException) as invalid:
                chart(x, y)
            self.assertEqual(invalid.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()

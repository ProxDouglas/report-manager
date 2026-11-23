import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
from pydantic import ValidationError

from relatorios_service.services.chart_service import ChartBuilder
from relatorios_service.services.output_chart_service import OutputChartService
from relatorios_service.pipeline_schemas import (
    Autonomy, DecisionAction, PipelineDecision, PipelineMode, PipelinePlan,
    PipelineRequest, PipelineStatus, StepRevision,
)
from relatorios_service.repositories.dataset_repository import LocalDatasetRepository
from relatorios_service.repositories.pipeline_repository import LocalPipelineRepository
from relatorios_service.services.dataset_profiler import DatasetProfiler
from relatorios_service.services.dataset_service import DatasetService, DatasetStorageError
from relatorios_service.services.file_reader import FileReader
from relatorios_service.services.pipeline_executor import PipelineExecutionError, PipelineExecutor
from relatorios_service.services.pipeline_planner import LLMPipelinePlanner
from relatorios_service.services.pipeline_service import (
    PipelineConflictError, PipelinePlanningError, PipelineService,
)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.datasets = LocalDatasetRepository(self.directory.name)
        self.pipelines = LocalPipelineRepository(Path(self.directory.name) / "pipelines.sqlite3")
        self.reader = FileReader()
        self.uploads = DatasetService(self.reader, self.datasets)
        self.profiler = DatasetProfiler(self.reader, self.datasets)
        self.planner = Mock()
        self.executor = PipelineExecutor()
        self.service = PipelineService(
            self.datasets, self.pipelines, self.profiler, self.planner, self.executor,
        )

    def upload(self, content, alias="source"):
        result = self.uploads.store_csv(f"{alias}.csv", content.encode("utf-8"))
        return {"alias": alias, "dataset_id": result["dataset_id"]}

    def plan(self, steps, outputs):
        self.planner.create_plan.return_value = PipelinePlan.model_validate({
            "steps": steps, "outputs": outputs,
        })

    def trim(self, step_id="trimmed", source="source", columns=None):
        if columns is None:
            columns = ["name"]
        return {
            "id": step_id, "operation": "trim", "input": source,
            "columns": columns, "reason": "Remover espaços identificados no perfil.",
        }

    def test_llm_prompt_contains_only_allowed_metadata_even_for_invalid_values(self):
        dataset = self.upload(
            "name;valor\nSEGREDO_CLIENTE_A;1,0\nSEGREDO_CLIENTE_B;2,0\n"
            "SEGREDO_CLIENTE_C;3,0\nSEGREDO_CLIENTE_D;4,0\nSEGREDO_CLIENTE_E;SEGREDO_INVALIDO\n",
        )
        self.plan([], ["source"])
        model = Mock()
        model.with_structured_output.return_value.invoke.return_value = self.planner.create_plan.return_value
        self.service.planner = LLMPipelinePlanner(model)
        self.service.create(PipelineRequest(datasets=[dataset]))
        prompt = model.with_structured_output.return_value.invoke.call_args.args[0]
        self.assertNotIn("SEGREDO", prompt)
        self.assertNotIn(dataset["dataset_id"], prompt)
        self.assertNotIn("invalid_examples", prompt)
        self.assertIn('"name": "valor"', prompt)
        self.assertIn('"invalid_count": 1', prompt)
        self.assertEqual(model.with_structured_output.return_value.invoke.call_count, 1)

    def test_llm_receives_the_user_objective_alongside_only_allowed_metadata(self):
        dataset = self.upload("name\nSEGREDO_CLIENTE\n")
        self.plan([], ["source"])
        model = Mock()
        model.with_structured_output.return_value.invoke.return_value = self.planner.create_plan.return_value
        self.service.planner = LLMPipelinePlanner(model)
        prompt = "Preserve a coluna name como texto."
        self.service.create(PipelineRequest(datasets=[dataset], prompt=prompt))
        rendered = model.with_structured_output.return_value.invoke.call_args.args[0]
        self.assertIn(prompt, rendered)
        self.assertNotIn("SEGREDO_CLIENTE", rendered)

    def test_step_preview_exposes_only_fifteen_processed_rows_and_preserves_inputs(self):
        dataset = self.upload("name\n" + "\n".join(f" Name_{i} " for i in range(20)))
        self.plan([self.trim()], ["trimmed"])
        state = self.service.create(PipelineRequest(datasets=[dataset], autonomy="autonomous"))
        with self.assertRaises(PipelineConflictError):
            self.service.preview_step(state.id, "trimmed")
        self.service.run(state.id)
        preview = self.service.preview_step(state.id, "trimmed")
        self.assertEqual(preview.row_count, 20)
        self.assertEqual(preview.columns, ["name"])
        self.assertEqual(preview.rows, [[f"Name_{i}"] for i in range(15)])
        self.assertEqual(self.profiler.load(dataset["dataset_id"])[0].iloc[0, 0], " Name_0 ")
        self.assertEqual(self.planner.create_plan.call_count, 1)

    def test_step_preview_preserves_large_integers_nulls_and_identifiers(self):
        dataset = self.upload("value;code\n9007199254740993;001\nNULL;002\n")
        self.plan([
            {"id": "nulls", "operation": "null_markers", "input": "source",
             "columns": ["value"], "reason": "Normalize nulls."},
            {"id": "numbers", "operation": "cast", "input": "nulls",
             "columns": ["value"], "target": "integer", "reason": "Convert integers."},
        ], ["numbers"])
        state = self.service.create(PipelineRequest(datasets=[dataset], autonomy="autonomous"))
        state = self.service.run(state.id)
        preview = self.service.preview_step(state.id, "numbers")
        self.assertEqual(preview.rows, [["9007199254740993", "001"], [None, "002"]])
        self.assertEqual(self.service.get(state.id).model_dump(), state.model_dump())

    def test_correcting_executed_step_invalidates_suffix_and_requires_new_approvals(self):
        dataset = self.upload("name;code\n Ana ; 001 \n")
        self.plan([
            self.trim("first"), self.trim("second", "first"),
            self.trim("third", "second", ["code"]),
        ], ["third"])
        state = self.service.create(PipelineRequest(datasets=[dataset], autonomy="autonomous"))
        state = self.service.run(state.id)
        self.assertEqual(self.service.preview_step(state.id, "second").rows, [["Ana", " 001 "]])
        revision = StepRevision(
            replacement=self.trim("second", "first", ["name", "code"]), expected_revision=0,
        )
        state = self.service.revise_step(state.id, "second", revision)
        self.assertEqual(state.next_step, 1)
        self.assertEqual([report.step_id for report in state.reports], ["first"])
        self.assertEqual(state.outputs, [])
        self.assertEqual(state.revision, 1)
        self.assertEqual(state.pending_decision.step_id, "second")
        self.assertEqual(state.request.autonomy, Autonomy.SUPERVISED)
        self.assertEqual(self.service.preview_step(state.id, "first").rows, [["Ana", " 001 "]])
        with self.assertRaises(PipelineConflictError):
            self.service.preview_step(state.id, "second")
        with self.assertRaises(PipelineConflictError):
            self.service.revise_step(state.id, "first", revision)
        state = self.service.decide(state.id, PipelineDecision(step_id="second", action="approve"))
        self.assertEqual(state.pending_decision.step_id, "third")
        self.assertEqual(self.service.preview_step(state.id, "second").rows, [["Ana", "001"]])
        state = self.service.decide(state.id, PipelineDecision(step_id="third", action="approve"))
        self.assertEqual(state.status, PipelineStatus.COMPLETED)
        self.assertEqual(len(state.outputs), 1)
        self.assertEqual(self.planner.create_plan.call_count, 1)

    def test_invalid_executed_step_correction_preserves_completed_state(self):
        dataset = self.upload("name\n Ana \n")
        self.plan([self.trim()], ["trimmed"])
        state = self.service.create(PipelineRequest(datasets=[dataset], autonomy="autonomous"))
        state = self.service.run(state.id)
        before = state.model_dump()
        with self.assertRaises(ValueError):
            self.service.revise_step(state.id, "trimmed", StepRevision(
                replacement=self.trim(columns=["missing"]), expected_revision=0,
            ))
        self.assertEqual(self.service.get(state.id).model_dump(), before)
        with self.assertRaises(ValueError):
            self.service.revise_step(state.id, "trimmed", StepRevision(
                replacement=self.trim("new_id"), expected_revision=0,
            ))
        self.assertEqual(self.service.get(state.id).model_dump(), before)

    def test_response_language_defaults_to_english_and_accepts_portuguese(self):
        dataset = self.upload("name\n Ana \n")
        self.plan([], ["source"])
        model = Mock()
        model.with_structured_output.return_value.invoke.return_value = self.planner.create_plan.return_value
        self.service.planner = LLMPipelinePlanner(model)
        for language in ("en", "pt-BR"):
            with self.subTest(language=language):
                options = {}
                if language == "pt-BR":
                    options["language"] = language
                state = self.service.create(PipelineRequest(datasets=[dataset], **options))
                rendered = model.with_structured_output.return_value.invoke.call_args.args[0]
                self.assertIn(f"generated labels in {language}", rendered)
                self.assertEqual(state.request.language, language)
                self.assertEqual(self.service.get(state.id).request.language, language)

    def test_authorized_sample_is_limited_and_sent_to_llm(self):
        dataset = self.upload("name\n" + "\n".join(f"CLIENTE_{i}" for i in range(8)))
        self.plan([], ["source"])
        model = Mock()
        model.with_structured_output.return_value.invoke.return_value = self.planner.create_plan.return_value
        self.service.planner = LLMPipelinePlanner(model)
        state = self.service.create(PipelineRequest(datasets=[dataset], allow_data_sample=True))
        rendered = model.with_structured_output.return_value.invoke.call_args.args[0]
        self.assertIn("CLIENTE_4", rendered)
        self.assertNotIn("CLIENTE_5", rendered)
        self.assertTrue(state.request.allow_data_sample)

    def test_raw_values_survive_loading_until_their_explicit_step(self):
        dataset = self.upload("name;code\n Ana ;001\nNULL;002\n")
        frame, _ = self.profiler.load(dataset["dataset_id"])
        self.assertEqual(frame.iloc[0]["name"], " Ana ")
        self.assertEqual(frame.iloc[1]["name"], "NULL")
        self.assertEqual(frame.iloc[0]["code"], "001")

    def test_analytical_output_is_persisted_and_its_planned_chart_is_rendered(self):
        from types import SimpleNamespace
        from relatorios_service.controllers.pipelines_controller import generate_output_chart

        dataset = self.upload('Pokemon,Type\nA,"Grass, Ice"\nB,Normal\nC,Psychic\n')
        self.planner.create_plan.return_value = PipelinePlan.model_validate({
            "steps": [
                dict(id="types", operation="split_explode", input="source", column="Type", separator=",", reason="Separar tipos."),
                dict(id="filtered", operation="filter", input="types", conditions=[
                    dict(column="Type", operator="in", values=["Ice", "Normal"]),
                ], reason="Tipos pedidos."),
                dict(id="counts", operation="aggregate", input="filtered", group_by=["Type"], metrics=[
                    dict(function="size", alias="count"),
                ], reason="Contar registros."),
            ],
            "outputs": ["counts"],
            "charts": [dict(reference="counts", x="Type", y="count", chart_type="bar")],
        })
        state = self.service.create(PipelineRequest(datasets=[dataset], autonomy="autonomous"))
        state = self.service.run(state.id)
        self.assertEqual(state.status, PipelineStatus.COMPLETED)
        output = self.datasets.get(state.outputs[0].dataset_id).content.decode("utf-8-sig")
        self.assertEqual(output, "Type,count\nIce,1\nNormal,1\n")
        self.assertEqual(self.service.get(state.id).plan.charts[0].y, "count")
        chart = generate_output_chart(state.id, "counts", container=SimpleNamespace(output_chart_service=OutputChartService(
            self.pipelines, self.profiler, ChartBuilder(),
        )))
        self.assertIn(b"Plotly.newPlot", chart.body)
        self.planner.create_plan.assert_called_once()

    def test_supervised_asks_at_each_step_and_delegating_one_does_not_delegate_rest(self):
        dataset = self.upload("name\n Ana \n")
        self.plan([
            self.trim(), self.trim("trimmed_again", "trimmed"),
        ], ["trimmed_again"])
        state = self.service.create(PipelineRequest(datasets=[dataset]))
        state = self.service.run(state.id)
        self.assertEqual(state.status, PipelineStatus.AWAITING_DECISION)
        self.assertEqual(state.next_step, 0)
        self.assertEqual(state.outputs, [])
        self.assertEqual(state.pending_decision.actions, list(DecisionAction))
        state = self.service.decide(state.id, PipelineDecision(
            step_id="trimmed", action=DecisionAction.DELEGATE_STEP,
        ))
        self.assertEqual(state.next_step, 1)
        self.assertEqual(state.pending_decision.step_id, "trimmed_again")
        self.assertEqual(state.request.autonomy, Autonomy.SUPERVISED)
        self.assertEqual(state.reports[0].decided_by, Autonomy.AUTONOMOUS)
        # Outra instância recupera a decisão pendente sem replanejar.
        restored = LocalPipelineRepository(self.pipelines.path).get(state.id)
        self.assertEqual(restored.pending_decision.step_id, "trimmed_again")
        with self.assertRaises(PipelineConflictError):
            self.service.decide(state.id, PipelineDecision(
                step_id="trimmed", action=DecisionAction.APPROVE,
            ))
        state = self.service.decide(state.id, PipelineDecision(
            step_id="trimmed_again", action=DecisionAction.APPROVE,
        ))
        self.assertEqual(state.status, PipelineStatus.COMPLETED)
        self.assertEqual(state.reports[1].decided_by, Autonomy.SUPERVISED)
        self.assertEqual(state.outputs[0].row_count, 1)
        output = self.datasets.get(state.outputs[0].dataset_id)
        self.assertIn("Ana", output.content.decode("utf-8-sig"))
        # run concluído é idempotente: não cria novas saídas.
        self.assertEqual(self.service.run(state.id).outputs, state.outputs)

    def test_delegate_remaining_and_initial_autonomy_finish_without_new_questions(self):
        dataset = self.upload("name\n Ana \n")
        self.plan([self.trim(), self.trim("second", "trimmed")], ["second"])
        for autonomy in Autonomy:
            with self.subTest(autonomy=autonomy):
                state = self.service.create(PipelineRequest(datasets=[dataset], autonomy=autonomy))
                state = self.service.run(state.id)
                if autonomy == Autonomy.SUPERVISED:
                    state = self.service.decide(state.id, PipelineDecision(
                        step_id="trimmed", action=DecisionAction.DELEGATE_REMAINING,
                    ))
                self.assertEqual(state.status, PipelineStatus.COMPLETED)
                self.assertEqual(len(state.reports), 2)
                self.assertIsNone(state.pending_decision)

    def test_failure_pauses_autonomous_execution_and_manual_replacement_can_recover(self):
        dataset = self.upload("amount\nSEGREDO_INVALIDO\n")
        cast = {
            "id": "converted", "operation": "cast", "input": "source",
            "columns": ["amount"], "target": "integer", "reason": "Conversão proposta.",
        }
        self.plan([cast], ["converted"])
        state = self.service.create(PipelineRequest(datasets=[dataset], autonomy=Autonomy.AUTONOMOUS))
        state = self.service.run(state.id)
        self.assertEqual(state.status, PipelineStatus.AWAITING_DECISION)
        self.assertNotIn("SEGREDO", state.error)
        self.assertEqual(state.next_step, 0)
        cast["errors"] = "null"
        state = self.service.decide(state.id, PipelineDecision.model_validate({
            "step_id": "converted", "action": "approve", "replacement": cast,
        }))
        self.assertEqual(state.status, PipelineStatus.COMPLETED)
        self.assertEqual(state.reports[0].null_count, 1)
        self.assertEqual(self.planner.create_plan.call_count, 1)

    def test_cancel_never_executes_pending_step(self):
        dataset = self.upload("name\n Ana \n")
        self.plan([self.trim()], ["trimmed"])
        state = self.service.create(PipelineRequest(datasets=[dataset]))
        self.service.run(state.id)
        with patch.object(self.executor, "execute") as execute:
            state = self.service.decide(state.id, PipelineDecision(
                step_id="trimmed", action=DecisionAction.CANCEL,
            ))
            execute.assert_not_called()
        self.assertEqual(state.status, PipelineStatus.CANCELLED)
        self.assertEqual(self.service.run(state.id).status, PipelineStatus.CANCELLED)

    def test_separate_mode_keeps_multiple_outputs_and_originals(self):
        first = self.upload("name\n Ana \n", "first")
        second = self.upload("name\n Bia \n", "second")
        self.plan([
            self.trim("a", "first"), self.trim("b", "second"),
        ], ["a", "b"])
        state = self.service.create(PipelineRequest(
            datasets=[first, second], autonomy=Autonomy.AUTONOMOUS,
        ))
        state = self.service.run(state.id)
        self.assertEqual(len(state.outputs), 2)
        self.assertIn(" Ana ", self.datasets.get(first["dataset_id"]).content.decode())

    def test_joined_pipeline_normalizes_keys_locally_and_preserves_leading_zeroes(self):
        clients = self.upload("client_id;name\n001;Ana\n002;Bia\n", "clients")
        orders = self.upload("client_id;amount\n 001 ;10,5\n001;20,0\n", "orders")
        self.plan([
            self.trim("clean_orders", "orders", ["client_id"]),
            {"id": "numbers", "operation": "cast", "input": "clean_orders", "columns": ["amount"],
             "target": "number", "number_format": "brazilian", "reason": "Decimal com vírgula."},
            {"id": "joined", "operation": "join", "left": "numbers", "right": "clients",
             "left_on": ["client_id"], "right_on": ["client_id"], "how": "left",
             "cardinality": "many_to_one", "reason": "Relacionar pedidos a clientes."},
        ], ["joined"])
        state = self.service.create(PipelineRequest(
            datasets=[clients, orders], mode=PipelineMode.JOINED, autonomy=Autonomy.AUTONOMOUS,
        ))
        state = self.service.run(state.id)
        self.assertEqual(state.status, PipelineStatus.COMPLETED)
        self.assertEqual(state.outputs[0].row_count, 2)
        output = self.datasets.get(state.outputs[0].dataset_id).content.decode("utf-8-sig")
        self.assertIn("001,10.5,Ana", output)
        self.assertIn("001,20.0,Ana", output)

    def test_invalid_graph_unknown_columns_or_incomplete_outputs_are_rejected_before_run(self):
        dataset = self.upload("name\nAna\n")
        cases = [
            ([self.trim(source="future")], ["trimmed"]),
            ([self.trim(columns=["missing"])], ["trimmed"]),
            ([self.trim(step_id="source")], ["source"]),
            ([], ["missing"]),
        ]
        for steps, outputs in cases:
            with self.subTest(outputs=outputs, steps=steps):
                self.plan(steps, outputs)
                with self.assertRaises(PipelinePlanningError):
                    self.service.create(PipelineRequest(datasets=[dataset]))

    def test_unsafe_operations_extra_parameters_and_ambiguous_dates_are_rejected(self):
        for step in [
            {**self.trim(), "code": "print('unsafe')"},
            {**self.trim(), "operation": "python"},
            {**self.trim(), "operation": "cast", "target": "date"},
        ]:
            with self.subTest(step=step), self.assertRaises(ValidationError):
                PipelinePlan.model_validate({"steps": [step], "outputs": ["trimmed"]})

    def test_pipeline_repository_rolls_back_failed_edits_and_expires_state(self):
        dataset = self.upload("name\nAna\n")
        self.plan([], ["source"])
        state = self.service.create(PipelineRequest(datasets=[dataset]))
        with self.assertRaises(ValueError):
            with self.pipelines.edit(state.id) as editable:
                editable.status = PipelineStatus.CANCELLED
                raise ValueError("rollback")
        self.assertEqual(self.pipelines.get(state.id).status, PipelineStatus.READY)
        with patch("relatorios_service.repositories.pipeline_repository.time.time", return_value=time.time() + 7201):
            with self.assertRaises(FileNotFoundError):
                self.pipelines.get(state.id)
            self.assertEqual(self.pipelines.cleanup_expired(), 1)

    def test_concurrent_decisions_execute_the_step_only_once(self):
        dataset = self.upload("name\n Ana \n")
        self.plan([self.trim()], ["trimmed"])
        state = self.service.create(PipelineRequest(datasets=[dataset]))
        self.service.run(state.id)
        decision = PipelineDecision(step_id="trimmed", action=DecisionAction.APPROVE)
        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(self.service.decide, state.id, decision) for _ in range(2)]
            results = []
            conflicts = 0
            for future in futures:
                try:
                    results.append(future.result(timeout=5))
                except PipelineConflictError:
                    conflicts += 1
        self.assertEqual(conflicts, 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(self.service.get(state.id).reports), 1)

    def test_failed_batch_storage_removes_previously_saved_files(self):
        save = self.datasets.save
        calls = 0

        def fail_second(dataset):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("Falha simulada de armazenamento.")
            save(dataset)

        before = set(Path(self.directory.name).iterdir())
        with patch.object(self.datasets, "save", side_effect=fail_second):
            with self.assertRaises(DatasetStorageError):
                self.uploads.store_many([("a.csv", b"name\nAna\n"), ("b.csv", b"name\nBia\n")])
        self.assertEqual(set(Path(self.directory.name).iterdir()), before)


class PipelineExecutorTests(unittest.TestCase):
    def setUp(self):
        self.executor = PipelineExecutor(max_rows=10)

    def step(self, **parameters):
        return PipelinePlan.model_validate({
            "steps": [{"id": "out", "reason": "Tratamento local.", **parameters}],
            "outputs": ["out"],
        }).steps[0]

    def join(self, **parameters):
        return self.step(
            operation="join", left="left", right="right", left_on=["id"], right_on=["id"],
            **parameters,
        )

    def test_many_to_many_is_bounded_before_materialization(self):
        frames = {"left": pd.DataFrame({"id": [1] * 4}), "right": pd.DataFrame({"id": [1] * 4})}
        with patch.object(self.executor.joins, "_merge") as merge:
            with self.assertRaisesRegex(PipelineExecutionError, "limite"):
                self.executor.execute(self.join(cardinality="many_to_many"), frames)
            merge.assert_not_called()

    def test_cardinality_and_type_mismatch_are_blocked(self):
        for right in [pd.DataFrame({"id": [1, 1]}), pd.DataFrame({"id": ["1"]})]:
            with self.subTest(right=right):
                with self.assertRaises(PipelineExecutionError):
                    self.executor.execute(self.join(), {"left": pd.DataFrame({"id": [1]}), "right": right})

    def test_null_keys_never_match_for_all_join_types(self):
        frames = {
            "left": pd.DataFrame({"id": pd.Series([1, None, None], dtype="Int64"), "a": [1, 2, 3]}),
            "right": pd.DataFrame({"id": pd.Series([1, None, None], dtype="Int64"), "b": [1, 2, 3]}),
        }
        for how, expected in [("inner", 1), ("left", 3), ("right", 3), ("outer", 5)]:
            with self.subTest(how=how):
                result = self.executor.execute(self.join(how=how, cardinality="one_to_one"), frames)
                self.assertEqual(len(result), expected)
                self.assertEqual(int((result.a.notna() & result.b.notna()).sum()), 1)

    def test_composite_keys_join(self):
        step = self.step(operation="join", left="left", right="right", left_on=["id", "day"], right_on=["id", "day"])
        result = self.executor.execute(step, {
            "left": pd.DataFrame({"id": [1, 1], "day": [1, 2]}),
            "right": pd.DataFrame({"id": [1, 1], "day": [1, 2], "amount": [10, 20]}),
        })
        self.assertEqual(result.amount.tolist(), [10, 20])

    def test_transformations_do_not_mutate_source_and_support_explicit_nulls(self):
        frame = pd.DataFrame({"value": pd.Series([" 1,5 ", "NULL", " 3,5 "], dtype="string")})
        frames = {"source": frame}
        steps = [
            self.step(operation="trim", input="source", columns=["value"]),
            self.step(operation="null_markers", input="out", columns=["value"]),
            self.step(operation="cast", input="out", columns=["value"], target="number", number_format="brazilian"),
            self.step(operation="fill_nulls", input="out", columns=["value"], strategy="mean"),
        ]
        for step in steps:
            frames["out"] = self.executor.execute(step, frames)
        self.assertEqual(frames["out"].value.tolist(), [1.5, 2.5, 3.5])
        self.assertEqual(frame.value.tolist(), [" 1,5 ", "NULL", " 3,5 "])

    def test_dates_drop_nulls_deduplication_and_select(self):
        frames = {"source": pd.DataFrame({"date": pd.Series(["23/10/2026", "23/10/2026", "invalid"], dtype="string"), "x": [1, 1, 2]})}
        steps = [
            self.step(operation="cast", input="source", columns=["date"], target="date", date_format="%d/%m/%Y", errors="null"),
            self.step(operation="drop_nulls", input="out", columns=["date"]),
            self.step(operation="deduplicate", input="out", columns=["date"], keep="first"),
            self.step(operation="select", input="out", columns=["date"]),
        ]
        for step in steps:
            frames["out"] = self.executor.execute(step, frames)
        self.assertEqual(list(frames["out"].columns), ["date"])
        self.assertEqual(len(frames["out"]), 1)
        self.assertEqual(frames["out"].date.iloc[0], pd.Timestamp("2026-10-23"))

    def test_mode_requires_unique_winner(self):
        step = self.step(operation="fill_nulls", input="source", columns=["x"], strategy="mode")
        with self.assertRaises(PipelineExecutionError):
            self.executor.execute(step, {"source": pd.DataFrame({"x": [1, 2, None]})})

    def test_integer_conversion_preserves_precision_above_float_exact_range(self):
        step = self.step(operation="cast", input="source", columns=["x"], target="integer")
        result = self.executor.execute(step, {"source": pd.DataFrame({
            "x": pd.Series(["9007199254740993", "9007199254740995"], dtype="string"),
        })})
        self.assertEqual(result.x.tolist(), [9007199254740993, 9007199254740995])


if __name__ == "__main__":
    unittest.main()

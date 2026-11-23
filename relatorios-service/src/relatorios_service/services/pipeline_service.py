import json
import uuid

import pandas as pd

from relatorios_service.models.dataset import StoredDataset
from relatorios_service.pipeline_schemas import (
    Autonomy, DecisionAction, DecisionPrompt, PipelineDecision, PipelineOutput,
    PipelineRequest, PipelineState, PipelineStatus, StepPreview, StepReport, StepRevision,
)
from relatorios_service.repositories.dataset_repository import DatasetRepository
from relatorios_service.repositories.pipeline_repository import PipelineRepository
from relatorios_service.services.dataset_profiler import DatasetProfiler
from relatorios_service.services.pipeline_executor import PipelineExecutionError, PipelineExecutor
from relatorios_service.services.pipeline_planner import PipelinePlanner


class PipelineConflictError(ValueError):
    pass


class PipelinePlanningError(Exception):
    pass


class PipelineService:
    def __init__(
        self, datasets: DatasetRepository, pipelines: PipelineRepository,
        profiler: DatasetProfiler, planner: PipelinePlanner, executor: PipelineExecutor,
    ) -> None:
        self.datasets = datasets
        self.pipelines = pipelines
        self.profiler = profiler
        self.planner = planner
        self.executor = executor

    def create(self, request: PipelineRequest) -> PipelineState:
        profiles = []
        frames = {}
        for dataset in request.datasets:
            frame, delimiter = self.profiler.load(dataset.dataset_id)
            frames[dataset.alias] = frame
            profile = self.profiler.profile(dataset.alias, frame, delimiter)
            if request.allow_data_sample:
                sample = frame.head(5).astype(object)
                profile.sample = sample.where(sample.notna(), None).to_dict(orient="records")
            profiles.append(profile)
        try:
            plan = self.planner.create_plan(profiles, request.mode, request.prompt, request.language)
            self.executor.validate_plan(plan, frames, request.mode)
        except Exception as error:
            # Não devolver respostas/erros do provedor nem fazer retry com dados brutos.
            raise PipelinePlanningError(
                "Não foi possível obter um plano válido usando os metadados permitidos.",
            ) from error
        state = PipelineState(id=uuid.uuid4().hex, request=request, plan=plan)
        self.pipelines.create(state)
        return state

    def get(self, pipeline_id: str) -> PipelineState:
        return self.pipelines.get(pipeline_id)

    def preview_step(
        self, pipeline_id: str, step_id: str,
    ) -> StepPreview:
        frame = self.step_result(pipeline_id, step_id)
        # A prévia é textual para preservar inteiros grandes e formatos no navegador.
        rows = json.loads(frame.head(15).astype("string").to_json(
            orient="values", force_ascii=False,
        ))
        return StepPreview(
            step_id=step_id, columns=list(frame.columns), rows=rows,
            row_count=len(frame),
        )

    def step_result(self, pipeline_id: str, step_id: str) -> pd.DataFrame:
        state = self.pipelines.get(pipeline_id)
        executed = state.plan.steps[:state.next_step]
        for index, step in enumerate(executed):
            if step.id == step_id:
                return self._replay(state, index + 1)[step_id]
        raise PipelineConflictError("O resultado só está disponível para etapas executadas.")

    def cleanup_expired(self) -> int:
        return self.pipelines.cleanup_expired()

    def run(self, pipeline_id: str) -> PipelineState:
        with self.pipelines.edit(pipeline_id) as state:
            if state.status == PipelineStatus.READY:
                self._advance(state)
            return state

    def decide(self, pipeline_id: str, decision: PipelineDecision) -> PipelineState:
        with self.pipelines.edit(pipeline_id) as state:
            if (state.status != PipelineStatus.AWAITING_DECISION
                    or state.pending_decision is None
                    or state.pending_decision.step_id != decision.step_id):
                raise PipelineConflictError("A decisão não corresponde à etapa pendente.")
            if decision.action == DecisionAction.CANCEL:
                state.status = PipelineStatus.CANCELLED
                state.pending_decision = None
                return state
            if decision.replacement is not None:
                candidate = state.plan.model_copy(deep=True)
                candidate.steps[state.next_step] = decision.replacement
                self.executor.validate_plan(candidate, self._load_frames(state), state.request.mode)
                state.plan = candidate
            if decision.action == DecisionAction.DELEGATE_REMAINING:
                state.request.autonomy = Autonomy.AUTONOMOUS
            actor = Autonomy.AUTONOMOUS
            if decision.action == DecisionAction.APPROVE:
                actor = Autonomy.SUPERVISED
            state.status = PipelineStatus.READY
            state.pending_decision = None
            state.error = None
            self._advance(state, approved_actor=actor)
            return state

    def revise_step(
        self, pipeline_id: str, step_id: str, revision: StepRevision,
    ) -> PipelineState:
        with self.pipelines.edit(pipeline_id) as state:
            if revision.expected_revision != state.revision:
                raise PipelineConflictError("O pipeline foi alterado. Atualize o estado antes de corrigir.")
            if state.status == PipelineStatus.CANCELLED:
                raise PipelineConflictError("Um pipeline cancelado não pode ser corrigido.")
            index = next((
                index for index, step in enumerate(state.plan.steps[:state.next_step])
                if step.id == step_id
            ), None)
            if index is None:
                raise PipelineConflictError("Somente etapas executadas podem ser corrigidas.")
            if revision.replacement.id != step_id:
                raise ValueError("A correção deve preservar o identificador da etapa.")
            candidate = state.plan.model_copy(deep=True)
            candidate.steps[index] = revision.replacement
            self.executor.validate_plan(candidate, self._load_frames(state), state.request.mode)
            state.plan = candidate
            state.next_step = index
            state.reports = state.reports[:index]
            state.outputs = []
            state.error = None
            state.revision += 1
            state.request.autonomy = Autonomy.SUPERVISED
            self._pause(state)
            return state

    def _load_frames(self, state: PipelineState) -> dict[str, pd.DataFrame]:
        return {
            dataset.alias: self.profiler.load(dataset.dataset_id)[0]
            for dataset in state.request.datasets
        }

    def _replay(self, state: PipelineState, count: int) -> dict[str, pd.DataFrame]:
        frames = self._load_frames(state)
        # Reconstituir o prefixo mantém os tipos e não envia dados ao LLM.
        for step in state.plan.steps[:count]:
            frames[step.id] = self.executor.execute(step, frames)
        return frames

    def _advance(self, state: PipelineState, approved_actor: Autonomy | None = None) -> None:
        frames = self._replay(state, state.next_step)
        while state.next_step < len(state.plan.steps):
            step = state.plan.steps[state.next_step]
            if state.request.autonomy == Autonomy.SUPERVISED and approved_actor is None:
                self._pause(state)
                return
            actor = approved_actor
            if actor is None:
                actor = Autonomy.AUTONOMOUS
            try:
                result = self.executor.execute(step, frames)
            except PipelineExecutionError as error:
                state.error = str(error)
                state.request.autonomy = Autonomy.SUPERVISED
                self._pause(state)
                return
            state.reports.append(StepReport(
                step_id=step.id, decided_by=actor,
                input_rows=self.executor.input_rows(step, frames),
                output_rows=len(result), null_count=int(result.isna().sum().sum()),
            ))
            frames[step.id] = result
            state.next_step += 1
            approved_actor = None
        state.outputs = self._save_outputs(state, frames)
        state.status = PipelineStatus.COMPLETED
        state.pending_decision = None
        state.error = None

    def _pause(self, state: PipelineState) -> None:
        state.status = PipelineStatus.AWAITING_DECISION
        state.pending_decision = DecisionPrompt(step_id=state.plan.steps[state.next_step].id)

    def _save_outputs(self, state: PipelineState, frames: dict[str, pd.DataFrame]) -> list[PipelineOutput]:
        outputs = []
        try:
            for reference in state.plan.outputs:
                frame = frames[reference]
                dataset_id = uuid.uuid4().hex
                self.datasets.save(StoredDataset(
                    dataset_id=dataset_id,
                    filename=f"{reference}.csv",
                    content=frame.to_csv(index=False).encode("utf-8-sig"),
                ))
                outputs.append(PipelineOutput(
                    reference=reference, dataset_id=dataset_id,
                    row_count=len(frame), columns=list(frame.columns),
                ))
        except OSError:
            for output in outputs:
                self.datasets.delete(output.dataset_id)
            raise
        return outputs

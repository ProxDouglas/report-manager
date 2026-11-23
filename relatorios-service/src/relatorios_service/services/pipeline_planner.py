import json
from typing import Protocol

from langchain_openai import ChatOpenAI

from relatorios_service.pipeline_schemas import Language, PipelineMode, PipelinePlan
from relatorios_service.prompts import load_prompt
from relatorios_service.services.dataset_profiler import DatasetProfile


class PipelinePlanner(Protocol):
    def create_plan(
        self, profiles: list[DatasetProfile], mode: PipelineMode, prompt: str = "",
        language: Language = Language.ENGLISH,
    ) -> PipelinePlan: ...


class LLMPipelinePlanner:
    def __init__(self, model: ChatOpenAI) -> None:
        self.model = model

    def create_plan(
        self, profiles: list[DatasetProfile], mode: PipelineMode, prompt: str = "",
        language: Language = Language.ENGLISH,
    ) -> PipelinePlan:
        # Amostras limitadas entram no perfil somente com autorização explícita.
        prompt = load_prompt("data_pipeline").format(
            response_language=language.value,
            schema_json=json.dumps(PipelinePlan.model_json_schema(), ensure_ascii=False),
            mode=mode.value,
            user_prompt=json.dumps(prompt, ensure_ascii=False),
            profiles_json=json.dumps(
                [profile.model_dump(mode="json") for profile in profiles],
                ensure_ascii=False,
            ),
        )
        structured_model = self.model.with_structured_output(
            PipelinePlan, method="json_mode",
        )
        return PipelinePlan.model_validate(structured_model.invoke(prompt))

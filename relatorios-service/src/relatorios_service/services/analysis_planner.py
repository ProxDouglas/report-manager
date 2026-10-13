import json

from langchain_openai import ChatOpenAI

from relatorios_service.metric_catalog import MetricCatalog
from relatorios_service.schemas import AnalysisPlan, AnalysisRequest
from relatorios_service.prompts import load_prompt


class AnalysisPlanner:
    """Gera o plano estruturado de análise a partir da pergunta."""

    def __init__(self, model: ChatOpenAI, catalog: MetricCatalog) -> None:
        self.model = model
        self.catalog = catalog

    def create_plan(self, request: AnalysisRequest) -> AnalysisPlan:
        prompt = load_prompt("analysis_plan").format(
            schema_json=json.dumps(AnalysisPlan.model_json_schema(), ensure_ascii=False),
            catalog_context=self.catalog.context(),
            question=request.question,
        )
        structured_model = self.model.with_structured_output(
            AnalysisPlan,
            method="json_mode",
        )
        result = structured_model.invoke(prompt)
        return AnalysisPlan.model_validate(result)

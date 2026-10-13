import json
from typing import Any

import pandas as pd
from langchain_openai import ChatOpenAI

from relatorios_service.schemas import AnalysisPlan, AnalysisRequest
from relatorios_service.prompts import load_prompt


def to_records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
    content = dataframe.to_json(
        orient="records",
        date_format="iso",
    )
    return json.loads(content)



def to_text(content: Any) -> str:
    if isinstance(content, str):
        return content

    return json.dumps(content, ensure_ascii=False, default=str)



class AnswerWriter:
    """Gera a resposta textual a partir do resultado calculado."""

    def __init__(self, model: ChatOpenAI) -> None:
        self.model = model

    def create_answer(
        self,
        request: AnalysisRequest,
        plan: AnalysisPlan,
        dataframe: pd.DataFrame,
        truncated: bool,
        warnings: list[dict[str, Any]],
    ) -> str:
        records = to_records(dataframe.head(100))
        truncation_note = ""

        if truncated:
            truncation_note = (
                " O resultado foi limitado ao máximo configurado de linhas."
            )

        prompt = load_prompt("answer").format(
            question=request.question,
            plan_json=plan.model_dump_json(ensure_ascii=False),
            records_json=json.dumps(records, ensure_ascii=False, default=str),
            truncation_note=truncation_note,
            warnings_json=json.dumps(warnings, ensure_ascii=False, default=str),
        )
        result = self.model.invoke(prompt)
        return to_text(result.content) + truncation_note

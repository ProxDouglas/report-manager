from fastapi import APIRouter, Depends, HTTPException

from relatorios_service.common.dependencies import (
    ApplicationContainer,
    get_container,
)
from relatorios_service.schemas import AnalysisRequest


router = APIRouter()


@router.post("/analytics/question")
def analytics_question(
    request: AnalysisRequest,
    container: ApplicationContainer = Depends(get_container),
) -> dict:
    try:
        result = container.analysis_service.analyze(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao analisar os dados: {error}",
        ) from error

    return result.model_dump(mode="json")

import sqlite3
from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response

from relatorios_service.common.dependencies import ApplicationContainer, get_container
from relatorios_service.pipeline_schemas import PipelineDecision, PipelineRequest, PipelineState, StepPreview, StepRevision
from relatorios_service.schemas import ChartType
from relatorios_service.services.output_chart_service import (
    OutputChartNotFoundError, OutputChartValidationError,
)
from relatorios_service.services.pipeline_service import PipelineConflictError, PipelinePlanningError


router = APIRouter(prefix="/pipelines", tags=["pipelines"])


ResponseT = TypeVar("ResponseT")


def _respond(action: Callable[[], ResponseT]) -> ResponseT:
    try:
        return action()
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="Pipeline ou dataset não encontrado ou expirado.") from error
    except PipelineConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except PipelinePlanningError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except ValueError as error:
        # Erros de bibliotecas podem incluir valores brutos. Não os devolver neste fluxo.
        raise HTTPException(status_code=422, detail="Plano, parâmetros ou estrutura de CSV inválidos.") from error
    except sqlite3.OperationalError as error:
        raise HTTPException(status_code=503, detail="Armazenamento de pipelines temporariamente indisponível.") from error
    except OSError as error:
        raise HTTPException(status_code=500, detail="Não foi possível armazenar o pipeline ou suas saídas.") from error


@router.post("", status_code=201, response_model=PipelineState)
def create_pipeline(
    request: PipelineRequest,
    container: ApplicationContainer = Depends(get_container),
) -> PipelineState:
    return _respond(lambda: container.pipeline_service.create(request))


@router.get("/{pipeline_id}", response_model=PipelineState)
def get_pipeline(
    pipeline_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> PipelineState:
    return _respond(lambda: container.pipeline_service.get(pipeline_id))


@router.post("/{pipeline_id}/run", response_model=PipelineState)
def run_pipeline(
    pipeline_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> PipelineState:
    return _respond(lambda: container.pipeline_service.run(pipeline_id))


@router.post("/{pipeline_id}/decisions", response_model=PipelineState)
def decide_pipeline_step(
    pipeline_id: str,
    decision: PipelineDecision,
    container: ApplicationContainer = Depends(get_container),
) -> PipelineState:
    return _respond(lambda: container.pipeline_service.decide(pipeline_id, decision))


@router.get("/{pipeline_id}/outputs/{reference}/chart", response_class=HTMLResponse)
def generate_output_chart(
    pipeline_id: str,
    reference: str,
    x: str | None = None,
    y: str | None = None,
    chart_type: ChartType | None = None,
    container: ApplicationContainer = Depends(get_container),
) -> HTMLResponse:
    def generate() -> str:
        try:
            return container.output_chart_service.generate(pipeline_id, reference, x, y, chart_type)
        except OutputChartValidationError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except OutputChartNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    return HTMLResponse(_respond(generate))


@router.get("/{pipeline_id}/steps/{step_id}/preview", response_model=StepPreview)
def preview_pipeline_step(
    pipeline_id: str,
    step_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> StepPreview:
    return _respond(lambda: container.pipeline_service.preview_step(pipeline_id, step_id))


@router.get("/{pipeline_id}/steps/{step_id}/csv")
def download_pipeline_step(
    pipeline_id: str,
    step_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> Response:
    frame = _respond(lambda: container.pipeline_service.step_result(pipeline_id, step_id))
    return Response(
        content=frame.to_csv(index=False).encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="step-result.csv"'},
    )


@router.put("/{pipeline_id}/steps/{step_id}", response_model=PipelineState)
def revise_pipeline_step(
    pipeline_id: str,
    step_id: str,
    revision: StepRevision,
    container: ApplicationContainer = Depends(get_container),
) -> PipelineState:
    return _respond(lambda: container.pipeline_service.revise_step(pipeline_id, step_id, revision))

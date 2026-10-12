from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from relatorios_service.common.dependencies import (
    ApplicationContainer,
    get_container,
)
from relatorios_service.schemas import ExportFormat


router = APIRouter()


@router.get("/reports/{report_id}/chart.json")
def download_chart_json(
    report_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> FileResponse:
    path = container.analysis_service.chart_path(report_id, "json")

    if not path.is_file():
        raise HTTPException(status_code=404, detail="Gráfico não encontrado.")

    return FileResponse(
        path,
        filename=path.name,
        media_type="application/json",
    )


@router.get("/reports/{report_id}/chart.html")
def download_chart_html(
    report_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> FileResponse:
    path = container.analysis_service.chart_path(report_id, "html")

    if not path.is_file():
        raise HTTPException(status_code=404, detail="Gráfico não encontrado.")

    return FileResponse(
        path,
        filename=path.name,
        media_type="text/html",
    )


@router.get("/reports/{report_id}/{file_format}")
def download_report(
    report_id: str,
    file_format: ExportFormat,
    container: ApplicationContainer = Depends(get_container),
) -> FileResponse:
    path = container.analysis_service.report_path(report_id, file_format)

    if not path.is_file():
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")

    return FileResponse(
        path,
        filename=path.name,
    )

import json
from io import BytesIO

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from relatorios_service.analysis_service import AnalysisService
from relatorios_service.database import DatabaseEngineFactory
from relatorios_service.file_reader import FileReader
from relatorios_service.schemas import AnalysisRequest, ExportFormat


app = FastAPI(title="API de Relatórios")

file_reader = FileReader()
database_factory = DatabaseEngineFactory()
analysis_service = AnalysisService()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/database/health")
def database_health() -> dict[str, str]:
    try:
        database_factory.test_connection()
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao conectar ao banco: {error}",
        ) from error

    return {
        "database": database_factory.active_database().value,
        "status": "connected",
    }


@app.post("/analytics/question")
def analytics_question(request: AnalysisRequest) -> dict:
    try:
        result = analysis_service.analyze(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao analisar os dados: {error}",
        ) from error

    return result.model_dump(mode="json")


@app.get("/reports/{report_id}/chart.json")
def download_chart_json(report_id: str) -> FileResponse:
    path = analysis_service.chart_path(report_id, "json")

    if not path.is_file():
        raise HTTPException(status_code=404, detail="Gráfico não encontrado.")

    return FileResponse(
        path,
        filename=path.name,
        media_type="application/json",
    )


@app.get("/reports/{report_id}/chart.html")
def download_chart_html(report_id: str) -> FileResponse:
    path = analysis_service.chart_path(report_id, "html")

    if not path.is_file():
        raise HTTPException(status_code=404, detail="Gráfico não encontrado.")

    return FileResponse(
        path,
        filename=path.name,
        media_type="text/html",
    )


@app.get("/reports/{report_id}/{file_format}")
def download_report(
    report_id: str,
    file_format: ExportFormat,
) -> FileResponse:
    path = analysis_service.report_path(report_id, file_format)

    if not path.is_file():
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")

    return FileResponse(
        path,
        filename=path.name,
    )


@app.post("/files/preview")
async def preview_file(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="O arquivo precisa possuir um nome.",
        )

    content = await file.read()

    try:
        dataframe = file_reader.read(
            BytesIO(content),
            file.filename,
        )
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    preview = json.loads(
        dataframe.head(20).to_json(
            orient="records",
            date_format="iso",
        )
    )

    return {
        "filename": file.filename,
        "total_rows": len(dataframe),
        "columns": list(dataframe.columns),
        "preview": preview,
    }

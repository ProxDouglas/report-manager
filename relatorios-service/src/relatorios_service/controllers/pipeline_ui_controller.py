from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from relatorios_service.common.dependencies import ApplicationContainer, get_container


STATIC_DIRECTORY = Path(__file__).resolve().parents[1] / "static"
UI_CACHE_HEADERS = {"Cache-Control": "no-cache"}
router = APIRouter(include_in_schema=False)


class UIStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers.update(UI_CACHE_HEADERS)
        return response


@router.get("/")
def pipeline_ui() -> FileResponse:
    return FileResponse(STATIC_DIRECTORY / "index.html", headers=UI_CACHE_HEADERS)


@router.get("/ui/config")
def ui_configuration(
    container: ApplicationContainer = Depends(get_container),
) -> dict:
    return {
        "max_files": min(container.settings.max_upload_files, 10),
        "max_file_bytes": container.settings.max_upload_bytes,
        "max_batch_bytes": container.settings.max_batch_upload_bytes,
    }

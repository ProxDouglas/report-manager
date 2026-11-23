import asyncio
import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from relatorios_service.common.dependencies import (
    ApplicationContainer,
    build_container,
)
from relatorios_service.controllers import (
    datasets_controller,
    health_controller,
    pipelines_controller,
    pipeline_ui_controller,
)
from relatorios_service.repositories.dataset_repository import DatasetRepository
from relatorios_service.services.pipeline_service import PipelineService


logger = logging.getLogger(__name__)


async def _cleanup_expired_datasets(
    dataset_repository: DatasetRepository,
    pipeline_service: PipelineService,
) -> None:
    while True:
        try:
            await run_in_threadpool(dataset_repository.cleanup_expired)
            await run_in_threadpool(pipeline_service.cleanup_expired)
        except (OSError, ValueError, sqlite3.Error):
            logger.exception("Falha ao remover datasets expirados.")

        await asyncio.sleep(300)


def create_app(container: ApplicationContainer | None = None) -> FastAPI:
    application_container = (
        container if container is not None else build_container()
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        cleanup_task = asyncio.create_task(
            _cleanup_expired_datasets(
                app.state.container.dataset_repository,
                app.state.container.pipeline_service,
            )
        )
        try:
            yield
        finally:
            cleanup_task.cancel()
            try:
                await cleanup_task
            except asyncio.CancelledError:
                pass

    app = FastAPI(title="API de Relatórios", lifespan=lifespan)
    app.state.container = application_container
    app.include_router(health_controller.router)
    app.include_router(datasets_controller.router)
    app.include_router(pipelines_controller.router)
    app.include_router(pipeline_ui_controller.router)
    app.mount("/static", pipeline_ui_controller.UIStaticFiles(directory=pipeline_ui_controller.STATIC_DIRECTORY), name="static")
    return app


@lru_cache(maxsize=1)
def get_app() -> FastAPI:
    return create_app()


# O app é montado só no primeiro acesso: importar o módulo não lê a configuração.
def __getattr__(name: str) -> FastAPI:
    if name == "app":
        return get_app()

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

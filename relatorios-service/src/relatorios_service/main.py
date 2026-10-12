import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from relatorios_service.common.dependencies import (
    ApplicationContainer,
    build_container,
)
from relatorios_service.controllers import (
    analysis_controller,
    datasets_controller,
    health_controller,
    reports_controller,
)
from relatorios_service.repositories.dataset_repository import DatasetRepository


logger = logging.getLogger(__name__)


async def _cleanup_expired_datasets(
    dataset_repository: DatasetRepository,
) -> None:
    while True:
        try:
            dataset_repository.cleanup_expired()
        except (OSError, ValueError):
            logger.exception("Falha ao remover datasets expirados.")

        await asyncio.sleep(300)


def create_app(container: ApplicationContainer | None = None) -> FastAPI:
    application_container = (
        container if container is not None else build_container()
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        cleanup_task = asyncio.create_task(
            _cleanup_expired_datasets(app.state.container.dataset_repository)
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
    app.include_router(analysis_controller.router)
    app.include_router(datasets_controller.router)
    app.include_router(reports_controller.router)
    return app


app = create_app()

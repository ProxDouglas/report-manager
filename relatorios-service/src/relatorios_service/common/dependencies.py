from dataclasses import dataclass

from fastapi import Request

from relatorios_service.config import Settings, settings
from relatorios_service.database import DatabaseEngineFactory
from relatorios_service.repositories.analytics_repository import (
    AnalyticsRepository,
    SqlAlchemyAnalyticsRepository,
)
from relatorios_service.repositories.dataset_repository import (
    DatasetRepository,
    LocalDatasetRepository,
)
from relatorios_service.services.analysis_service import AnalysisService
from relatorios_service.services.dataset_service import DatasetService
from relatorios_service.services.file_reader import FileReader


@dataclass(frozen=True)
class ApplicationContainer:
    settings: Settings
    analytics_repository: AnalyticsRepository
    dataset_repository: DatasetRepository
    analysis_service: AnalysisService
    dataset_service: DatasetService


def build_container(
    configuration: Settings | None = None,
) -> ApplicationContainer:
    active_settings = configuration or settings
    database_factory = DatabaseEngineFactory()
    analytics_repository = SqlAlchemyAnalyticsRepository(database_factory)
    dataset_repository = LocalDatasetRepository(
        active_settings.datasets_directory,
        retention_seconds=active_settings.dataset_retention_seconds,
    )
    file_reader = FileReader(
        max_rows=active_settings.max_dataset_rows,
        max_columns=active_settings.max_dataset_columns,
    )

    return ApplicationContainer(
        settings=active_settings,
        analytics_repository=analytics_repository,
        dataset_repository=dataset_repository,
        analysis_service=AnalysisService(analytics_repository),
        dataset_service=DatasetService(file_reader, dataset_repository),
    )


def get_container(request: Request) -> ApplicationContainer:
    return request.app.state.container

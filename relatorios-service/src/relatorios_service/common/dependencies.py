from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

from relatorios_service.config import Settings, get_settings
from relatorios_service.database import DatabaseEngineFactory
from relatorios_service.llm import create_chat_model
from relatorios_service.metric_catalog import MetricCatalog
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
from relatorios_service.services.report_exporter import ReportExporter


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
    active_settings = configuration or get_settings()
    database_factory = DatabaseEngineFactory(active_settings)
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
        analysis_service=AnalysisService(
            analytics_repository=analytics_repository,
            model=create_chat_model(active_settings),
            catalog=MetricCatalog(),
            exporter=ReportExporter(active_settings.reports_directory),
            max_analysis_rows=active_settings.max_analysis_rows,
            audit_log_path=(
                Path(active_settings.audit_log_file)
                if active_settings.audit_log_enabled
                else None
            ),
        ),
        dataset_service=DatasetService(file_reader, dataset_repository),
    )


def get_container(request: Request) -> ApplicationContainer:
    return request.app.state.container

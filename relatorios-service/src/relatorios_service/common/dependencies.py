from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

from relatorios_service.config import Settings, get_settings
from relatorios_service.llm import create_chat_model
from relatorios_service.repositories.dataset_repository import (
    DatasetRepository,
    LocalDatasetRepository,
)
from relatorios_service.repositories.pipeline_repository import LocalPipelineRepository
from relatorios_service.services.chart_service import ChartBuilder
from relatorios_service.services.dataset_profiler import DatasetProfiler
from relatorios_service.services.dataset_service import DatasetService
from relatorios_service.services.file_reader import FileReader
from relatorios_service.services.output_chart_service import OutputChartService
from relatorios_service.services.pipeline_executor import PipelineExecutor
from relatorios_service.services.pipeline_planner import LLMPipelinePlanner
from relatorios_service.services.pipeline_service import PipelineService


@dataclass(frozen=True)
class ApplicationContainer:
    settings: Settings
    dataset_repository: DatasetRepository
    dataset_service: DatasetService
    pipeline_service: PipelineService
    output_chart_service: OutputChartService


def build_container(
    configuration: Settings | None = None,
) -> ApplicationContainer:
    active_settings = configuration or get_settings()
    dataset_repository = LocalDatasetRepository(
        active_settings.datasets_directory,
        retention_seconds=active_settings.dataset_retention_seconds,
    )
    file_reader = FileReader(
        max_rows=active_settings.max_dataset_rows,
        max_columns=active_settings.max_dataset_columns,
    )
    model = create_chat_model(active_settings)
    pipeline_repository = LocalPipelineRepository(
        Path(active_settings.datasets_directory) / ".pipelines.sqlite3",
        retention_seconds=active_settings.dataset_retention_seconds,
    )

    profiler = DatasetProfiler(file_reader, dataset_repository)

    return ApplicationContainer(
        settings=active_settings,
        dataset_repository=dataset_repository,
        dataset_service=DatasetService(file_reader, dataset_repository),
        output_chart_service=OutputChartService(pipeline_repository, profiler, ChartBuilder()),
        pipeline_service=PipelineService(
            datasets=dataset_repository,
            pipelines=pipeline_repository,
            profiler=profiler,
            planner=LLMPipelinePlanner(model),
            executor=PipelineExecutor(
                max_rows=active_settings.max_dataset_rows,
                max_columns=active_settings.max_dataset_columns,
            ),
        ),
    )


def get_container(request: Request) -> ApplicationContainer:
    return request.app.state.container

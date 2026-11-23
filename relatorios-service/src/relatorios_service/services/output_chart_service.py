import pandas as pd
import plotly.io as pio

from relatorios_service.pipeline_schemas import PipelineStatus
from relatorios_service.repositories.pipeline_repository import PipelineRepository
from relatorios_service.schemas import ChartType, ChartSpec, ChartSeries
from relatorios_service.services.chart_service import ChartBuilder
from relatorios_service.services.dataset_profiler import DatasetProfiler
from relatorios_service.services.pipeline_service import PipelineConflictError


class OutputChartValidationError(ValueError):
    pass


class OutputChartNotFoundError(FileNotFoundError):
    pass


class OutputChartService:
    def __init__(
        self, pipelines: PipelineRepository, profiler: DatasetProfiler, builder: ChartBuilder,
    ) -> None:
        self.pipelines = pipelines
        self.profiler = profiler
        self.builder = builder

    def generate(
        self, pipeline_id: str, reference: str, x: str | None = None,
        y: str | None = None, chart_type: ChartType | None = None,
    ) -> str:
        state = self.pipelines.get(pipeline_id)
        if state.status != PipelineStatus.COMPLETED:
            raise PipelineConflictError("Conclua o tratamento antes de gerar o gráfico.")
        output = next((item for item in state.outputs if item.reference == reference), None)
        if output is None:
            raise OutputChartNotFoundError("Saída não encontrada.")
        planned = next((item for item in state.plan.charts if item.reference == reference), None)
        if planned is not None:
            if x is None:
                x = planned.x
            if y is None:
                y = planned.y
            if chart_type is None:
                chart_type = ChartType(planned.chart_type.value)
        if chart_type is None:
            chart_type = ChartType.BAR
        if x not in output.columns or y not in output.columns or chart_type == ChartType.TABLE:
            raise OutputChartValidationError("Selecione colunas e tipo de gráfico válidos.")
        try:
            frame, _ = self.profiler.load(output.dataset_id)
            values = pd.to_numeric(frame[y], errors="coerce")
            if values.isna().any() or frame.empty:
                raise OutputChartValidationError("A série deve conter valores numéricos sem nulos.")
            frame[y] = values
            chart = self.builder.build(frame, ChartSpec(
                x=x, chart_type=chart_type, series=[ChartSeries(column=y)],
            ))
            if chart is None:
                raise OutputChartValidationError("Não foi possível gerar o gráfico com estas colunas.")
            return pio.to_html(chart, full_html=True, include_plotlyjs=True)
        except FileNotFoundError as error:
            raise OutputChartNotFoundError("Dataset não encontrado ou expirado.") from error

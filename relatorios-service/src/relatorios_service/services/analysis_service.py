import time
import traceback
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
from langchain_openai import ChatOpenAI

from relatorios_service.database import DatabaseType
from relatorios_service.domain.charts import plan_chart_spec
from relatorios_service.domain.composition import (
    ComponentExecution,
    component_warnings,
    compose_components,
)
from relatorios_service.domain.measures import (
    derive_composed_measures,
    derive_measures,
    normalize_measure_columns,
    validate_result,
)
from relatorios_service.domain.planning import normalize_plan
from relatorios_service.domain.rules import resolve_tables, validate_plan
from relatorios_service.metric_catalog import MetricCatalog
from relatorios_service.repositories.analytics_repository import (
    AnalyticsRepository,
    AnalyticsSession,
)
from relatorios_service.schemas import (
    AnalysisComponent,
    AnalysisPlan,
    AnalysisRequest,
    AnalysisResult,
    ExportFormat,
)
from relatorios_service.services.analysis_planner import AnalysisPlanner
from relatorios_service.services.answer_writer import AnswerWriter, to_records
from relatorios_service.services.audit_log import AuditTrail, elapsed_ms
from relatorios_service.services.chart_service import ChartBuilder
from relatorios_service.services.normalization import DataNormalizer
from relatorios_service.services.report_exporter import ReportExporter
from relatorios_service.services.schema_context import build_schema_context
from relatorios_service.services.sql_generator import SqlGenerator
from relatorios_service.sql_safety import SqlSafetyValidator


class AnalysisService:
    def __init__(
        self,
        analytics_repository: AnalyticsRepository,
        model: ChatOpenAI,
        catalog: MetricCatalog,
        exporter: ReportExporter,
        max_analysis_rows: int,
        audit_log_path: Path | None = None,
    ) -> None:
        self.analytics_repository = analytics_repository
        self.catalog = catalog
        self.exporter = exporter
        self.max_analysis_rows = max_analysis_rows
        self.audit_log_path = audit_log_path
        self.chart_builder = ChartBuilder()
        self.normalizer = DataNormalizer()
        self.planner = AnalysisPlanner(model, catalog)
        self.sql_generator = SqlGenerator(model, SqlSafetyValidator())
        self.answers = AnswerWriter(model)

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        report_id = uuid.uuid4().hex
        audit = AuditTrail(self.audit_log_path, report_id)
        started = time.perf_counter()
        audit.event("analysis.started", request=request.model_dump(mode="json"))

        try:
            result = self._analyze(request, report_id, audit)
        except Exception as error:
            audit.event(
                "analysis.failed",
                error_type=type(error).__name__,
                error=str(error),
                traceback="".join(traceback.format_exception(error)),
                duration_ms=elapsed_ms(started),
            )
            raise

        audit.event(
            "analysis.completed",
            row_count=result.row_count,
            truncated=result.truncated,
            files=result.files,
            duration_ms=elapsed_ms(started),
        )
        return result

    def _analyze(
        self,
        request: AnalysisRequest,
        report_id: str,
        audit: AuditTrail,
    ) -> AnalysisResult:
        plan = self.planner.create_plan(request)
        plan = normalize_plan(plan, request)
        audit.event("plan.created", plan=plan.model_dump(mode="json"))

        executions: list[ComponentExecution] = []

        with self.analytics_repository.open_session() as session:
            for component in plan.components:
                executions.append(
                    self._run_component(
                        request,
                        component,
                        session.database,
                        session,
                        audit,
                    )
                )

        dataframe = compose_components(executions, plan)
        warnings = component_warnings(executions)
        sqls = [execution.sql for execution in executions]
        dataframe = derive_composed_measures(dataframe, plan)
        composed_rows = len(dataframe)
        truncated = composed_rows > self.max_analysis_rows
        if truncated:
            dataframe = dataframe.head(self.max_analysis_rows)

        chart = self._build_chart(request, plan, dataframe)
        audit.event(
            "analysis.composed",
            rows=composed_rows,
            returned_rows=len(dataframe),
            truncated=truncated,
            warnings=warnings,
            chart=chart is not None,
        )
        formats = self._export_formats(request, plan)
        files = self.exporter.export(report_id, dataframe, formats, chart)
        answer_started = time.perf_counter()
        answer = self.answers.create_answer(
            request,
            plan,
            dataframe,
            truncated,
            warnings,
        )
        audit.event(
            "answer.created",
            answer_chars=len(answer),
            duration_ms=elapsed_ms(answer_started),
        )
        data = to_records(dataframe)

        return AnalysisResult(
            report_id=report_id,
            answer=answer,
            plan=plan,
            sql=sqls[0],
            sqls=sqls,
            row_count=len(dataframe),
            truncated=truncated,
            data=data,
            chart=chart,
            files=files,
            warnings=warnings,
        )

    def _run_component(
        self,
        request: AnalysisRequest,
        component: AnalysisComponent,
        database: DatabaseType,
        session: AnalyticsSession,
        audit: AuditTrail,
    ) -> ComponentExecution:
        metric = self.catalog.get(component.metric)
        validate_plan(component, metric)
        selected_tables = resolve_tables(component, metric)
        schema = build_schema_context(session, metric, selected_tables)
        sql, sql_plan = self.sql_generator.validated_plan(
            request,
            component,
            metric,
            schema,
            database,
            audit,
        )
        query_started = time.perf_counter()
        dataframe = self._execute_query(
            session,
            sql,
            sql_plan.parameters,
        )
        audit.event(
            "query.executed",
            component=component.id,
            rows=len(dataframe),
            duration_ms=elapsed_ms(query_started),
        )
        dataframe = normalize_measure_columns(
            dataframe,
            component.measures,
        )
        normalization = self.normalizer.normalize(
            dataframe,
            metric,
            component.measures,
            component.dimensions,
        )
        dataframe = normalization.dataframe
        validate_result(dataframe, component)
        dataframe = derive_measures(
            dataframe,
            component.measures,
        )

        return ComponentExecution(
            component=component,
            dataframe=dataframe,
            sql=sql,
            warnings=normalization.warnings,
        )

    def _execute_query(
        self,
        session: AnalyticsSession,
        sql: str,
        parameters: dict[str, Any],
    ) -> pd.DataFrame:
        return session.execute_read(sql, parameters)

    def _build_chart(
        self,
        request: AnalysisRequest,
        plan: AnalysisPlan,
        dataframe: pd.DataFrame,
    ) -> dict[str, Any] | None:
        return self.chart_builder.build(
            dataframe,
            plan_chart_spec(request, plan, dataframe),
        )

    def _export_formats(
        self,
        request: AnalysisRequest,
        plan: AnalysisPlan,
    ) -> list[ExportFormat]:
        formats = list(request.export_formats)

        for file_format in plan.requested_exports:
            if file_format not in formats:
                formats.append(file_format)

        return formats

    def report_path(
        self,
        report_id: str,
        file_format: ExportFormat,
    ):
        return self.exporter.path_for(report_id, file_format)

    def chart_path(self, report_id: str, extension: str):
        return self.exporter.chart_path(report_id, extension)

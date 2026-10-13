import json

from langchain_openai import ChatOpenAI

from relatorios_service.database import DatabaseType
from relatorios_service.domain.rules import (
    resolve_tables,
    validate_sql_semantics,
)
from relatorios_service.schemas import (
    AnalysisComponent,
    AnalysisRequest,
    MetricDefinition,
    SqlPlan,
)
from relatorios_service.services.audit_log import AuditTrail
from relatorios_service.services.parameter_binder import ParameterBinder
from relatorios_service.sql_safety import SqlSafetyValidator
from relatorios_service.prompts import load_prompt


class SqlGenerator:
    """Gera, valida e corrige a consulta SQL de um componente."""

    def __init__(
        self,
        model: ChatOpenAI,
        sql_validator: SqlSafetyValidator,
    ) -> None:
        self.model = model
        self.sql_validator = sql_validator
        self.binder = ParameterBinder(sql_validator)

    def create_plan(
        self,
        request: AnalysisRequest,
        component: AnalysisComponent,
        metric: MetricDefinition,
        schema: str,
        database: DatabaseType,
        validation_error: str | None = None,
    ) -> SqlPlan:
        correction_instructions = ""
        native_table_functions = self.sql_validator.native_table_functions(
            database
        )

        if native_table_functions:
            native_sql_rules = (
                "Recursos nativos de tabela permitidos para este banco: "
                f"{', '.join(native_table_functions)}. "
                "Use somente esses recursos e não os trate como tabelas "
                "do catálogo."
            )
        else:
            native_sql_rules = (
                "Nenhum recurso nativo de tabela está liberado para este "
                "banco."
            )

        if validation_error:
            correction_instructions = f"""
A tentativa anterior foi rejeitada pela validação de segurança.

Erro retornado: {validation_error}

Gere uma nova consulta corrigida. Não repita a tabela ou operação que causou
o erro e mantenha todas as regras de segurança abaixo.
"""

        prompt = load_prompt("sql_plan").format(
            plan_schema_json=json.dumps(SqlPlan.model_json_schema(), ensure_ascii=False),
            database=database.value,
            metric_json=metric.model_dump_json(ensure_ascii=False),
            component_json=component.model_dump_json(ensure_ascii=False),
            question=request.question,
            schema=schema,
            native_sql_rules=native_sql_rules,
            correction_instructions=correction_instructions,
        )
        structured_model = self.model.with_structured_output(
            SqlPlan,
            method="json_mode",
        )
        result = structured_model.invoke(prompt)
        return SqlPlan.model_validate(result)

    def validated_plan(
        self,
        request: AnalysisRequest,
        component: AnalysisComponent,
        metric: MetricDefinition,
        schema: str,
        database: DatabaseType,
        audit: AuditTrail | None = None,
    ) -> tuple[str, SqlPlan]:
        if audit is None:
            audit = AuditTrail.disabled()

        sql_plan = self.create_plan(
            request,
            component,
            metric,
            schema,
            database,
        )

        for attempt in range(2):
            try:
                sql = self.sql_validator.validate(
                    sql_plan.sql,
                    resolve_tables(component, metric),
                    metric.allowed_columns,
                    database=database,
                )
                sql_plan = self.binder.prepare_sql_plan_parameters(
                    sql_plan,
                    component,
                    metric,
                    sql,
                )
                self.binder.validate_component_filter_parameters(
                    sql_plan,
                    component,
                    metric,
                    sql,
                )
                self.sql_validator.validate_parameters(
                    sql,
                    sql_plan.parameters,
                    forbidden_values=self.binder.component_filter_values(component),
                    require_parameter=self.binder.component_requires_parameters(
                        component
                    ),
                )
                validate_sql_semantics(
                    sql,
                    metric,
                    component.measures,
                )
                audit.event(
                    "sql.validated",
                    component=component.id,
                    attempts=attempt + 1,
                    sql=sql,
                    parameters=sql_plan.parameters,
                )
                return sql, sql_plan
            except ValueError as error:
                audit.event(
                    "sql.rejected",
                    component=component.id,
                    attempt=attempt + 1,
                    sql=sql_plan.sql,
                    error=str(error),
                )
                if attempt == 1:
                    raise

                sql_plan = self.create_plan(
                    request,
                    component,
                    metric,
                    schema,
                    database,
                    validation_error=str(error),
                )

        raise ValueError("Não foi possível validar o plano SQL.")

import re
from datetime import date, datetime
from typing import Any

from relatorios_service.domain.period import period_values
from relatorios_service.schemas import (
    AnalysisComponent,
    MetricDefinition,
    SemanticValueType,
    SqlPlan,
)
from relatorios_service.sql_safety import SqlSafetyValidator


class ParameterBinder:
    """Prepara e converte os parâmetros nomeados da consulta."""

    def __init__(self, sql_validator: SqlSafetyValidator) -> None:
        self.sql_validator = sql_validator

    def prepare_sql_plan_parameters(
        self,
        sql_plan: SqlPlan,
        component: AnalysisComponent,
        metric: MetricDefinition,
        sql: str,
    ) -> SqlPlan:
        mappings_by_parameter = {
            mapping.parameter: mapping
            for mapping in metric.semantic_mappings.values()
            if mapping.parameter
        }
        parameter_names = self.sql_validator.parameter_names(sql)
        period_parameters = {}

        if component.period is not None:
            period_parameters = {
                name: value
                for name, value in (
                    ("filter_period_start", component.period.start),
                    ("filter_period_end", component.period.end),
                )
                if value is not None and name in parameter_names
            }

        parameters = {
            **sql_plan.parameters,
            **period_parameters,
        }

        for name, value in parameters.items():
            mapping = mappings_by_parameter.get(name)
            value_type = mapping.value_type if mapping else None

            if value_type is None:
                value_type = self.infer_parameter_type(name)

            parameters[name] = self.convert_parameter_value(
                value,
                value_type,
                name,
            )

        return sql_plan.model_copy(update={"parameters": parameters})

    def validate_component_filter_parameters(
        self,
        sql_plan: SqlPlan,
        component: AnalysisComponent,
        metric: MetricDefinition,
        sql: str,
    ) -> None:
        mappings = metric.semantic_mappings
        parameter_names = self.sql_validator.parameter_names(sql)

        for filter_name, filter_value in component.filters.items():
            mapping = mappings.get(filter_name)

            if mapping is None or mapping.parameter is None:
                continue

            parameter_pattern = re.compile(
                rf"{re.escape(mapping.parameter)}(?:_\d+)?\Z"
            )
            component_parameters = {
                name
                for name in parameter_names
                if parameter_pattern.fullmatch(name)
            }

            if not component_parameters:
                raise ValueError(
                    f"O SQL do componente {component.id} não usa o "
                    f"parâmetro {mapping.parameter} do filtro "
                    f"{filter_name}."
                )

            expected_values = {
                self.normalize_filter_value(
                    self.convert_parameter_value(
                        value,
                        mapping.value_type,
                        mapping.parameter,
                    )
                )
                for value in self.flatten_values(filter_value)
            }

            for parameter_name in component_parameters:
                if parameter_name not in sql_plan.parameters:
                    continue

                actual_values = self.flatten_values(
                    sql_plan.parameters[parameter_name]
                )
                if any(
                    self.normalize_filter_value(value) not in expected_values
                    for value in actual_values
                ):
                    raise ValueError(
                        f"O parâmetro {parameter_name} não corresponde ao "
                        f"filtro {filter_name} do componente {component.id}. "
                        "Use somente os valores definidos nesse componente."
                    )

    def normalize_filter_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().casefold()

        return value

    def infer_parameter_type(
        self,
        parameter_name: str,
    ) -> SemanticValueType | None:
        tokens = set(re.split(r"[^a-z0-9]+", parameter_name.casefold()))

        if tokens & {"date", "start", "end", "period"}:
            return SemanticValueType.DATE

        return None

    def convert_parameter_value(
        self,
        value: Any,
        value_type: SemanticValueType | None,
        parameter_name: str,
    ) -> Any:
        if value is None or value_type is None:
            return value

        if value_type == SemanticValueType.DATE:
            if isinstance(value, datetime):
                return value.date()

            if isinstance(value, date):
                return value

            for date_format in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(
                        str(value),
                        date_format,
                    ).date()
                except ValueError:
                    continue

            try:
                return datetime.fromisoformat(str(value)).date()
            except ValueError:
                pass

            raise ValueError(
                f"O parâmetro {parameter_name} não contém uma data válida."
            )

        if value_type == SemanticValueType.NUMBER:
            try:
                return float(value)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"O parâmetro {parameter_name} não contém um número válido."
                ) from error

        if value_type == SemanticValueType.BOOLEAN:
            if isinstance(value, bool):
                return value

            normalized = str(value).strip().casefold()
            if normalized in {"true", "1", "sim", "yes"}:
                return True
            if normalized in {"false", "0", "não", "nao", "no"}:
                return False

            raise ValueError(
                f"O parâmetro {parameter_name} não contém um booleano válido."
            )

        return value

    def component_requires_parameters(
        self,
        component: AnalysisComponent,
    ) -> bool:
        if component.filters:
            return True

        if component.period is None:
            return False

        return bool(period_values(component.period))

    def component_filter_values(
        self,
        component: AnalysisComponent,
    ) -> list[Any]:
        values: list[Any] = []

        for value in component.filters.values():
            values.extend(self.flatten_values(value))

        if component.period:
            values.extend(period_values(component.period))

        return values

    def flatten_values(self, value: Any) -> list[Any]:
        if isinstance(value, dict):
            flattened: list[Any] = []

            for nested_value in value.values():
                flattened.extend(self.flatten_values(nested_value))

            return flattened

        if isinstance(value, (list, tuple, set)):
            flattened = []

            for nested_value in value:
                flattened.extend(self.flatten_values(nested_value))

            return flattened

        return [value]

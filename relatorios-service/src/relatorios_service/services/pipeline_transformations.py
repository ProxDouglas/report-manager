import math
import operator
from typing import Generic, Protocol, TypeVar

import pandas as pd
from pandas.api.types import is_bool_dtype, is_numeric_dtype, is_string_dtype

from relatorios_service.pipeline_schemas import (
    AggregateFunction, AggregateMetric, AggregateStep, BucketScale, BucketStep,
    CastStep, ColumnStep, ErrorPolicy, ExtractMeasurementsStep, FillNullsStep, FillStrategy, FilterCondition,
    FilterMatch, FilterOperator, FilterStep, InputStep, NumberFormat, Operation,
    SplitExplodeStep, TrimStep, ValueType,
)

from relatorios_service.services.file_reader import FileReader
from relatorios_service.services.measurement_parser import MeasurementParser
from relatorios_service.services.pipeline_errors import PipelineExecutionError


StepT = TypeVar("StepT", bound=InputStep, contravariant=True)


class Transformation(Protocol[StepT]):
    """Contrato para prever colunas e executar uma transformação declarativa."""

    def columns(self, step: StepT, columns: list[str]) -> list[str]: ...

    def apply(self, frame: pd.DataFrame, step: StepT) -> pd.DataFrame: ...


def _validate_columns(required: list[str], columns: list[str]) -> None:
    if not set(required).issubset(columns):
        raise ValueError("A etapa referencia uma coluna inexistente.")


class FilterTransformation(Transformation[FilterStep]):
    comparisons = {
        FilterOperator.EQ: operator.eq,
        FilterOperator.NE: operator.ne,
        FilterOperator.GT: operator.gt,
        FilterOperator.GE: operator.ge,
        FilterOperator.LT: operator.lt,
        FilterOperator.LE: operator.le,
    }
    def columns(self, step: FilterStep, columns: list[str]) -> list[str]:
        _validate_columns([condition.column for condition in step.conditions], columns)
        return list(columns)

    def apply(self, frame: pd.DataFrame, step: FilterStep) -> pd.DataFrame:
        masks = [self._condition(frame[condition.column], condition) for condition in step.conditions]
        combined = masks[0]
        for mask in masks[1:]:
            if step.match == FilterMatch.ALL:
                combined = combined & mask
            else:
                combined = combined | mask
        return frame.loc[combined]

    def _condition(self, values: pd.Series, condition: FilterCondition) -> pd.Series:
        if condition.operator == FilterOperator.IS_NULL:
            return values.isna()
        if condition.operator == FilterOperator.NOT_NULL:
            return values.notna()
        if condition.operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
            mask = values.isin(condition.values)
            if condition.operator == FilterOperator.NOT_IN:
                mask = ~mask
        else:
            mask = self.comparisons[condition.operator](values, condition.values[0])
        # Nulos só participam de filtros explícitos is_null/not_null.
        return mask.fillna(False) & values.notna()



class SplitExplodeTransformation(Transformation[SplitExplodeStep]):
    def __init__(self, max_rows: int) -> None:
        self.max_rows = max_rows

    def columns(self, step: SplitExplodeStep, columns: list[str]) -> list[str]:
        _validate_columns([step.column], columns)
        return list(columns)

    def apply(self, frame: pd.DataFrame, step: SplitExplodeStep) -> pd.DataFrame:
        values = frame[step.column]
        if not is_string_dtype(values):
            raise ValueError("A separação exige texto.")
        # Estimar antes de criar listas ou materializar a expansão.
        count = values.dropna().map(lambda value: value.count(step.separator) + 1).sum()
        if int(count) + int(values.isna().sum()) > self.max_rows:
            raise ValueError("A expansão excederia o limite de linhas.")
        frame[step.column] = values.str.split(step.separator, regex=False)
        frame = frame.explode(step.column, ignore_index=True)
        if step.strip:
            frame[step.column] = frame[step.column].str.strip()
        return frame



class ExtractMeasurementsTransformation(Transformation[ExtractMeasurementsStep]):
    def columns(self, step: ExtractMeasurementsStep, columns: list[str]) -> list[str]:
        _validate_columns([step.column], columns)
        generated = [
            f"{step.column}_{component}_{index}"
            for index in range(1, step.pairs + 1)
            for component in ("value", "unit")
        ]
        if set(generated).intersection(columns):
            raise ValueError("As colunas de medidas devem ter nomes novos.")
        return [*columns, *generated]

    def apply(self, frame: pd.DataFrame, step: ExtractMeasurementsStep) -> pd.DataFrame:
        self.columns(step, list(frame.columns))
        values = frame[step.column]
        if not is_string_dtype(values):
            raise ValueError("A extração de medidas exige texto.")
        parser = MeasurementParser()
        rows = []
        for value in values:
            pairs = []
            if pd.notna(value):
                pairs = parser.parse(value, step.number_format)
                if pairs is None or len(pairs) > step.pairs:
                    if step.errors == ErrorPolicy.FAIL:
                        raise ValueError("Há medidas incompatíveis com o formato ou quantidade de pares.")
                    pairs = []
            rows.append(pairs)
        for index in range(step.pairs):
            numbers = []
            units = []
            for pairs in rows:
                numeric, unit = pd.NA, pd.NA
                if index < len(pairs):
                    numeric, unit = pairs[index]
                numbers.append(numeric)
                units.append(unit)
            frame[f"{step.column}_value_{index + 1}"] = pd.array(numbers, dtype="Float64")
            frame[f"{step.column}_unit_{index + 1}"] = pd.array(units, dtype="string")
        return frame


class AggregateTransformation(Transformation[AggregateStep]):
    numeric_functions = {
        AggregateFunction.SUM, AggregateFunction.MEAN, AggregateFunction.MEDIAN,
        AggregateFunction.MIN, AggregateFunction.MAX,
    }

    def columns(self, step: AggregateStep, columns: list[str]) -> list[str]:
        required = step.group_by + [metric.column for metric in step.metrics if metric.column is not None]
        _validate_columns(required, columns)
        return step.group_by + [metric.alias for metric in step.metrics]

    def apply(self, frame: pd.DataFrame, step: AggregateStep) -> pd.DataFrame:
        for metric in step.metrics:
            if metric.function in self.numeric_functions:
                values = frame[metric.column]
                if not is_numeric_dtype(values) or is_bool_dtype(values):
                    raise ValueError("Converta as métricas para número antes de agregar.")
        if not step.group_by:
            return pd.DataFrame([{
                metric.alias: self._metric(frame, metric)
                for metric in step.metrics
            }])
        grouped = frame.groupby(step.group_by, dropna=False, observed=True, sort=False)
        result = grouped.size().to_frame("__size__").iloc[:, :0]
        for metric in step.metrics:
            if metric.function == AggregateFunction.SIZE:
                result[metric.alias] = grouped.size()
            elif metric.function == AggregateFunction.SUM:
                result[metric.alias] = grouped[metric.column].sum(min_count=1)
            else:
                result[metric.alias] = getattr(grouped[metric.column], metric.function.value)()
        return result.reset_index()

    def _metric(self, frame: pd.DataFrame, metric: AggregateMetric):
        if metric.function == AggregateFunction.SIZE:
            return len(frame)
        if metric.function == AggregateFunction.SUM:
            return frame[metric.column].sum(min_count=1)
        return getattr(frame[metric.column], metric.function.value)()



class BucketTransformation(Transformation[BucketStep]):
    def columns(self, step: BucketStep, columns: list[str]) -> list[str]:
        if step.output_column in columns:
            raise ValueError("A coluna de faixas deve ter um nome novo.")
        _validate_columns([step.column], columns)
        return [*columns, step.output_column]

    def apply(self, frame: pd.DataFrame, step: BucketStep) -> pd.DataFrame:
        original = frame[step.column]
        values = original
        if step.scale == BucketScale.PERCENT_TEXT:
            text = original.astype("string").str.strip()
            if (original.notna() & ~text.str.endswith("%", na=False)).any():
                raise ValueError("Percentuais textuais exigem o sufixo %.")
            values = text.str.removesuffix("%").str.strip().str.replace(",", ".", regex=False)
        values = pd.to_numeric(values, errors="coerce")
        if (original.notna() & values.isna()).any() or is_bool_dtype(original):
            raise ValueError("As faixas exigem valores numéricos válidos.")
        if step.scale == BucketScale.FRACTION:
            values = values * 100
        outside = values.notna() & ~values.between(step.edges[0], step.edges[-1])
        if outside.any():
            raise ValueError("Há valores fora dos limites das faixas.")
        buckets = pd.cut(values, bins=step.edges, labels=step.labels, right=False)
        # Intervalos [início, fim), com o último limite incluído na última faixa.
        buckets = buckets.mask(values.eq(step.edges[-1]).fillna(False), step.labels[-1])
        frame[step.output_column] = buckets
        return frame


ColumnStepT = TypeVar("ColumnStepT", bound=ColumnStep)


class ColumnTransformation(Generic[ColumnStepT]):
    def columns(self, step: ColumnStepT, columns: list[str]) -> list[str]:
        _validate_columns(step.columns, columns)
        return list(columns)


class TrimTransformation(ColumnTransformation[TrimStep], Transformation[TrimStep]):
    def apply(self, frame: pd.DataFrame, step: TrimStep) -> pd.DataFrame:
        for column in step.columns:
            if not pd.api.types.is_string_dtype(frame[column]):
                raise PipelineExecutionError("trim exige colunas de texto.")
            frame[column] = frame[column].str.strip()
        return frame


class CastTransformation(ColumnTransformation[CastStep], Transformation[CastStep]):
    def apply(self, frame: pd.DataFrame, step: CastStep) -> pd.DataFrame:
        for column in step.columns:
            original = frame[column]
            if step.target == ValueType.TEXT:
                converted = original.astype("string")
            elif step.target == ValueType.DATE:
                converted = pd.to_datetime(original, format=step.date_format.value, errors="coerce", exact=True)
            elif step.target == ValueType.BOOLEAN:
                converted = original.astype("string").str.casefold().map(FileReader.boolean_values).astype("boolean")
            else:
                values = original.astype("string")
                if step.strip_percent:
                    text = values.str.strip()
                    values = text.str.removesuffix("%").str.strip().where(text.str.endswith("%"))
                if step.number_format == NumberFormat.BRAZILIAN:
                    values = values.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
                converted = pd.to_numeric(values, errors="coerce")
                converted = converted.mask(~converted.map(
                    lambda value: pd.isna(value) or math.isfinite(value),
                ), pd.NA)
                if step.target == ValueType.INTEGER:
                    converted = converted.mask(converted % 1 != 0, pd.NA).astype("Int64")
                else:
                    converted = converted.astype("Float64")
            invalid = original.notna() & converted.isna()
            if invalid.any() and step.errors == ErrorPolicy.FAIL:
                raise PipelineExecutionError("A conversão encontrou valores incompatíveis com o tipo ou formato escolhido.")
            frame[column] = converted
        return frame


class FillNullsTransformation(ColumnTransformation[FillNullsStep], Transformation[FillNullsStep]):
    def apply(self, frame: pd.DataFrame, step: FillNullsStep) -> pd.DataFrame:
        for column in step.columns:
            values = frame[column]
            if not values.isna().any():
                continue
            if step.strategy == FillStrategy.MODE:
                modes = values.mode()
                if len(modes) != 1:
                    raise PipelineExecutionError("O preenchimento por moda exige um único valor mais frequente.")
                replacement = modes.iloc[0]
            else:
                if not is_numeric_dtype(values.dtype) or pd.api.types.is_bool_dtype(values.dtype):
                    raise PipelineExecutionError("A estratégia de preenchimento exige uma coluna numérica.")
                replacement = 0
                if step.strategy == FillStrategy.MEAN:
                    replacement = values.mean()
                elif step.strategy == FillStrategy.MEDIAN:
                    replacement = values.median()
                if pd.isna(replacement):
                    raise PipelineExecutionError("Não é possível preencher usando uma coluna inteiramente nula.")
                if pd.api.types.is_integer_dtype(values.dtype) and float(replacement) % 1:
                    values = values.astype("Float64")
            frame[column] = values.fillna(replacement)
        return frame


class PipelineTransformations:
    """Registro das transformações declarativas disponíveis no pipeline."""

    def __init__(self, max_rows: int) -> None:
        self._transformations = {
            Operation.TRIM: TrimTransformation(),
            Operation.CAST: CastTransformation(),
            Operation.FILL_NULLS: FillNullsTransformation(),
            Operation.FILTER: FilterTransformation(),
            Operation.SPLIT_EXPLODE: SplitExplodeTransformation(max_rows),
            Operation.AGGREGATE: AggregateTransformation(),
            Operation.BUCKET: BucketTransformation(),
            Operation.EXTRACT_MEASUREMENTS: ExtractMeasurementsTransformation(),
        }
        self.operations = {
            operation: transformation.apply
            for operation, transformation in self._transformations.items()
        }

    def columns(self, step: InputStep, columns: list[str]) -> list[str]:
        return self._transformations[step.operation].columns(step, columns)

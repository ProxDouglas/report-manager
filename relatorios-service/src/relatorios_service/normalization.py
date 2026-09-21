import json
import math
import unicodedata
from dataclasses import dataclass
from typing import Any

import pandas as pd

from relatorios_service.schemas import (
    DataErrorPolicy,
    DataParser,
    MeasureDefinition,
    MetricDefinition,
)


WEEKDAY_NAMES = (
    "segunda",
    "terca",
    "quarta",
    "quinta",
    "sexta",
    "sabado",
    "domingo",
)


@dataclass
class NormalizationResult:
    dataframe: pd.DataFrame
    warnings: list[dict[str, Any]]


class DataNormalizationError(ValueError):
    pass


class DataNormalizer:
    def normalize(
        self,
        dataframe: pd.DataFrame,
        metric: MetricDefinition,
        selected_measures: list[str] | None = None,
        dimensions: list[str] | None = None,
    ) -> NormalizationResult:
        result = dataframe.copy()
        warnings: list[dict[str, Any]] = []
        measure_keys = selected_measures

        if measure_keys is None:
            measure_keys = list(metric.measures)

        for measure_key in measure_keys:
            definition = metric.measures.get(measure_key)

            if definition is None:
                continue

            if definition.parser is DataParser.PASSTHROUGH:
                continue

            result, measure_warnings = self._normalize_measure(
                result,
                measure_key,
                definition,
                dimensions,
            )
            warnings.extend(measure_warnings)

        return NormalizationResult(result, warnings)

    def _normalize_measure(
        self,
        dataframe: pd.DataFrame,
        measure_key: str,
        definition: MeasureDefinition,
        dimensions: list[str] | None,
    ) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
        raw_column = definition.raw_alias or definition.column
        raw_column = self._find_column(dataframe, raw_column)

        if raw_column is None:
            raise DataNormalizationError(
                f"A coluna bruta da medida {measure_key} não foi retornada "
                "pelo SQL."
            )

        date_column = None

        if definition.parser is DataParser.WEEKLY_24H_JSON:
            date_column = self._find_column(
                dataframe,
                definition.date_alias,
            )

            if date_column is None:
                raise DataNormalizationError(
                    f"A medida {measure_key} exige uma coluna de data para "
                    "expandir a escala semanal."
                )

        values: list[float] = []
        valid_positions: list[int] = []
        warnings: list[dict[str, Any]] = []

        for position, (_, row) in enumerate(dataframe.iterrows()):
            try:
                parsed_value = self._parse_value(
                    row[raw_column],
                    row,
                    date_column,
                    definition,
                )
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                if definition.on_error is DataErrorPolicy.FAIL:
                    raise DataNormalizationError(
                        f"Não foi possível normalizar {measure_key} na "
                        f"linha {position}: {error}"
                    ) from error

                warnings.append(
                    {
                        "measure": measure_key,
                        "row_number": position,
                        "parser": definition.parser.value,
                        "message": str(error),
                    }
                )
                continue

            valid_positions.append(position)
            values.append(parsed_value)

        normalized = dataframe.iloc[valid_positions].copy()
        normalized[measure_key] = values

        if definition.parser is DataParser.WEEKLY_24H_JSON:
            normalized = self._aggregate_measure(
                normalized,
                raw_column,
                measure_key,
                dimensions,
            )

        return normalized, warnings

    def _parse_value(
        self,
        value: Any,
        row: pd.Series,
        date_column: str | None,
        definition: MeasureDefinition,
    ) -> float:
        if definition.parser is DataParser.NUMERIC:
            return self._number(value)

        if definition.parser is DataParser.NUMERIC_TEXT:
            return self._number(value)

        if definition.parser is DataParser.COMMA_SEPARATED_24H:
            return self._parse_comma_separated_hours(value, definition)

        if definition.parser is DataParser.WEEKLY_24H_JSON:
            if date_column is None:
                raise ValueError("A coluna de data não foi configurada.")

            return self._parse_weekly_schedule(
                value,
                row[date_column],
                definition,
            )

        raise ValueError(
            f"Parser não suportado: {definition.parser.value}"
        )

    def _parse_weekly_schedule(
        self,
        value: Any,
        date_value: Any,
        definition: MeasureDefinition,
    ) -> float:
        payload = self._json_object(value)
        schedule = self._path_value(payload, definition.json_path)

        if not isinstance(schedule, dict):
            raise ValueError("O caminho JSON da demanda não é um objeto.")

        required_days = definition.required_days or list(WEEKDAY_NAMES)
        normalized_schedule = {
            self._normalize_key(key): day_values
            for key, day_values in schedule.items()
        }
        normalized_required_days = [
            self._normalize_key(day)
            for day in required_days
        ]
        missing_days = [
            day
            for day in normalized_required_days
            if day not in normalized_schedule
        ]

        if missing_days:
            names = ", ".join(missing_days)
            raise ValueError(f"Dias ausentes na escala: {names}.")

        parsed_date = pd.to_datetime(date_value, errors="coerce")

        if pd.isna(parsed_date):
            raise ValueError("Data inválida para a escala semanal.")

        day_name = WEEKDAY_NAMES[parsed_date.dayofweek]
        values = normalized_schedule.get(day_name)
        expected_hours = definition.hours_per_day or 24

        if not isinstance(values, list):
            raise ValueError(f"A escala de {day_name} não é uma lista.")

        if len(values) != expected_hours:
            raise ValueError(
                f"A escala de {day_name} possui {len(values)} posições; "
                f"eram esperadas {expected_hours}."
            )

        return sum(self._number(item) for item in values)

    def _parse_comma_separated_hours(
        self,
        value: Any,
        definition: MeasureDefinition,
    ) -> float:
        if isinstance(value, str):
            values = [item.strip() for item in value.split(",")]
        elif isinstance(value, list):
            values = value
        else:
            raise ValueError("A escala de horas não é texto ou lista.")

        expected_hours = definition.hours_per_day or 24

        if len(values) != expected_hours:
            raise ValueError(
                f"A escala possui {len(values)} posições; eram esperadas "
                f"{expected_hours}."
            )

        return sum(self._number(item) for item in values)

    def _aggregate_measure(
        self,
        dataframe: pd.DataFrame,
        raw_column: str,
        measure_key: str,
        dimensions: list[str] | None,
    ) -> pd.DataFrame:
        technical_columns = {raw_column, "restr_id"}

        if dimensions:
            group_columns = [
                column
                for column in dimensions
                if column in dataframe.columns
            ]
        else:
            group_columns = [
                column
                for column in dataframe.columns
                if column not in technical_columns
                and column not in {measure_key, "allocation_hours"}
            ]

        if not group_columns:
            return pd.DataFrame(
                {
                    measure_key: [dataframe[measure_key].sum()],
                }
            )

        aggregation = {measure_key: "sum"}

        if "allocation_hours" in dataframe.columns:
            aggregation["allocation_hours"] = "max"

        return (
            dataframe.groupby(
                group_columns,
                dropna=False,
                as_index=False,
            )
            .agg(aggregation)
        )

    def _json_object(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value

        if isinstance(value, (str, bytes, bytearray)):
            parsed = json.loads(value)

            if isinstance(parsed, dict):
                return parsed

        raise ValueError("O valor não contém um objeto JSON.")

    def _path_value(
        self,
        value: dict[str, Any],
        path: list[str],
    ) -> Any:
        current: Any = value

        for key in path:
            if not isinstance(current, dict) or key not in current:
                raise ValueError(f"Caminho JSON não encontrado: {key}.")

            current = current[key]

        return current

    def _number(self, value: Any) -> float:
        if value is None or isinstance(value, bool):
            raise ValueError("Valor numérico ausente ou inválido.")

        if isinstance(value, float) and math.isnan(value):
            raise ValueError("Valor numérico ausente ou inválido.")

        if isinstance(value, str) and not value.strip():
            raise ValueError("Valor numérico vazio.")

        try:
            parsed = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(f"Valor não numérico: {value}") from error

        if not math.isfinite(parsed):
            raise ValueError(f"Valor numérico não finito: {value}")

        return parsed

    def _find_column(
        self,
        dataframe: pd.DataFrame,
        configured_name: str | None,
    ) -> str | None:
        if not configured_name:
            return None

        normalized_name = configured_name.lower()

        for column in dataframe.columns:
            if str(column).lower() == normalized_name:
                return column

        return None

    def _normalize_key(self, value: Any) -> str:
        normalized = unicodedata.normalize("NFKD", str(value))
        without_accents = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )
        return without_accents.strip().lower()

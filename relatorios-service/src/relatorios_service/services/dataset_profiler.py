from collections import Counter
from io import BytesIO

import pandas as pd
from pydantic import Field

from relatorios_service.pipeline_schemas import DateFormat, NumberFormat, PipelineModel
from relatorios_service.repositories.dataset_repository import DatasetRepository
from relatorios_service.services.file_reader import FileReader
from relatorios_service.services.measurement_parser import MeasurementParser


class MeasurementProfile(PipelineModel):
    recognized_count: int
    unrecognized_count: int
    max_pairs: int
    units_by_position: list[dict[str, int]]


class ColumnProfile(PipelineModel):
    name: str
    detected_type: str
    suggested_type: str
    null_count: int
    null_percentage: float
    distinct_count: int
    duplicate_count: int
    invalid_count: int
    whitespace_count: int
    formats: dict[str, int] = Field(default_factory=dict)
    format_masks: dict[str, int] = Field(default_factory=dict)
    other_format_count: int = 0
    measurements: dict[NumberFormat, MeasurementProfile] = Field(default_factory=dict)


class ValueFormatProfiler:
    """Máscaras estruturais limitadas, sem letras ou números dos registros."""

    punctuation = frozenset(".,%/:-+() ")
    max_length = 80
    max_masks = 10

    def summarize(self, values: pd.Series) -> tuple[dict[str, int], int]:
        counts = Counter(values.map(self._mask))
        masks = dict(counts.most_common(self.max_masks))
        return masks, len(values) - sum(masks.values())

    def _mask(self, value: str) -> str:
        masked = []
        for character in value[:self.max_length]:
            if character.isdecimal():
                masked.append("0")
            elif character.isalpha():
                masked.append("A")
            elif character.isspace():
                masked.append(" ")
            elif character in self.punctuation:
                masked.append(character)
            else:
                masked.append("?")
        if len(value) > self.max_length:
            masked.append("…")
        return "".join(masked)


class DatasetProfile(PipelineModel):
    table: str
    row_count: int
    delimiter: str
    columns: list[ColumnProfile]
    sample: list[dict[str, str | None]] = Field(default_factory=list)


class DatasetProfiler:
    """Perfis locais com amostras limitadas somente quando autorizadas."""

    def __init__(self, reader: FileReader, repository: DatasetRepository) -> None:
        self.reader = reader
        self.repository = repository
        self.value_formats = ValueFormatProfiler()

    def load(self, dataset_id: str) -> tuple[pd.DataFrame, str]:
        stored = self.repository.get(dataset_id)
        return self.reader.read_csv_with_dialect(
            BytesIO(stored.content), preserve_values=True,
        )

    def profile(
        self, alias: str, dataframe: pd.DataFrame, delimiter: str,
    ) -> DatasetProfile:
        # A inferência é local e não altera o dataframe que será executado.
        cleaned = self.reader.clean_text_and_nulls(dataframe)
        normalized = self.reader.normalize(cleaned, delimiter)
        columns = []
        for inferred in normalized.columns:
            name = inferred["name"]
            values = cleaned[name]
            non_null = values.dropna()
            raw = dataframe[name].astype("string")
            masks, other_count = self.value_formats.summarize(non_null)
            # Não copiar o perfil completo: ele pode conter exemplos de valores inválidos.
            columns.append(ColumnProfile(
                name=name,
                detected_type=inferred["detected_type"],
                suggested_type=inferred["normalized_type"],
                null_count=int(values.isna().sum()),
                null_percentage=round(float(values.isna().mean() * 100), 2),
                distinct_count=int(non_null.nunique()),
                duplicate_count=int(non_null.duplicated().sum()),
                invalid_count=inferred["invalid_count"],
                whitespace_count=int((raw != raw.str.strip()).fillna(False).sum()),
                formats=self._formats(non_null, inferred["normalized_type"]),
                format_masks=masks,
                other_format_count=other_count,
                measurements=self._measurements(non_null),
            ))
        return DatasetProfile(
            table=alias, row_count=len(dataframe), delimiter=delimiter, columns=columns,
        )

    def _measurements(self, values: pd.Series) -> dict[NumberFormat, MeasurementProfile]:
        parser = MeasurementParser()
        profiles = {}
        for number_format in NumberFormat:
            recognized = []
            for value in values:
                pairs = parser.parse(value, number_format)
                if pairs is not None:
                    recognized.append(pairs)
            if not recognized:
                continue
            max_pairs = max(map(len, recognized))
            counts = [Counter() for _ in range(max_pairs)]
            for pairs in recognized:
                for index, (_, unit) in enumerate(pairs):
                    counts[index][unit] += 1
            profiles[number_format] = MeasurementProfile(
                recognized_count=len(recognized),
                unrecognized_count=len(values) - len(recognized),
                max_pairs=max_pairs,
                units_by_position=[dict(count) for count in counts],
            )
        return profiles

    def _formats(self, values: pd.Series, suggested_type: str) -> dict[str, int]:
        formats: dict[str, int] = {}
        formats["percent_suffix"] = int(values.str.endswith("%").sum())
        if suggested_type == "date":
            for date_format in DateFormat:
                count = int(pd.to_datetime(
                    values, format=date_format.value, errors="coerce", exact=True,
                ).notna().sum())
                if count:
                    formats[date_format.value] = count
        if suggested_type in {"integer", "number"}:
            formats["decimal_comma"] = int(values.str.contains(",", regex=False).sum())
            formats["decimal_dot"] = int(values.str.contains(".", regex=False).sum())
        return formats

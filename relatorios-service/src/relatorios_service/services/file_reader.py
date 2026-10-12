import csv
import math
import re
import unicodedata
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd


@dataclass(frozen=True)
class CSVNormalizationResult:
    dataframe: pd.DataFrame
    columns: list[dict[str, Any]]


class FileReader:
    null_markers = {"", "null", "none", "n/a", "n/d", "nan"}
    boolean_values = {
        "true": True,
        "false": False,
        "sim": True,
        "não": False,
        "nao": False,
        "yes": True,
        "no": False,
    }
    date_formats = (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y",
    )

    def __init__(
        self,
        max_rows: int = 100000,
        max_columns: int = 500,
    ) -> None:
        self.max_rows = max_rows
        self.max_columns = max_columns

    def read(self, file: BinaryIO, filename: str) -> pd.DataFrame:
        extension = Path(filename).suffix.lower()

        if extension == ".csv":
            return self.read_csv(file)

        if extension in {".xlsx", ".xls"}:
            return pd.read_excel(file)

        if extension == ".json":
            return pd.read_json(file)

        raise ValueError(
            "Formato não suportado. Use CSV, XLSX, XLS ou JSON."
        )

    def normalize(
        self,
        dataframe: pd.DataFrame,
        delimiter: str | None = None,
    ) -> CSVNormalizationResult:
        normalized = dataframe.copy()
        profiles: list[dict[str, Any]] = []

        for column in normalized.columns:
            original = normalized[column].astype("string")
            non_null = original.dropna()
            null_count = int(original.isna().sum())
            identifier_column = self._is_identifier_column(str(column))

            if non_null.empty:
                normalized[column] = original
                profiles.append(
                    self._column_profile(
                        column=str(column),
                        detected_type="empty",
                        normalized_type="empty",
                        null_count=null_count,
                        row_count=len(normalized),
                    )
                )
                continue

            if identifier_column:
                normalized[column] = original
                profiles.append(
                    self._column_profile(
                        column=str(column),
                        detected_type="text",
                        normalized_type="text",
                        null_count=null_count,
                        row_count=len(normalized),
                    )
                )
                continue

            boolean_values = non_null.str.casefold().map(self.boolean_values)
            if not non_null.empty and boolean_values.notna().all():
                converted = original.str.casefold().map(self.boolean_values)
                normalized[column] = converted.astype("boolean")
                profiles.append(
                    self._column_profile(
                        column=str(column),
                        detected_type="boolean",
                        normalized_type="boolean",
                        null_count=null_count,
                        row_count=len(normalized),
                    )
                )
                continue

            date_result = self._parse_dates(non_null, str(column))
            if date_result is not None:
                parsed_dates, invalid_dates = date_result
                converted_dates = pd.Series(
                    pd.NaT,
                    index=original.index,
                    dtype="datetime64[ns]",
                )
                converted_dates.loc[parsed_dates.index] = parsed_dates
                normalized[column] = converted_dates
                profiles.append(
                    self._column_profile(
                        column=str(column),
                        detected_type=(
                            "mixed" if not invalid_dates.empty else "date"
                        ),
                        normalized_type="date",
                        null_count=null_count,
                        row_count=len(normalized),
                        invalid_values=invalid_dates,
                    )
                )
                continue

            parsed_numbers = non_null.map(
                lambda value: self._parse_number(value, delimiter),
            )
            valid_numbers = parsed_numbers.notna()
            numeric_count = int(valid_numbers.sum())
            invalid_values = non_null[~valid_numbers]

            if self._is_numeric_column(
                column=str(column),
                numeric_count=numeric_count,
                value_count=len(non_null),
            ):
                numeric_values = pd.Series(
                    pd.NA,
                    index=original.index,
                    dtype="Float64",
                )
                numeric_values.loc[non_null.index] = parsed_numbers
                is_integer = (
                    numeric_count > 0
                    and (parsed_numbers[valid_numbers] % 1 == 0).all()
                )
                if is_integer:
                    numeric_values = numeric_values.astype("Int64")
                    normalized_type = "integer"
                else:
                    normalized_type = "number"

                normalized[column] = numeric_values
                profiles.append(
                    self._column_profile(
                        column=str(column),
                        detected_type=(
                            "mixed" if not invalid_values.empty
                            else normalized_type
                        ),
                        normalized_type=normalized_type,
                        null_count=null_count,
                        row_count=len(normalized),
                        invalid_values=invalid_values,
                    )
                )
                continue

            normalized[column] = original
            profiles.append(
                self._column_profile(
                    column=str(column),
                    detected_type="text",
                    normalized_type="text",
                    null_count=null_count,
                    row_count=len(normalized),
                )
            )

        return CSVNormalizationResult(normalized, profiles)

    def _clean_text_and_nulls(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        cleaned = dataframe.copy()
        for column in cleaned.columns:
            values = cleaned[column].astype("string").str.strip()
            null_mask = values.str.casefold().isin(self.null_markers)
            cleaned[column] = values.mask(null_mask, pd.NA)

        return cleaned

    def _is_identifier_column(self, column: str) -> bool:
        normalized = self._ascii_text(column)
        separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", normalized)
        tokens = {
            token
            for token in re.split(r"[^a-zA-Z0-9]+", separated.casefold())
            if token
        }
        identifier_tokens = {
            "id",
            "codigo",
            "code",
            "matricula",
            "cpf",
            "cnpj",
            "cep",
            "zip",
        }
        return bool(tokens & identifier_tokens)

    def _parse_number(
        self,
        value: str,
        delimiter: str | None,
    ) -> float | None:
        normalized = value.strip().replace("\u00a0", "").replace(" ", "")
        if not normalized:
            return None

        candidates = [normalized]
        if "," in normalized and "." not in normalized:
            candidates.append(normalized.replace(",", "."))
        elif "," in normalized and "." in normalized:
            if re.fullmatch(
                r"[+-]?\d{1,3}(?:\.\d{3})+,\d+",
                normalized,
            ):
                candidates.append(
                    normalized.replace(".", "").replace(",", "."),
                )
            if re.fullmatch(
                r"[+-]?\d{1,3}(?:,\d{3})+\.\d+",
                normalized,
            ):
                candidates.append(normalized.replace(",", ""))
        elif delimiter == ";" and re.fullmatch(
            r"[+-]?\d{1,3}(?:\.\d{3})+",
            normalized,
        ):
            candidates.insert(0, normalized.replace(".", ""))

        for candidate in candidates:
            try:
                number = float(candidate)
            except ValueError:
                continue
            if math.isfinite(number):
                return number

        return None

    def _is_numeric_column(
        self,
        column: str,
        numeric_count: int,
        value_count: int,
    ) -> bool:
        if value_count == 0 or numeric_count == 0:
            return False
        if numeric_count == value_count:
            return True

        numeric_name_tokens = {
            "amount",
            "valor",
            "value",
            "total",
            "price",
            "preco",
            "preço",
            "quantidade",
            "quantity",
            "count",
            "idade",
            "age",
            "horas",
            "hours",
            "percentual",
            "percent",
        }
        tokens = self._name_tokens(column)
        return (
            numeric_count / value_count >= 0.5
            or bool(tokens & numeric_name_tokens)
        )

    def _parse_dates(
        self,
        values: pd.Series,
        column: str,
    ) -> tuple[pd.Series, pd.Series] | None:
        if values.empty:
            return None

        parsed_dates = pd.Series(
            pd.NaT,
            index=values.index,
            dtype="datetime64[ns]",
        )
        for date_format in self.date_formats:
            pending_values = values.loc[parsed_dates.isna()]
            parsed = pd.to_datetime(
                pending_values,
                format=date_format,
                errors="coerce",
            )
            parsed_dates.loc[parsed.index] = parsed

        invalid_dates = values[parsed_dates.isna()]
        if invalid_dates.empty:
            return parsed_dates, invalid_dates

        valid_count = int(parsed_dates.notna().sum())
        date_name_tokens = {
            "date",
            "data",
            "dates",
            "datetime",
            "timestamp",
            "birth",
            "nascimento",
        }
        name_tokens = self._name_tokens(column)
        is_date_named = bool(name_tokens & date_name_tokens)
        enough_date_values = valid_count >= 2 and (
            valid_count / len(values) >= 0.8
        )
        if is_date_named or enough_date_values:
            return parsed_dates, invalid_dates

        return None

    def _name_tokens(self, value: str) -> set[str]:
        normalized = self._ascii_text(value).casefold()
        return {
            token
            for token in re.split(r"[^a-z0-9]+", normalized)
            if token
        }

    def _ascii_text(self, value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        return "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )

    def _column_profile(
        self,
        *,
        column: str,
        detected_type: str,
        normalized_type: str,
        null_count: int,
        row_count: int,
        invalid_values: pd.Series | None = None,
    ) -> dict[str, Any]:
        if invalid_values is None:
            invalid_values = pd.Series(dtype="string")
        invalid_examples = [
            {
                "record": int(index) + 1,
                "value": str(value),
            }
            for index, value in invalid_values.head(5).items()
        ]

        return {
            "name": column,
            "detected_type": detected_type,
            "normalized_type": normalized_type,
            "null_count": null_count,
            "null_percentage": round(null_count / row_count * 100, 2),
            "invalid_count": len(invalid_values),
            "invalid_examples": invalid_examples,
        }

    def read_csv_with_dialect(
        self,
        file: BinaryIO,
    ) -> tuple[pd.DataFrame, str]:
        content = file.read()
        if not isinstance(content, bytes):
            raise ValueError("Não foi possível ler o conteúdo do CSV.")

        text = self._decode_csv(content)
        delimiter = self._detect_delimiter(text)
        return self._read_csv_text(text, delimiter), delimiter

    def _decode_csv(self, content: bytes) -> str:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = content.decode("cp1252")
            except UnicodeDecodeError as error:
                raise ValueError(
                    "A codificação do CSV não é suportada. "
                    "Salve o arquivo como UTF-8."
                ) from error

        if not text.strip():
            raise ValueError("O CSV está vazio.")

        return text

    def _detect_delimiter(self, text: str) -> str:
        try:
            return csv.Sniffer().sniff(
                text[:8192],
                delimiters=",;\t|",
            ).delimiter
        except csv.Error:
            return ","

    def _read_csv_text(
        self,
        text: str,
        delimiter: str,
    ) -> pd.DataFrame:
        header_reader = csv.reader(
            StringIO(text),
            delimiter=delimiter,
            skipinitialspace=False,
        )
        raw_headers = next(
            (row for row in header_reader if row),
            [],
        )
        headers = [header.strip() for header in raw_headers]
        if not headers:
            raise ValueError("O CSV precisa conter uma linha de cabeçalho.")
        if any(not header for header in headers):
            raise ValueError("O CSV contém nome de coluna vazio.")

        duplicated_headers = sorted(
            {
                header
                for header in headers
                if headers.count(header) > 1
            }
        )
        if duplicated_headers:
            names = ", ".join(duplicated_headers)
            raise ValueError(
                f"O CSV contém nomes de coluna duplicados: {names}."
            )

        try:
            dataframe = pd.read_csv(
                StringIO(text),
                sep=delimiter,
                dtype="string",
                keep_default_na=False,
                na_filter=False,
                on_bad_lines="error",
                nrows=self.max_rows + 1,
            )
        except pd.errors.EmptyDataError as error:
            raise ValueError(
                "O CSV precisa conter uma linha de cabeçalho."
            ) from error
        except pd.errors.ParserError as error:
            raise ValueError(
                "O CSV possui linhas com quantidade de campos inválida."
            ) from error

        if len(dataframe) > self.max_rows:
            raise ValueError(
                f"O CSV excede o limite de {self.max_rows} linhas."
            )

        if len(dataframe.columns) > self.max_columns:
            raise ValueError(
                f"O CSV excede o limite de {self.max_columns} colunas."
            )

        dataframe.columns = headers
        if dataframe.empty:
            raise ValueError("O CSV contém cabeçalho, mas não possui registros.")

        return self._clean_text_and_nulls(dataframe)

    def read_csv(self, file: BinaryIO) -> pd.DataFrame:
        dataframe, _delimiter = self.read_csv_with_dialect(file)
        return dataframe
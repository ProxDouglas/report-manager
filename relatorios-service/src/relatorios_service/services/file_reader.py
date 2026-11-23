import csv
from io import StringIO
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from relatorios_service.services.csv_normalizer import CSVNormalizationResult, CSVNormalizer


class FileReader:
    null_markers = CSVNormalizer.null_markers
    boolean_values = CSVNormalizer.boolean_values
    date_formats = CSVNormalizer.date_formats

    def __init__(
        self,
        max_rows: int = 100000,
        max_columns: int = 500,
    ) -> None:
        self.normalizer = CSVNormalizer()
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
        return self.normalizer.normalize(dataframe, delimiter)

    def clean_text_and_nulls(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        return self.normalizer.clean_text_and_nulls(dataframe)

    def read_csv_with_dialect(
        self,
        file: BinaryIO,
        preserve_values: bool = False,
    ) -> tuple[pd.DataFrame, str]:
        content = file.read()
        if not isinstance(content, bytes):
            raise ValueError("Não foi possível ler o conteúdo do CSV.")

        text = self._decode_csv(content)
        delimiter = self._detect_delimiter(text)
        return self._read_csv_text(text, delimiter, preserve_values), delimiter

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
        preserve_values: bool = False,
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

        if preserve_values:
            return dataframe
        return self.clean_text_and_nulls(dataframe)

    def read_csv(self, file: BinaryIO) -> pd.DataFrame:
        dataframe, _delimiter = self.read_csv_with_dialect(file)
        return dataframe

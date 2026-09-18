from pathlib import Path
from typing import BinaryIO

import pandas as pd


class FileReader:
    def read(self, file: BinaryIO, filename: str) -> pd.DataFrame:
        extension = Path(filename).suffix.lower()

        if extension == ".csv":
            return pd.read_csv(file)

        if extension in {".xlsx", ".xls"}:
            return pd.read_excel(file)

        if extension == ".json":
            return pd.read_json(file)

        raise ValueError(
            "Formato não suportado. Use CSV, XLSX, XLS ou JSON."
        )
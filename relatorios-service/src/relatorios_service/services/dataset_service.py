import json
from io import BytesIO
import uuid
from typing import Any

import pandas as pd

from relatorios_service.models.dataset import StoredDataset
from relatorios_service.repositories.dataset_repository import DatasetRepository
from relatorios_service.services.file_reader import FileReader


class DatasetStorageError(Exception):
    pass


class DatasetService:
    def __init__(
        self,
        file_reader: FileReader,
        dataset_repository: DatasetRepository,
    ) -> None:
        self.file_reader = file_reader
        self.dataset_repository = dataset_repository

    def preview(self, filename: str, content: bytes) -> dict[str, Any]:
        if filename.lower().endswith(".csv"):
            raw_dataframe, delimiter = self.file_reader.read_csv_with_dialect(
                BytesIO(content),
            )
            normalized = self.file_reader.normalize(raw_dataframe, delimiter)
            dataframe = normalized.dataframe
            column_profile = normalized.columns
        else:
            dataframe = self.file_reader.read(BytesIO(content), filename)
            column_profile = None

        response: dict[str, Any] = {
            "filename": filename,
            "total_rows": len(dataframe),
            "columns": list(dataframe.columns),
            "preview": self._preview_records(dataframe),
        }
        if column_profile is not None:
            response["column_profile"] = column_profile

        return response

    def store_csv(self, filename: str, content: bytes) -> dict[str, Any]:
        if not filename.lower().endswith(".csv"):
            raise ValueError("Envie um arquivo com extensão .csv.")

        raw_dataframe, delimiter = self.file_reader.read_csv_with_dialect(
            BytesIO(content),
        )
        normalized = self.file_reader.normalize(raw_dataframe, delimiter)
        dataframe = normalized.dataframe
        dataset_id = uuid.uuid4().hex
        try:
            self.dataset_repository.save(
                StoredDataset(
                    dataset_id=dataset_id,
                    filename=filename,
                    content=content,
                )
            )
        except OSError as error:
            raise DatasetStorageError from error

        return {
            "dataset_id": dataset_id,
            "filename": filename,
            "total_rows": len(dataframe),
            "columns": normalized.columns,
            "preview": self._preview_records(dataframe),
        }

    @staticmethod
    def _preview_records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        return json.loads(
            dataframe.head(20).to_json(
                orient="records",
                date_format="iso",
            )
        )

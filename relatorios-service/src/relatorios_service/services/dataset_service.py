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
        dataset, response = self._prepare_csv(filename, content)
        self._save(dataset)
        return response

    def store_many(self, files: list[tuple[str, bytes]]) -> list[dict[str, Any]]:
        prepared = [self._prepare_csv(filename, content) for filename, content in files]
        saved: list[str] = []
        try:
            for dataset, _response in prepared:
                self._save(dataset)
                saved.append(dataset.dataset_id)
        except DatasetStorageError:
            for dataset_id in saved:
                self.dataset_repository.delete(dataset_id)
            raise
        return [response for _dataset, response in prepared]

    def _prepare_csv(self, filename: str, content: bytes) -> tuple[StoredDataset, dict[str, Any]]:
        if not filename.lower().endswith(".csv"):
            raise ValueError("Envie um arquivo com extensão .csv.")

        raw_dataframe, delimiter = self.file_reader.read_csv_with_dialect(
            BytesIO(content),
        )
        normalized = self.file_reader.normalize(raw_dataframe, delimiter)
        dataframe = normalized.dataframe
        dataset_id = uuid.uuid4().hex
        dataset = StoredDataset(dataset_id=dataset_id, filename=filename, content=content)
        return dataset, {
            "dataset_id": dataset_id,
            "filename": filename,
            "total_rows": len(dataframe),
            "columns": normalized.columns,
            "preview": self._preview_records(dataframe),
        }

    def _save(self, dataset: StoredDataset) -> None:
        try:
            self.dataset_repository.save(dataset)
        except OSError as error:
            raise DatasetStorageError from error

    @staticmethod
    def _preview_records(dataframe: pd.DataFrame) -> list[dict[str, Any]]:
        return json.loads(
            dataframe.head(20).to_json(
                orient="records",
                date_format="iso",
            )
        )

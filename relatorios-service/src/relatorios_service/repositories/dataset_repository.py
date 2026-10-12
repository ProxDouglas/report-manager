import json
import re
import shutil
import tempfile
import time
from abc import ABC, abstractmethod
from pathlib import Path

from relatorios_service.models.dataset import StoredDataset


class DatasetRepository(ABC):
    @abstractmethod
    def save(self, dataset: StoredDataset) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, dataset_id: str) -> StoredDataset:
        raise NotImplementedError

    @abstractmethod
    def delete(self, dataset_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def cleanup_expired(self) -> int:
        raise NotImplementedError


class LocalDatasetRepository(DatasetRepository):
    def __init__(
        self,
        directory: str | Path,
        retention_seconds: int = 7200,
    ) -> None:
        if retention_seconds <= 0:
            raise ValueError("O tempo de retenção precisa ser positivo.")

        self.directory = Path(directory)
        self.retention_seconds = retention_seconds
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, dataset: StoredDataset) -> None:
        self._validate_id(dataset.dataset_id)
        self.cleanup_expired()
        destination = self.directory / dataset.dataset_id

        with tempfile.TemporaryDirectory(
            prefix=".dataset-",
            dir=self.directory,
        ) as temporary_directory:
            temporary_path = Path(temporary_directory)
            (temporary_path / "data.csv").write_bytes(dataset.content)
            (temporary_path / "metadata.json").write_text(
                json.dumps(
                    {
                        "filename": dataset.filename,
                        "saved_at": time.time(),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            temporary_path.rename(destination)

    def get(self, dataset_id: str) -> StoredDataset:
        self._validate_id(dataset_id)
        self.cleanup_expired()
        dataset_directory = self.directory / dataset_id

        try:
            metadata = json.loads(
                (dataset_directory / "metadata.json").read_text(
                    encoding="utf-8",
                )
            )
            content = (dataset_directory / "data.csv").read_bytes()
        except FileNotFoundError as error:
            raise FileNotFoundError(
                f"Dataset não encontrado: {dataset_id}"
            ) from error

        if not isinstance(metadata, dict):
            raise ValueError(
                f"Metadados inválidos para o dataset: {dataset_id}"
            )

        filename = metadata.get("filename")
        if not isinstance(filename, str):
            raise ValueError(
                f"Metadados inválidos para o dataset: {dataset_id}"
            )

        return StoredDataset(
            dataset_id=dataset_id,
            filename=filename,
            content=content,
        )

    def delete(self, dataset_id: str) -> None:
        self._validate_id(dataset_id)
        dataset_directory = self.directory / dataset_id

        if not dataset_directory.is_dir():
            raise FileNotFoundError(f"Dataset não encontrado: {dataset_id}")

        shutil.rmtree(dataset_directory)

    def cleanup_expired(self) -> int:
        now = time.time()
        removed_count = 0
        for dataset_directory in self.directory.iterdir():
            if (
                not dataset_directory.is_dir()
                or not re.fullmatch(r"[0-9a-f]{32}", dataset_directory.name)
            ):
                continue

            metadata_path = dataset_directory / "metadata.json"
            if not metadata_path.is_file():
                continue

            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict):
                raise ValueError(
                    f"Metadados inválidos para o dataset: "
                    f"{dataset_directory.name}"
                )
            saved_at = metadata.get("saved_at")
            if not isinstance(saved_at, (int, float)):
                raise ValueError(
                    f"Metadados de retenção inválidos: "
                    f"{dataset_directory.name}"
                )

            if now - saved_at >= self.retention_seconds:
                shutil.rmtree(dataset_directory)
                removed_count += 1

        return removed_count

    def _validate_id(self, dataset_id: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", dataset_id):
            raise ValueError("Identificador de dataset inválido.")

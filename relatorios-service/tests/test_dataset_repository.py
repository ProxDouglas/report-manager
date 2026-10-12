import json
from pathlib import Path
import tempfile
import unittest

from relatorios_service.models.dataset import StoredDataset
from relatorios_service.repositories.dataset_repository import (
    LocalDatasetRepository,
)


class LocalDatasetRepositoryTests(unittest.TestCase):
    def test_round_trips_dataset_content_and_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = LocalDatasetRepository(directory)
            dataset = StoredDataset(
                dataset_id="a" * 32,
                filename="dados.csv",
                content=b"name\nvalue\n",
            )

            repository.save(dataset)

            self.assertEqual(repository.get(dataset.dataset_id), dataset)

    def test_rejects_invalid_identifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = LocalDatasetRepository(directory)

            with self.assertRaisesRegex(ValueError, "inválido"):
                repository.get("../outside")

    def test_cleanup_removes_only_expired_dataset_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = LocalDatasetRepository(
                directory,
                retention_seconds=1,
            )
            dataset = StoredDataset(
                dataset_id="b" * 32,
                filename="dados.csv",
                content=b"value\n1\n",
            )
            repository.save(dataset)
            dataset_path = Path(directory) / dataset.dataset_id

            metadata_path = dataset_path / "metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["saved_at"] = 1
            metadata_path.write_text(
                json.dumps(metadata),
                encoding="utf-8",
            )

            self.assertEqual(repository.cleanup_expired(), 1)
            self.assertFalse(dataset_path.exists())


if __name__ == "__main__":
    unittest.main()

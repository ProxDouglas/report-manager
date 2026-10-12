import tempfile
import unittest

from relatorios_service.repositories.dataset_repository import (
    LocalDatasetRepository,
)
from relatorios_service.services.dataset_service import DatasetService
from relatorios_service.services.file_reader import FileReader


class DatasetServiceTests(unittest.TestCase):
    def test_preview_csv_returns_normalized_data_and_column_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            service = DatasetService(
                FileReader(),
                LocalDatasetRepository(directory),
            )

            result = service.preview(
                "dados.csv",
                "nome;valor\nAna;1,5\n".encode("utf-8"),
            )

            self.assertEqual(result["filename"], "dados.csv")
            self.assertEqual(result["total_rows"], 1)
            self.assertEqual(result["columns"], ["nome", "valor"])
            self.assertEqual(result["preview"][0]["valor"], 1.5)
            self.assertEqual(
                result["column_profile"][1]["normalized_type"],
                "number",
            )

    def test_store_csv_persists_original_content_and_returns_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = LocalDatasetRepository(directory)
            service = DatasetService(FileReader(), repository)
            content = b"name,value\nAna,1\n"

            result = service.store_csv("data.csv", content)
            stored = repository.get(result["dataset_id"])

            self.assertEqual(stored.filename, "data.csv")
            self.assertEqual(stored.content, content)
            self.assertEqual(result["preview"], [{"name": "Ana", "value": 1}])

    def test_store_rejects_non_csv_files(self):
        with tempfile.TemporaryDirectory() as directory:
            service = DatasetService(
                FileReader(),
                LocalDatasetRepository(directory),
            )

            with self.assertRaisesRegex(ValueError, "extensão .csv"):
                service.store_csv("dados.xlsx", b"")


if __name__ == "__main__":
    unittest.main()

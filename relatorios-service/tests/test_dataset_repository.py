import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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

    def test_cleanup_skips_invalid_metadata_and_preserves_other_operations(self):
        invalid_metadata = [b"{", b"[]", b'{"saved_at": "invalid"}', b"\xff"]
        for metadata in invalid_metadata:
            with self.subTest(metadata=metadata), tempfile.TemporaryDirectory() as directory:
                repository = LocalDatasetRepository(directory)
                broken = Path(directory) / ("a" * 32)
                broken.mkdir()
                (broken / "metadata.json").write_bytes(metadata)
                expired = Path(directory) / ("b" * 32)
                expired.mkdir()
                (expired / "metadata.json").write_text('{"saved_at": 1}', encoding="utf-8")
                dataset = StoredDataset(
                    dataset_id="c" * 32, filename="dados.csv", content=b"value\n1\n",
                )

                with self.assertLogs(
                    "relatorios_service.repositories.dataset_repository", level="ERROR",
                ):
                    self.assertEqual(repository.cleanup_expired(), 1)
                    repository.save(dataset)
                    self.assertEqual(repository.get(dataset.dataset_id), dataset)

                self.assertTrue(broken.exists())
                self.assertFalse(expired.exists())

    def test_cleanup_continues_after_a_dataset_removal_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = LocalDatasetRepository(directory)
            paths = [Path(directory) / (letter * 32) for letter in ("a", "b")]
            for path in paths:
                path.mkdir()
                (path / "metadata.json").write_text('{"saved_at": 1}', encoding="utf-8")
            with patch(
                "relatorios_service.repositories.dataset_repository.shutil.rmtree",
                side_effect=[PermissionError("denied"), None],
            ) as remove, self.assertLogs(
                "relatorios_service.repositories.dataset_repository", level="ERROR",
            ):
                self.assertEqual(repository.cleanup_expired(), 1)
                self.assertEqual(remove.call_count, 2)


if __name__ == "__main__":
    unittest.main()

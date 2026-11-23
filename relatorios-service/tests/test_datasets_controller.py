from contextlib import nullcontext
from io import BytesIO
from types import SimpleNamespace
from threading import get_ident
import unittest
from unittest.mock import AsyncMock, Mock
from zipfile import BadZipFile

from fastapi import HTTPException, UploadFile

from relatorios_service.controllers.datasets_controller import (
    preview_file, upload_dataset, upload_datasets,
)
from relatorios_service.services.dataset_service import DatasetStorageError


class DatasetsControllerTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_errors_have_controlled_messages_and_status_codes(self):
        routes = [
            (preview_file, "preview"),
            (upload_dataset, "store_csv"),
            (upload_datasets, "store_many"),
        ]
        errors = [
            (ValueError("private value"), 400, "Arquivo inválido ou formato não suportado."),
            (BadZipFile("private value"), 400, "Arquivo inválido ou formato não suportado."),
            (DatasetStorageError("private path"), 500, "Não foi possível armazenar os arquivos."),
            (RuntimeError("private path"), 500, "Não foi possível processar os arquivos."),
        ]
        for route, method in routes:
            for error, status, detail in errors:
                with self.subTest(route=route.__name__, error=type(error).__name__):
                    service = Mock()
                    getattr(service, method).side_effect = error
                    container = SimpleNamespace(
                        dataset_service=service,
                        settings=SimpleNamespace(
                            max_upload_bytes=128, max_upload_files=2, max_batch_upload_bytes=256,
                        ),
                    )
                    upload = UploadFile(filename="dados.csv", file=BytesIO(b"value\n1\n"))
                    upload.read = AsyncMock(side_effect=[b"value\n1\n", b""])
                    argument = upload
                    if route is upload_datasets:
                        argument = [upload]
                    logs = nullcontext()
                    if status == 500:
                        logs = self.assertLogs(
                            "relatorios_service.controllers.datasets_controller", level="ERROR",
                        )
                    with logs, self.assertRaises(HTTPException) as caught:
                        await route(argument, container)
                    self.assertEqual(caught.exception.status_code, status)
                    self.assertEqual(caught.exception.detail, detail)

    async def test_services_run_outside_the_event_loop_thread(self):
        loop_thread = get_ident()
        routes = [
            (preview_file, "preview"),
            (upload_dataset, "store_csv"),
            (upload_datasets, "store_many"),
        ]
        for route, method in routes:
            with self.subTest(route=route.__name__):
                service = Mock()
                threads = []

                def process(*args):
                    threads.append(get_ident())
                    return {"ok": True}

                getattr(service, method).side_effect = process
                container = SimpleNamespace(
                    dataset_service=service,
                    settings=SimpleNamespace(
                        max_upload_bytes=128, max_upload_files=2, max_batch_upload_bytes=256,
                    ),
                )
                upload = UploadFile(filename="dados.csv", file=BytesIO())
                upload.read = AsyncMock(side_effect=[b"value\n1\n", b""])
                argument = upload
                expected = {"ok": True}
                if route is upload_datasets:
                    argument = [upload]
                    expected = {"datasets": {"ok": True}}
                self.assertEqual(await route(argument, container), expected)
                self.assertEqual(len(threads), 1)
                self.assertNotEqual(threads[0], loop_thread)

    async def test_upload_limit_remains_413(self):
        container = SimpleNamespace(settings=SimpleNamespace(max_upload_bytes=1))
        upload = UploadFile(filename="dados.csv", file=BytesIO(b"value\n1\n"))
        upload.read = AsyncMock(return_value=b"value\n1\n")
        with self.assertRaises(HTTPException) as caught:
            await upload_dataset(upload, container)
        self.assertEqual(caught.exception.status_code, 413)

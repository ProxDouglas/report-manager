import asyncio
from threading import get_ident
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from relatorios_service.main import _cleanup_expired_datasets


class CleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_cleanup_runs_in_workers_and_propagates_cancellation(self):
        loop_thread = get_ident()
        threads = []
        datasets = Mock()
        pipelines = Mock()

        def cleanup():
            threads.append(get_ident())
            return 0

        datasets.cleanup_expired.side_effect = cleanup
        pipelines.cleanup_expired.side_effect = cleanup
        sleep = AsyncMock(side_effect=asyncio.CancelledError)
        with patch("relatorios_service.main.asyncio", SimpleNamespace(sleep=sleep)):
            with self.assertRaises(asyncio.CancelledError):
                await _cleanup_expired_datasets(datasets, pipelines)
        self.assertEqual(len(threads), 2)
        self.assertTrue(all(thread != loop_thread for thread in threads))
        sleep.assert_awaited_once_with(300)

    async def test_cleanup_retries_on_the_next_cycle_after_storage_failure(self):
        datasets = Mock()
        pipelines = Mock()
        datasets.cleanup_expired.side_effect = [OSError("unavailable"), 0]
        sleep = AsyncMock(side_effect=[None, asyncio.CancelledError])
        with patch(
            "relatorios_service.main.asyncio", SimpleNamespace(sleep=sleep),
        ), self.assertLogs("relatorios_service.main", level="ERROR"):
            with self.assertRaises(asyncio.CancelledError):
                await _cleanup_expired_datasets(datasets, pipelines)
        self.assertEqual(datasets.cleanup_expired.call_count, 2)
        pipelines.cleanup_expired.assert_called_once_with()

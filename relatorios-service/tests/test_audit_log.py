import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from relatorios_service.services.audit_log import AuditTrail


class AuditTrailTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.path = self.directory / "logs" / "auditoria.txt"

    def test_writes_one_line_per_event_with_timestamp_id_name_and_payload(self):
        trail = AuditTrail(self.path, "abc123")

        trail.event("analysis.started", question="Qual a alocação em 2026?")
        trail.event("query.executed", rows=3)

        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)

        timestamp, analysis_id, event_name, payload = lines[0].split(" | ", 3)
        self.assertIsNotNone(datetime.fromisoformat(timestamp).tzinfo)
        self.assertEqual(analysis_id, "abc123")
        self.assertEqual(event_name, "analysis.started")
        self.assertEqual(
            json.loads(payload),
            {"question": "Qual a alocação em 2026?"},
        )
        self.assertIn("query.executed", lines[1])

    def test_serializes_values_that_json_does_not_support(self):
        AuditTrail(self.path, "abc123").event(
            "analysis.completed",
            files={"csv": Path("reports/abc123/analysis.csv")},
        )

        payload = self.path.read_text(encoding="utf-8").split(" | ", 3)[3]
        self.assertEqual(
            json.loads(payload),
            {"files": {"csv": str(Path("reports/abc123/analysis.csv"))}},
        )

    def test_disabled_trail_does_not_write_anything(self):
        AuditTrail.disabled().event("analysis.started", question="Teste?")

        self.assertEqual(list(self.directory.iterdir()), [])

    def test_write_failure_is_logged_without_raising(self):
        trail = AuditTrail(self.directory, "abc123")

        with self.assertLogs(
            "relatorios_service.services.audit_log",
            level="ERROR",
        ):
            trail.event("analysis.started", question="Teste?")


if __name__ == "__main__":
    unittest.main()

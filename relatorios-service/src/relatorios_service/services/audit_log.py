import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)
_write_lock = threading.Lock()


def elapsed_ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 1)


class AuditTrail:
    """Grava os eventos de uma análise em arquivo texto, uma linha por evento."""

    def __init__(self, path: Path | None, analysis_id: str) -> None:
        self.path = path
        self.analysis_id = analysis_id

    @classmethod
    def disabled(cls) -> "AuditTrail":
        return cls(None, "")

    def event(self, event_name: str, **data: Any) -> None:
        if self.path is None:
            return

        timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
        payload = json.dumps(data, ensure_ascii=False, default=str)
        line = f"{timestamp} | {self.analysis_id} | {event_name} | {payload}\n"

        try:
            with _write_lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as file:
                    file.write(line)
        except OSError:
            # Falha de auditoria não deve impedir a entrega da análise.
            logger.exception("Falha ao gravar o log de auditoria em %s.", self.path)

import sqlite3
import time
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Protocol

from relatorios_service.pipeline_schemas import PipelineState


class PipelineRepository(Protocol):
    def create(self, state: PipelineState) -> None: ...

    def get(self, pipeline_id: str) -> PipelineState: ...

    def edit(self, pipeline_id: str) -> AbstractContextManager[PipelineState]: ...

    def cleanup_expired(self) -> int: ...


class LocalPipelineRepository:
    """Estado local durável; transações serializam decisões inclusive entre workers."""

    def __init__(self, path: str | Path, retention_seconds: int = 7200) -> None:
        if retention_seconds <= 0:
            raise ValueError("O tempo de retenção precisa ser positivo.")
        self.path = Path(path)
        self.retention_seconds = retention_seconds
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS pipelines "
                "(id TEXT PRIMARY KEY, created_at REAL NOT NULL, payload TEXT NOT NULL)",
            )

    def create(self, state: PipelineState) -> None:
        self.cleanup_expired()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO pipelines VALUES (?, ?, ?)",
                (state.id, time.time(), state.model_dump_json()),
            )

    def get(self, pipeline_id: str) -> PipelineState:
        with self._connect() as connection:
            return self._load(connection, pipeline_id)

    @contextmanager
    def edit(self, pipeline_id: str) -> Iterator[PipelineState]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = self._load(connection, pipeline_id)
            yield state
            connection.execute(
                "UPDATE pipelines SET payload = ? WHERE id = ?",
                (state.model_dump_json(), pipeline_id),
            )

    def cleanup_expired(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM pipelines WHERE created_at <= ?",
                (time.time() - self.retention_seconds,),
            )
            return cursor.rowcount

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _load(self, connection: sqlite3.Connection, pipeline_id: str) -> PipelineState:
        row = connection.execute(
            "SELECT payload FROM pipelines WHERE id = ? AND created_at > ?",
            (pipeline_id, time.time() - self.retention_seconds),
        ).fetchone()
        if row is None:
            raise FileNotFoundError("Pipeline não encontrado ou expirado.")
        return PipelineState.model_validate_json(row[0])

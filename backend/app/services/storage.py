from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from app.core.config import Settings
from app.core.errors import DomainError


class ArtifactStore(Protocol):
    """Contrato estável para trocar o bytea por object storage no pós-MVP."""

    def create_storage_key(self) -> str: ...

    def checksum(self, content: bytes) -> str: ...


@dataclass(frozen=True)
class PostgresArtifactStore:
    def create_storage_key(self) -> str:
        return f"postgres://artifacts/{uuid4()}"

    @staticmethod
    def checksum(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()


def get_artifact_store(settings: Settings) -> ArtifactStore:
    if settings.artifact_storage_backend != "postgres":
        raise DomainError(
            "O backend de artefatos configurado ainda não está disponível no MVP.",
            "unsupported_artifact_storage",
            501,
        )
    return PostgresArtifactStore()

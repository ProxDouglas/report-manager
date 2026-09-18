import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.core.errors import DomainError


class SecretManager(Protocol):
    def get(self, secret_ref: str) -> str:
        """Obtém um segredo sem persistir seu valor no banco."""

    def put(self, secret_ref: str, value: str) -> None:
        """Cria ou atualiza um segredo."""

    def delete(self, secret_ref: str) -> None:
        """Remove um segredo quando o provedor suportar a operação."""

    def verify_reference(self, secret_ref: str) -> bool:
        """Verifica se a referência está bem formada e acessível."""


@dataclass(frozen=True)
class EnvSecretManager:
    """Implementação exclusiva para desenvolvimento local e testes."""

    prefix: str = "env://"

    def _environment_key(self, secret_ref: str) -> str:
        if not secret_ref.startswith(self.prefix):
            raise DomainError(
                "A referência local deve usar o formato env://NOME.", "invalid_secret_ref"
            )
        key = secret_ref.removeprefix(self.prefix)
        if not key or not key.replace("_", "").isalnum():
            raise DomainError("Referência de segredo inválida.", "invalid_secret_ref")
        return key

    def get(self, secret_ref: str) -> str:
        value = os.getenv(self._environment_key(secret_ref))
        if not value:
            raise DomainError("Segredo não configurado.", "secret_unavailable", 503)
        return value

    def put(self, secret_ref: str, value: str) -> None:
        os.environ[self._environment_key(secret_ref)] = value

    def delete(self, secret_ref: str) -> None:
        os.environ.pop(self._environment_key(secret_ref), None)

    def verify_reference(self, secret_ref: str) -> bool:
        try:
            self._environment_key(secret_ref)
            return True
        except DomainError:
            return False


@dataclass(frozen=True)
class VaultSecretManager:
    """Adaptador mínimo para Vault KV v2; o valor continua fora do PostgreSQL."""

    address: str
    token: str
    mount: str = "secret"

    def _path(self, secret_ref: str) -> str:
        if not secret_ref.startswith("vault://"):
            raise DomainError(
                "A referência deve usar o formato vault://caminho.", "invalid_secret_ref"
            )
        path = secret_ref.removeprefix("vault://").strip("/")
        if not path:
            raise DomainError("Referência Vault inválida.", "invalid_secret_ref")
        return path

    def _request(
        self, method: str, path: str, json: Mapping[str, Any] | None = None
    ) -> httpx.Response:
        try:
            response = httpx.request(
                method,
                f"{self.address.rstrip('/')}/v1/{path}",
                headers={"X-Vault-Token": self.token},
                json=json,
                timeout=10,
            )
        except httpx.HTTPError as exc:
            raise DomainError(
                "Gerenciador de segredos indisponível.", "secret_unavailable", 503
            ) from exc
        if response.status_code >= 400:
            raise DomainError("Não foi possível acessar o segredo.", "secret_unavailable", 503)
        return response

    def get(self, secret_ref: str) -> str:
        response = self._request("GET", f"{self.mount}/data/{self._path(secret_ref)}")
        payload = response.json()
        value = payload.get("data", {}).get("data", {}).get("value")
        if not isinstance(value, str) or not value:
            raise DomainError("Segredo não configurado.", "secret_unavailable", 503)
        return value

    def put(self, secret_ref: str, value: str) -> None:
        self._request(
            "POST", f"{self.mount}/data/{self._path(secret_ref)}", {"data": {"value": value}}
        )

    def delete(self, secret_ref: str) -> None:
        self._request("DELETE", f"{self.mount}/metadata/{self._path(secret_ref)}")

    def verify_reference(self, secret_ref: str) -> bool:
        try:
            self._request("GET", f"{self.mount}/metadata/{self._path(secret_ref)}")
            return True
        except DomainError:
            return False


def get_secret_manager(settings: Settings) -> SecretManager:
    if settings.app_env == "local" or settings.app_env == "test":
        return EnvSecretManager()
    return VaultSecretManager(settings.vault_addr, settings.vault_token.get_secret_value())

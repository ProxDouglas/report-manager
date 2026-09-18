from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, Engine

from app.core.errors import DomainError
from app.core.secrets import SecretManager
from app.db.enums import SourceType
from app.db.models import DataSource

READ_ONLY_PATTERN = re.compile(r"^(?:with\b[\s\S]*?\bselect\b|select\b)", re.IGNORECASE)
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|merge|call|execute)\b",
    re.IGNORECASE,
)


def validate_public_host(host: str, public_only: bool = True) -> None:
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise DomainError(
            "O host deve ser um endereço IP válido no MVP.", "invalid_source_host"
        ) from exc
    if public_only and (
        address.is_private or address.is_loopback or address.is_link_local or address.is_reserved
    ):
        raise DomainError("O endereço IP da fonte deve ser público no MVP.", "private_source_host")


def validate_read_only_query(query: str) -> str:
    normalized = query.strip().rstrip(";").strip()
    if (
        not normalized
        or not READ_ONLY_PATTERN.match(normalized)
        or FORBIDDEN_SQL.search(normalized)
    ):
        raise DomainError(
            "A consulta deve ser somente leitura e iniciar com SELECT ou WITH.", "unsafe_query"
        )
    if ";" in normalized:
        raise DomainError("Múltiplas instruções não são permitidas.", "unsafe_query")
    return normalized


class SourceConnector(Protocol):
    def test_connection(self, source: DataSource) -> dict[str, Any]: ...

    def read_rows(
        self, source: DataSource, query: str, parameters: dict[str, Any], max_rows: int
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class RelationalConnector:
    secret_manager: SecretManager
    timeout_seconds: int
    public_only: bool

    def _engine(self, source: DataSource) -> Engine:
        config = source.connection_config
        host = str(config.get("host", ""))
        validate_public_host(host, self.public_only)
        password = self.secret_manager.get(source.secret_ref or "")
        database = str(config["database"])
        username = str(config["username"])
        port = int(config["port"])
        if source.source_type is SourceType.POSTGRESQL:
            url = URL.create(
                "postgresql+psycopg",
                username=username,
                password=password,
                host=host,
                port=port,
                database=database,
            )
            connect_args = {
                "connect_timeout": self.timeout_seconds,
                "sslmode": "require" if config.get("tls_verify", True) else "prefer",
            }
        elif source.source_type is SourceType.ORACLE:
            url = URL.create(
                "oracle+oracledb",
                username=username,
                password=password,
                host=host,
                port=port,
                database=database,
            )
            connect_args = {"timeout": self.timeout_seconds}
        else:
            url = URL.create(
                "mssql+pyodbc",
                username=username,
                password=password,
                host=host,
                port=port,
                database=database,
                query={"driver": "ODBC Driver 18 for SQL Server", "Encrypt": "yes"},
            )
            connect_args = {"timeout": self.timeout_seconds}
        return create_engine(url, pool_pre_ping=True, connect_args=connect_args)

    def test_connection(self, source: DataSource) -> dict[str, Any]:
        engine = self._engine(source)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                inspector = inspect(connection)
                schemas = inspector.get_schema_names()
                configured_schema = source.connection_config.get("schema_name")
                selected_schemas = [configured_schema] if configured_schema else schemas[:20]
                objects: list[dict[str, Any]] = []
                for schema_name in selected_schemas:
                    if not isinstance(schema_name, str):
                        continue
                    for table_name in inspector.get_table_names(schema=schema_name)[:100]:
                        columns = inspector.get_columns(table_name, schema=schema_name)[:500]
                        objects.append(
                            {
                                "name": f"{schema_name}.{table_name}",
                                "type": "TABLE",
                                "columns": [
                                    {
                                        "name": str(column.get("name")),
                                        "type": str(column.get("type")),
                                    }
                                    for column in columns
                                ],
                            }
                        )
                return {
                    "schemas": schemas[:100],
                    "objects": objects,
                    "driver": source.source_type,
                }
        except Exception as exc:
            raise DomainError(
                "Não foi possível testar a conexão da fonte.", "source_connection_failed", 502
            ) from exc
        finally:
            engine.dispose()

    def read_rows(
        self, source: DataSource, query: str, parameters: dict[str, Any], max_rows: int
    ) -> list[dict[str, Any]]:
        safe_query = validate_read_only_query(query)
        self._validate_allowlist(source, safe_query)
        engine = self._engine(source)
        try:
            with engine.connect() as connection:
                result = connection.execute(text(safe_query), parameters)
                rows = result.mappings().fetchmany(max_rows)
                return [dict(row) for row in rows]
        except DomainError:
            raise
        except Exception as exc:
            raise DomainError(
                "Não foi possível coletar dados da fonte.", "source_read_failed", 502
            ) from exc
        finally:
            engine.dispose()

    @staticmethod
    def _validate_allowlist(source: DataSource, query: str) -> None:
        allowed = source.connection_config.get("allowed_tables", [])
        if not isinstance(allowed, list) or not allowed:
            return
        references = re.findall(
            r"\b(?:from|join)\s+([A-Za-z0-9_.\"`]+)", query, flags=re.IGNORECASE
        )
        normalized_allowed = {str(item).strip('"`').lower() for item in allowed}
        unauthorized = {
            reference.strip('"`').lower()
            for reference in references
            if reference.strip('"`').lower() not in normalized_allowed
        }
        if unauthorized:
            raise DomainError(
                "A consulta referencia tabela fora da allowlist da fonte.",
                "source_object_not_allowed",
                403,
            )


def relational_schema_from_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    first = next(iter(rows), {})
    return {
        "row_count": None,
        "columns": [{"name": name, "type": type(value).__name__} for name, value in first.items()],
    }

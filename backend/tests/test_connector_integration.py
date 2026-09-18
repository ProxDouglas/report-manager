import os

import pytest
from sqlalchemy.engine import make_url

from app.core.secrets import EnvSecretManager
from app.db.enums import SourceStatus, SourceType
from app.db.models import DataSource
from app.services.connectors import RelationalConnector

pytestmark = pytest.mark.integration


def test_postgresql_connector_reads_only_from_a_test_database() -> None:
    database_url = os.getenv("CONNECTOR_TEST_DATABASE_URL")
    password = os.getenv("CONNECTOR_TEST_PASSWORD")
    if not database_url or not password:
        pytest.skip("CONNECTOR_TEST_DATABASE_URL e CONNECTOR_TEST_PASSWORD não configuradas")
    parsed = make_url(database_url)
    source = DataSource(
        organization_id=None,  # type: ignore[arg-type]
        owner_user_id=None,  # type: ignore[arg-type]
        name="integration",
        source_type=SourceType.POSTGRESQL,
        status=SourceStatus.ACTIVE,
        connection_config={
            "host": "127.0.0.1" if parsed.host == "localhost" else (parsed.host or "127.0.0.1"),
            "port": parsed.port or 5432,
            "database": parsed.database or "postgres",
            "username": parsed.username or "postgres",
            "tls_verify": False,
        },
        secret_ref="env://CONNECTOR_TEST_PASSWORD",
    )
    os.environ["CONNECTOR_TEST_PASSWORD"] = password
    connector = RelationalConnector(EnvSecretManager(), 10, public_only=False)
    rows = connector.read_rows(source, "SELECT 1 AS integration_value", {}, 10)
    assert rows == [{"integration_value": 1}]


@pytest.mark.parametrize(
    ("url_variable", "password_variable", "source_type", "query"),
    [
        (
            "CONNECTOR_TEST_ORACLE_DATABASE_URL",
            "CONNECTOR_TEST_ORACLE_PASSWORD",
            SourceType.ORACLE,
            "SELECT 1 AS integration_value FROM dual",
        ),
        (
            "CONNECTOR_TEST_MSSQL_DATABASE_URL",
            "CONNECTOR_TEST_MSSQL_PASSWORD",
            SourceType.SQLSERVER,
            "SELECT 1 AS integration_value",
        ),
    ],
)
def test_optional_oracle_and_mssql_connectors_read_only(
    url_variable: str,
    password_variable: str,
    source_type: SourceType,
    query: str,
) -> None:
    database_url = os.getenv(url_variable)
    password = os.getenv(password_variable)
    if not database_url or not password:
        pytest.skip(f"{url_variable} e {password_variable} não configuradas")
    parsed = make_url(database_url)
    source = DataSource(
        organization_id=None,  # type: ignore[arg-type]
        owner_user_id=None,  # type: ignore[arg-type]
        name=f"integration-{source_type.value}",
        source_type=source_type,
        status=SourceStatus.ACTIVE,
        connection_config={
            "host": parsed.host or "127.0.0.1",
            "port": parsed.port or (1521 if source_type is SourceType.ORACLE else 1433),
            "database": parsed.database or "master",
            "username": parsed.username or "sa",
            "tls_verify": False,
        },
        secret_ref=f"env://{password_variable}",
    )
    os.environ[password_variable] = password
    connector = RelationalConnector(EnvSecretManager(), 10, public_only=False)
    rows = connector.read_rows(source, query, {}, 10)
    assert len(rows) == 1
    assert list(rows[0].values()) == [1]

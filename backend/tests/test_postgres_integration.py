import os

import pytest
from sqlalchemy import create_engine, inspect

pytestmark = pytest.mark.integration


def test_postgres_migration_exposes_isolation_and_readiness_tables() -> None:
    database_url = os.getenv("INTEGRATION_DATABASE_URL")
    if not database_url:
        pytest.skip("INTEGRATION_DATABASE_URL não configurada")
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "source_grants" in tables
        assert "worker_heartbeats" in tables
        assert "audit_events" in tables
        report_indexes = {item["name"] for item in inspector.get_indexes("report_versions")}
        source_indexes = {item["name"] for item in inspector.get_indexes("data_source_versions")}
        assert "uq_report_published_version" in report_indexes
        assert "uq_source_latest_valid" in source_indexes
    finally:
        engine.dispose()

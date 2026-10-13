from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import Any, Protocol

import pandas as pd
from sqlalchemy import MetaData, Table, inspect, select, text
from sqlalchemy.engine import Engine

from relatorios_service.database import DatabaseEngineFactory, DatabaseType
from relatorios_service.models.database import DatabaseTableSchema


class AnalyticsSession(Protocol):
    database: DatabaseType

    def table_names(self) -> list[str]: ...

    def inspect_table(
        self,
        table_name: str,
        sample_columns: list[str],
    ) -> DatabaseTableSchema: ...

    def execute_read(
        self,
        sql: str,
        parameters: dict[str, Any],
    ) -> pd.DataFrame: ...


class AnalyticsRepository(Protocol):
    def active_database(self) -> DatabaseType: ...

    def test_connection(self) -> bool: ...

    def open_session(self) -> AbstractContextManager[AnalyticsSession]: ...


class SqlAlchemyAnalyticsRepository:
    def __init__(self, database_factory: DatabaseEngineFactory) -> None:
        self.database_factory = database_factory

    def active_database(self) -> DatabaseType:
        return self.database_factory.active_database()

    def test_connection(self) -> bool:
        return self.database_factory.test_connection()

    @contextmanager
    def open_session(self) -> Iterator[AnalyticsSession]:
        database = self.database_factory.active_database()
        engine = self.database_factory.create()
        try:
            yield _SqlAlchemyAnalyticsSession(engine, database)
        finally:
            engine.dispose()


class _SqlAlchemyAnalyticsSession:
    def __init__(self, engine: Engine, database: DatabaseType) -> None:
        self.engine = engine
        self.database = database

    def table_names(self) -> list[str]:
        return inspect(self.engine).get_table_names()

    def inspect_table(
        self,
        table_name: str,
        sample_columns: list[str],
    ) -> DatabaseTableSchema:
        inspector = inspect(self.engine)
        columns = {
            column["name"]: str(column["type"])
            for column in inspector.get_columns(table_name)
        }
        reflected_table = Table(
            table_name,
            MetaData(),
            autoload_with=self.engine,
        )
        selected_columns = [
            reflected_table.c[name]
            for name in sample_columns
            if name in reflected_table.c
        ]
        sample_rows: list[dict[str, Any]] = []

        if selected_columns:
            sample_query = (
                select(*selected_columns)
                .select_from(reflected_table)
                .limit(5)
            )
            with self.engine.connect() as connection:
                sample_rows = [
                    dict(row._mapping)
                    for row in connection.execute(sample_query)
                ]

        primary_key = inspector.get_pk_constraint(table_name)
        return DatabaseTableSchema(
            columns=columns,
            sample_rows=sample_rows,
            primary_key=primary_key.get("constrained_columns") or [],
            foreign_keys=inspector.get_foreign_keys(table_name),
        )

    def execute_read(
        self,
        sql: str,
        parameters: dict[str, Any],
    ) -> pd.DataFrame:
        with self.engine.connect() as connection:
            return pd.read_sql(text(sql), connection, params=parameters)

import unittest

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from relatorios_service.database import DatabaseEngineFactory, DatabaseType
from relatorios_service.repositories.analytics_repository import (
    SqlAlchemyAnalyticsRepository,
)


class SQLiteDatabaseFactory(DatabaseEngineFactory):
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def active_database(self) -> DatabaseType:
        return DatabaseType.POSTGRES

    def create(self) -> Engine:
        return self.engine


class SqlAlchemyAnalyticsRepositoryTests(unittest.TestCase):
    def test_session_inspects_tables_and_executes_read_queries(self):
        engine = create_engine("sqlite://")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE items "
                    "(id INTEGER PRIMARY KEY, label VARCHAR(20), amount INTEGER)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO items (label, amount) "
                    "VALUES ('first', 7), ('second', 3)"
                )
            )

        repository = SqlAlchemyAnalyticsRepository(
            SQLiteDatabaseFactory(engine),
        )
        with repository.open_session() as session:
            self.assertEqual(session.database, DatabaseType.POSTGRES)
            self.assertEqual(session.table_names(), ["items"])

            schema = session.inspect_table("items", ["label", "amount"])
            self.assertEqual(schema.primary_key, ["id"])
            self.assertEqual(schema.columns["label"], "VARCHAR(20)")
            self.assertEqual(schema.sample_rows[0]["label"], "first")

            dataframe = session.execute_read(
                "SELECT label, amount FROM items WHERE amount > :minimum",
                {"minimum": 5},
            )

        self.assertEqual(
            dataframe.to_dict(orient="records"),
            [{"label": "first", "amount": 7}],
        )
        engine.dispose()


if __name__ == "__main__":
    unittest.main()

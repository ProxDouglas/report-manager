from enum import Enum

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from relatorios_service.config import settings


class DatabaseType(str, Enum):
    POSTGRES = "postgres"
    SQLSERVER = "sqlserver"
    ORACLE = "oracle"


class DatabaseEngineFactory:
    def active_database(self) -> DatabaseType:
        try:
            return DatabaseType(settings.database_type)
        except ValueError as error:
            supported = ", ".join(database.value for database in DatabaseType)
            raise ValueError(
                f"DATABASE_TYPE inválido: {settings.database_type}. "
                f"Valores aceitos: {supported}."
            ) from error

    def create(self) -> Engine:
        database = self.active_database()
        url = settings.database_url

        if not url:
            raise ValueError(
                "DATABASE_URL não foi configurada para o banco ativo: "
                f"{database.value}."
            )

        return create_engine(
            url,
            pool_pre_ping=True,
        )

    def test_connection(self) -> bool:
        database = self.active_database()
        engine = self.create()

        queries = {
            DatabaseType.POSTGRES: "SELECT 1",
            DatabaseType.SQLSERVER: "SELECT 1",
            DatabaseType.ORACLE: "SELECT 1 FROM dual",
        }

        with engine.connect() as connection:
            connection.execute(text(queries[database]))

        return True

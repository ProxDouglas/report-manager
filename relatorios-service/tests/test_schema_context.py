import json
import unittest
from unittest.mock import MagicMock

from relatorios_service.models.database import DatabaseTableSchema
from relatorios_service.schemas import ColumnDefinition, MetricDefinition, TableDefinition
from relatorios_service.services.schema_context import build_schema_context


def build_metric() -> MetricDefinition:
    return MetricDefinition(
        key="generic_analysis",
        label="Análise genérica",
        description="Teste.",
        business_rule="Teste.",
        tables={
            "funcionario": TableDefinition(
                description="Colaboradores.",
                columns={
                    "id": ColumnDefinition(description="Identificador."),
                },
            ),
        },
    )


class SchemaContextTests(unittest.TestCase):
    def test_describes_authorized_table_with_catalog_and_database_data(self):
        session = MagicMock()
        session.table_names.return_value = ["funcionario"]
        session.inspect_table.return_value = DatabaseTableSchema(
            columns={"id": "INTEGER", "nome": "VARCHAR"},
            sample_rows=[{"id": 1}],
            primary_key=["id"],
            foreign_keys=[],
        )

        context = json.loads(
            build_schema_context(session, build_metric(), ["funcionario"])
        )

        self.assertEqual(context[0]["table"], "funcionario")
        self.assertEqual(context[0]["description"], "Colaboradores.")
        self.assertEqual(
            context[0]["columns"],
            [
                {
                    "name": "id",
                    "type": "INTEGER",
                    "description": "Identificador.",
                },
            ],
        )
        self.assertEqual(context[0]["sample_rows"], [{"id": 1}])
        self.assertEqual(context[0]["primary_key"], ["id"])

    def test_rejects_table_missing_from_database(self):
        session = MagicMock()
        session.table_names.return_value = []

        with self.assertRaisesRegex(ValueError, "não foram encontradas"):
            build_schema_context(session, build_metric(), ["funcionario"])


if __name__ == "__main__":
    unittest.main()

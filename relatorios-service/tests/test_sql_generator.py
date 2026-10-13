import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from relatorios_service.database import DatabaseType
from relatorios_service.schemas import (
    AnalysisComponent,
    AnalysisRequest,
    ColumnDefinition,
    MetricDefinition,
    SemanticMapping,
    TableDefinition,
)
from relatorios_service.services.audit_log import AuditTrail
from relatorios_service.services.sql_generator import SqlGenerator
from relatorios_service.sql_safety import SqlSafetyValidator


def build_metric() -> MetricDefinition:
    return MetricDefinition(
        key="generic_analysis",
        label="Análise genérica",
        description="Teste.",
        business_rule="Teste.",
        tables={
            "funcionario": TableDefinition(
                columns={"id": ColumnDefinition()},
            ),
        },
    )


class SqlGeneratorTests(unittest.TestCase):
    def test_retries_with_correction_when_first_sql_is_rejected(self):
        model = MagicMock()
        structured = MagicMock()
        model.with_structured_output.return_value = structured
        structured.invoke.side_effect = [
            {"sql": "SELECT nome FROM tabela_proibida"},
            {"sql": "SELECT id FROM funcionario"},
        ]
        generator = SqlGenerator(model, SqlSafetyValidator())

        sql, sql_plan = generator.validated_plan(
            AnalysisRequest(question="Liste os colaboradores"),
            AnalysisComponent(id="c1", tables=["funcionario"]),
            build_metric(),
            "[]",
            DatabaseType.POSTGRES,
        )

        self.assertEqual(sql, "SELECT id FROM funcionario")
        self.assertEqual(sql_plan.sql, "SELECT id FROM funcionario")
        self.assertEqual(structured.invoke.call_count, 2)
        correction_prompt = structured.invoke.call_args_list[1].args[0]
        self.assertIn("A tentativa anterior foi rejeitada", correction_prompt)

    def test_audit_records_rejected_sql_and_its_correction(self):
        model = MagicMock()
        structured = MagicMock()
        model.with_structured_output.return_value = structured
        structured.invoke.side_effect = [
            {"sql": "SELECT nome FROM tabela_proibida"},
            {"sql": "SELECT id FROM funcionario"},
        ]
        generator = SqlGenerator(model, SqlSafetyValidator())

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "auditoria.txt"
            generator.validated_plan(
                AnalysisRequest(question="Liste os colaboradores"),
                AnalysisComponent(id="c1", tables=["funcionario"]),
                build_metric(),
                "[]",
                DatabaseType.POSTGRES,
                AuditTrail(path, "analysis-1"),
            )
            lines = path.read_text(encoding="utf-8").splitlines()

        events = [line.split(" | ", 3) for line in lines]
        self.assertEqual(
            [event[2] for event in events],
            ["sql.rejected", "sql.validated"],
        )
        rejected = json.loads(events[0][3])
        self.assertEqual(rejected["sql"], "SELECT nome FROM tabela_proibida")
        self.assertEqual(rejected["attempt"], 1)
        validated = json.loads(events[1][3])
        self.assertEqual(validated["sql"], "SELECT id FROM funcionario")
        self.assertEqual(validated["attempts"], 2)

    def test_retries_when_sql_uses_another_company_from_the_question(self):
        model = MagicMock()
        structured = MagicMock()
        model.with_structured_output.return_value = structured
        structured.invoke.side_effect = [
            {
                "sql": (
                    "SELECT descr FROM empresa "
                    "WHERE descr IN "
                    "(:filter_company_name, :filter_company_name_2)"
                ),
                "parameters": {
                    "filter_company_name": "Empresa teste",
                    "filter_company_name_2": "Expresso Aurora",
                },
            },
            {
                "sql": (
                    "SELECT descr FROM empresa "
                    "WHERE descr = :filter_company_name"
                ),
                "parameters": {"filter_company_name": "Empresa teste"},
            },
        ]
        metric = MetricDefinition(
            key="generic_analysis",
            label="Análise genérica",
            description="Teste.",
            business_rule="Teste.",
            tables={
                "empresa": TableDefinition(
                    columns={"descr": ColumnDefinition()},
                ),
            },
            semantic_mappings={
                "company_name": SemanticMapping(
                    table="empresa",
                    column="descr",
                    parameter="filter_company_name",
                ),
            },
        )
        component = AnalysisComponent(
            id="empresa_teste",
            tables=["empresa"],
            filters={"company_name": "Empresa teste"},
        )
        generator = SqlGenerator(model, SqlSafetyValidator())

        sql, sql_plan = generator.validated_plan(
            AnalysisRequest(
                question=(
                    "Compare Empresa teste e Expresso Aurora, "
                    "cada uma em seu componente"
                )
            ),
            component,
            metric,
            "[]",
            DatabaseType.POSTGRES,
        )

        self.assertEqual(
            sql,
            "SELECT descr FROM empresa WHERE descr = :filter_company_name",
        )
        self.assertEqual(
            sql_plan.parameters,
            {"filter_company_name": "Empresa teste"},
        )
        self.assertEqual(structured.invoke.call_count, 2)
        correction_prompt = structured.invoke.call_args_list[1].args[0]
        self.assertIn(
            "não corresponde ao filtro company_name",
            correction_prompt,
        )

if __name__ == "__main__":
    unittest.main()

from datetime import date
import unittest

from relatorios_service.sql_safety import SqlSafetyValidator


class SqlSafetyValidatorTests(unittest.TestCase):
    def setUp(self):
        self.validator = SqlSafetyValidator()
        self.month_series_sql = """
SELECT months.month_start AS month
FROM generate_series(
    CAST(:filter_period_start AS date),
    CAST(:filter_period_end AS date) - interval '1 month',
    interval '1 month'
) AS months(month_start)
"""

    def test_allows_postgres_native_table_function(self):
        result = self.validator.validate(
            self.month_series_sql,
            [],
            {},
            database="postgres",
        )

        self.assertIn("generate_series", result)

    def test_normalizes_postgres_casts_for_named_parameters(self):
        sql = """
SELECT dates.analysis_date
FROM generate_series(
    :filter_period_start::date,
    (:filter_period_end::date - interval '1 day'),
    interval '1 day'
) AS dates(analysis_date)
"""

        result = self.validator.validate(
            sql,
            [],
            {},
            database="postgres",
        )

        self.assertIn("CAST(:filter_period_start AS date)", result)
        self.assertIn("CAST(:filter_period_end AS date)", result)
        self.validator.validate_parameters(
            result,
            {
                "filter_period_start": date(2026, 1, 1),
                "filter_period_end": date(2027, 1, 1),
            },
            require_parameter=True,
        )

    def test_allows_qualified_postgres_catalog_function(self):
        sql = self.month_series_sql.replace(
            "FROM generate_series(",
            "FROM pg_catalog.generate_series(",
        )

        self.validator.validate(sql, [], {}, database="postgres")

    def test_rejects_native_function_without_dialect(self):
        with self.assertRaisesRegex(
            ValueError,
            "generate_series",
        ):
            self.validator.validate(self.month_series_sql, [], {})

    def test_rejects_postgres_function_for_oracle(self):
        with self.assertRaisesRegex(
            ValueError,
            "generate_series",
        ):
            self.validator.validate(
                self.month_series_sql,
                [],
                {},
                database="oracle",
            )

    def test_rejects_function_from_untrusted_schema(self):
        sql = self.month_series_sql.replace(
            "FROM generate_series(",
            "FROM public.generate_series(",
        )

        with self.assertRaisesRegex(
            ValueError,
            "generate_series",
        ):
            self.validator.validate(sql, [], {}, database="postgres")

    def test_keeps_physical_table_allowlist(self):
        sql = "SELECT company.descr FROM empresa AS company"

        result = self.validator.validate(
            sql,
            ["empresa"],
            {"empresa": ["descr"]},
            database="postgres",
        )

        self.assertEqual(sql, result)

    def test_keeps_rejecting_unknown_physical_tables(self):
        with self.assertRaisesRegex(
            ValueError,
            "tabelas não autorizadas: forbidden_table",
        ):
            self.validator.validate(
                "SELECT value FROM forbidden_table",
                [],
                {},
                database="postgres",
            )


if __name__ == "__main__":
    unittest.main()

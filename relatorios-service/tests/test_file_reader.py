from io import BytesIO
import unittest

from relatorios_service.services.file_reader import FileReader


class FileReaderTests(unittest.TestCase):
    def setUp(self):
        self.reader = FileReader()

    def test_normalizes_semicolon_csv_with_decimal_comma_and_nulls(self):
        content = (
            "id;valor;data;descricao\n"
            "001;1,5;2026-01-01;válido\n"
            "002;;2026-01-02;N/D\n"
        ).encode("utf-8")

        raw_dataframe, delimiter = self.reader.read_csv_with_dialect(
            BytesIO(content),
        )
        result = self.reader.normalize(raw_dataframe, delimiter)
        profiles = result.columns

        self.assertEqual(delimiter, ";")
        self.assertEqual(str(result.dataframe["id"].iloc[0]), "001")
        self.assertEqual(result.dataframe["valor"].iloc[0], 1.5)
        self.assertTrue(result.dataframe["valor"].isna().iloc[1])
        self.assertEqual(
            str(result.dataframe["data"].dtype),
            "datetime64[ns]",
        )
        self.assertEqual(
            [profile["detected_type"] for profile in profiles],
            ["text", "number", "date", "text"],
        )
        self.assertEqual(profiles[2]["null_count"], 0)
        self.assertEqual(profiles[1]["null_count"], 1)
        self.assertEqual(profiles[1]["null_percentage"], 50.0)
        self.assertEqual(profiles[3]["null_count"], 1)

    def test_reports_mixed_numeric_values_and_keeps_original_csv_available(self):
        raw_dataframe, delimiter = self.reader.read_csv_with_dialect(
            BytesIO(b"score\n10\nerrado\n"),
        )
        result = self.reader.normalize(raw_dataframe, delimiter)
        profile = result.columns[0]

        self.assertEqual(profile["detected_type"], "mixed")
        self.assertEqual(profile["normalized_type"], "integer")
        self.assertEqual(profile["invalid_count"], 1)
        self.assertEqual(
            profile["invalid_examples"],
            [{"record": 2, "value": "errado"}],
        )
        self.assertEqual(result.dataframe["score"].iloc[0], 10)
        self.assertTrue(result.dataframe["score"].isna().iloc[1])
        self.assertEqual(raw_dataframe.loc[1, "score"], "errado")

    def test_preserves_identifiers_and_normalizes_boolean_values(self):
        raw_dataframe, delimiter = self.reader.read_csv_with_dialect(
            BytesIO(
                "employee_code,active\n00123,Sim\n00456,Não\n".encode(
                    "utf-8",
                ),
            ),
        )
        result = self.reader.normalize(raw_dataframe, delimiter)

        self.assertEqual(
            result.dataframe["employee_code"].tolist(),
            ["00123", "00456"],
        )
        self.assertEqual(
            result.dataframe["active"].tolist(),
            [True, False],
        )
        self.assertEqual(result.columns[1]["normalized_type"], "boolean")

    def test_normalizes_european_thousands_and_decimal_separators(self):
        raw_dataframe, delimiter = self.reader.read_csv_with_dialect(
            BytesIO(b"valor;outro;inteiro\n1.234,56;2,75;1.234\n"),
        )
        result = self.reader.normalize(raw_dataframe, delimiter)

        self.assertEqual(result.dataframe.loc[0, "valor"], 1234.56)
        self.assertEqual(result.dataframe.loc[0, "outro"], 2.75)
        self.assertEqual(result.dataframe.loc[0, "inteiro"], 1234)

    def test_reports_invalid_dates_for_date_named_columns(self):
        raw_dataframe, delimiter = self.reader.read_csv_with_dialect(
            BytesIO(
                b"birth_date\n2026-01-01\ninvalid\n2026-01-03\n",
            ),
        )
        result = self.reader.normalize(raw_dataframe, delimiter)
        profile = result.columns[0]

        self.assertEqual(profile["detected_type"], "mixed")
        self.assertEqual(profile["normalized_type"], "date")
        self.assertEqual(profile["invalid_count"], 1)
        self.assertTrue(result.dataframe["birth_date"].isna().iloc[1])

    def test_reports_all_null_column_as_empty(self):
        raw_dataframe, delimiter = self.reader.read_csv_with_dialect(
            BytesIO(b"notes\nN/D\n"),
        )
        result = self.reader.normalize(raw_dataframe, delimiter)

        self.assertEqual(result.columns[0]["detected_type"], "empty")
        self.assertEqual(result.columns[0]["null_count"], 1)

    def test_rejects_duplicate_headers_after_trimming(self):
        with self.assertRaisesRegex(ValueError, "duplicados"):
            self.reader.read_csv(BytesIO(b"name, name\nA,B\n"))

    def test_rejects_csv_without_records(self):
        with self.assertRaisesRegex(ValueError, "não possui registros"):
            self.reader.read_csv(BytesIO(b"name,amount\n"))

    def test_rejects_csv_over_row_limit(self):
        reader = FileReader(max_rows=1)

        with self.assertRaisesRegex(ValueError, "excede o limite"):
            reader.read_csv(BytesIO(b"value\n1\n2\n"))

    def test_reads_windows_1252_csv(self):
        dataframe = self.reader.read_csv(
            BytesIO("nome\nJoão\n".encode("cp1252")),
        )

        self.assertEqual(dataframe.loc[0, "nome"], "João")


if __name__ == "__main__":
    unittest.main()

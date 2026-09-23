import re
from typing import Any


class SqlSafetyValidator:
    _identifier = r"(?:\"[^\"]+\"|`[^`]+`|\[[^\]]+\]|[A-Za-z_]\w*)"
    _forbidden = re.compile(
        r"\b(insert|update|delete|drop|alter|truncate|merge|create|grant|revoke|exec|execute)\b",
        re.IGNORECASE,
    )
    _table_reference = re.compile(
        rf"\b(?:from|join)\s+(?:lateral\s+)?"
        rf"(?P<table>{_identifier}(?:\s*\.\s*{_identifier})?)"
        rf"(?:\s+(?:as\s+)?(?P<alias>{_identifier}))?",
        re.IGNORECASE,
    )
    _cte_reference = re.compile(
        rf"(?:\bwith|,)\s*(?:recursive\s+)?"
        rf"(?P<name>{_identifier})\s+as\s*\(",
        re.IGNORECASE,
    )
    _qualified_identifier = re.compile(
        rf"(?P<qualifier>{_identifier})\s*\.\s*"
        rf"(?P<column>{_identifier})",
        re.IGNORECASE,
    )
    _postgres_parameter_cast = re.compile(
        r"(?<!:):(?P<name>[A-Za-z_]\w*)::"
        r"(?P<type>[A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)?"
        r"(?:\s*\[\])?)",
        re.IGNORECASE,
    )
    _parameter = re.compile(r"(?<!:):(?P<name>[A-Za-z_]\w*)")
    _string_literal = re.compile(r"'(?:''|[^'])*'")
    _token = re.compile(
        rf"(?:\"[^\"]+\"|`[^`]+`|\[[^\]]+\]|[A-Za-z_]\w*)"
    )
    _keywords = {
        "all",
        "and",
        "as",
        "asc",
        "between",
        "by",
        "case",
        "cast",
        "when",
        "then",
        "else",
        "end",
        "cross",
        "current_date",
        "current_timestamp",
        "date",
        "day",
        "desc",
        "distinct",
        "exists",
        "extract",
        "false",
        "filter",
        "first",
        "following",
        "for",
        "from",
        "full",
        "group",
        "having",
        "ilike",
        "in",
        "inner",
        "interval",
        "is",
        "join",
        "lateral",
        "last",
        "left",
        "like",
        "limit",
        "natural",
        "not",
        "null",
        "nulls",
        "offset",
        "on",
        "or",
        "order",
        "over",
        "partition",
        "range",
        "recursive",
        "right",
        "rows",
        "select",
        "some",
        "table",
        "to",
        "true",
        "union",
        "unbounded",
        "values",
        "where",
        "window",
        "with",
        "without",
    }
    _native_table_functions: dict[str, frozenset[str]] = {
        "postgres": frozenset(
            {"generate_series", "pg_catalog.generate_series"}
        ),
        "sqlserver": frozenset({"generate_series"}),
        "oracle": frozenset(),
    }

    def native_table_functions(
        self,
        database: str,
    ) -> tuple[str, ...]:
        functions = self._native_table_functions.get(
            self._database_name(database),
            frozenset(),
        )
        return tuple(
            sorted(
                {
                    function.rsplit(".", 1)[-1]
                    for function in functions
                }
            )
        )

    def validate(
        self,
        sql: str,
        allowed_tables: list[str],
        allowed_columns: dict[str, list[str]] | None = None,
        database: str | None = None,
    ) -> str:
        normalized = sql.strip()

        if self._database_name(database) == "postgres":
            normalized = self._normalize_postgres_parameter_casts(normalized)

        if not normalized:
            raise ValueError("O modelo não retornou uma consulta SQL.")

        if ";" in normalized.rstrip(";"):
            raise ValueError("A consulta deve conter somente uma instrução SQL.")

        if not re.match(r"^(select|with)\b", normalized, re.IGNORECASE):
            raise ValueError("Somente consultas SELECT são permitidas.")

        if "--" in normalized or "/*" in normalized or "*/" in normalized:
            raise ValueError("Comentários SQL não são permitidos.")

        if self._forbidden.search(normalized):
            raise ValueError("A consulta contém uma operação SQL não permitida.")

        cte_names = self._cte_names(normalized)
        table_references = list(self._table_reference.finditer(normalized))
        allowed = {self._normalize_identifier(table) for table in allowed_tables}
        unknown_tables = {
            self._table_name(reference.group("table"))
            for reference in table_references
            if self._table_name(reference.group("table")) not in allowed
            and self._table_name(reference.group("table")) not in cte_names
            and not self._is_allowed_native_table_function(
                normalized,
                reference,
                database,
            )
        }

        if unknown_tables:
            names = ", ".join(sorted(unknown_tables))
            raise ValueError(f"A consulta referencia tabelas não autorizadas: {names}")

        if allowed_columns is not None:
            self._validate_columns(
                normalized,
                table_references,
                cte_names,
                allowed_columns,
                database,
            )

        return normalized.rstrip(";").strip()

    def validate_parameters(
        self,
        sql: str,
        parameters: dict[str, Any],
        forbidden_values: list[Any] | None = None,
        require_parameter: bool = False,
    ) -> None:
        parameter_names = self.parameter_names(sql)
        configured_names = set(parameters)

        if require_parameter and not parameter_names:
            raise ValueError(
                "A consulta possui filtros, mas não usa parâmetros nomeados."
            )

        missing_parameters = parameter_names - configured_names
        if missing_parameters:
            names = ", ".join(sorted(missing_parameters))
            raise ValueError(f"Parâmetros SQL não informados: {names}")

        unused_parameters = configured_names - parameter_names
        if unused_parameters:
            names = ", ".join(sorted(unused_parameters))
            raise ValueError(f"Parâmetros SQL não utilizados: {names}")

        if not forbidden_values:
            return

        literals = [
            self._normalize_value(match.group(0)[1:-1])
            for match in self._string_literal.finditer(sql)
        ]

        for value in forbidden_values:
            normalized_value = self._normalize_value(value)

            if normalized_value and normalized_value in literals:
                raise ValueError(
                    "Um valor de filtro foi inserido diretamente no SQL. "
                    "Use um parâmetro nomeado."
                )

    def _validate_columns(
        self,
        sql: str,
        table_references: list[re.Match[str]],
        cte_names: set[str],
        allowed_columns: dict[str, list[str]],
        database: str | None,
    ) -> None:
        normalized_columns = {
            self._normalize_identifier(table): {
                self._normalize_identifier(column) for column in columns
            }
            for table, columns in allowed_columns.items()
        }
        aliases = self._table_aliases(
            sql,
            table_references,
            cte_names,
            database,
        )
        table_spans = [reference.span() for reference in table_references]

        for reference in self._qualified_identifier.finditer(sql):
            if self._inside_span(reference.span(), table_spans):
                continue

            qualifier = self._normalize_identifier(reference.group("qualifier"))
            column = self._normalize_identifier(reference.group("column"))

            if qualifier in cte_names:
                continue

            if qualifier not in aliases:
                raise ValueError(
                    f"A consulta usa o identificador não autorizado: "
                    f"{qualifier}.{column}"
                )

            table = aliases[qualifier]
            if table is None or table in cte_names:
                continue

            self._assert_column_allowed(table, column, normalized_columns)

        self._validate_unqualified_columns(
            sql,
            table_references,
            cte_names,
            aliases,
            normalized_columns,
        )

    def _validate_unqualified_columns(
        self,
        sql: str,
        table_references: list[re.Match[str]],
        cte_names: set[str],
        aliases: dict[str, str | None],
        allowed_columns: dict[str, set[str]],
    ) -> None:
        masked_sql = self._mask_literals(sql)
        spans_to_mask = [reference.span() for reference in table_references]
        spans_to_mask.extend(self._qualified_identifier_spans(masked_sql))
        masked_sql = self._mask_spans(masked_sql, spans_to_mask)

        known_columns = {
            column
            for columns in allowed_columns.values()
            for column in columns
        }
        ignored = set(self._keywords)
        ignored.update(aliases)
        ignored.update(cte_names)
        ignored.update(allowed_columns)

        aliases_from_as = re.findall(
            rf"\bas\s+({self._identifier})",
            masked_sql,
            re.IGNORECASE,
        )
        ignored.update(
            self._normalize_identifier(alias) for alias in aliases_from_as
        )
        ignored.update(
            self._select_aliases(self._mask_literals(sql))
        )
        ignored.update(
            self._derived_column_aliases(self._mask_literals(sql))
        )

        for token in self._token.finditer(masked_sql):
            value = self._normalize_identifier(token.group(0))
            if not value or value in ignored or value in known_columns:
                continue

            next_character = masked_sql[token.end():].lstrip()[:1]
            if next_character == "(":
                continue

            if token.start() > 0 and masked_sql[token.start() - 1] == ":":
                continue

            raise ValueError(
                f"A consulta usa a coluna ou identificador não autorizado: "
                f"{value}"
            )

    def _select_aliases(self, sql: str) -> set[str]:
        aliases: set[str] = set()
        alias_end = (
            r"(?=\s*(?:,|\bfrom\b|\bwhere\b|\bgroup\b|\border\b|"
            r"\bhaving\b|\blimit\b|\boffset\b|\bunion\b|$))"
        )

        patterns = (
            rf"\bend\s+(?P<alias>{self._identifier}){alias_end}",
            rf"\)\s+(?P<alias>{self._identifier}){alias_end}",
            rf"{self._qualified_identifier.pattern}\s+"
            rf"(?P<alias>{self._identifier}){alias_end}",
        )

        for pattern in patterns:
            for match in re.finditer(pattern, sql, re.IGNORECASE):
                aliases.add(
                    self._normalize_identifier(match.group("alias"))
                )

        return aliases

    def _derived_column_aliases(self, sql: str) -> set[str]:
        aliases: set[str] = set()
        pattern = (
            rf"\)\s*(?:as\s+)?{self._identifier}\s*\("
            rf"(?P<columns>{self._identifier}(?:\s*,\s*"
            rf"{self._identifier})*)\)"
        )

        for match in re.finditer(pattern, sql, re.IGNORECASE):
            columns = match.group("columns").split(",")
            aliases.update(
                self._normalize_identifier(column)
                for column in columns
            )

        return aliases

    def _assert_column_allowed(
        self,
        table: str,
        column: str,
        allowed_columns: dict[str, set[str]],
    ) -> None:
        columns = allowed_columns.get(table)

        if columns is None:
            raise ValueError(
                f"A tabela {table} não possui colunas autorizadas no catálogo."
            )

        if column not in columns:
            raise ValueError(
                f"A coluna {table}.{column} não está autorizada no catálogo."
            )

    def _table_aliases(
        self,
        sql: str,
        table_references: list[re.Match[str]],
        cte_names: set[str],
        database: str | None,
    ) -> dict[str, str | None]:
        aliases: dict[str, str | None] = {
            name: name for name in cte_names
        }

        for reference in table_references:
            table = self._table_name(reference.group("table"))

            if self._is_allowed_native_table_function(
                sql,
                reference,
                database,
            ):
                aliases[table] = None
                continue

            aliases[table] = table

            alias = reference.group("alias")
            if alias:
                normalized_alias = self._normalize_identifier(alias)
                if normalized_alias not in self._keywords:
                    aliases[normalized_alias] = table

        aliases.update(self._subquery_aliases(sql))
        aliases.update(
            self._native_table_function_aliases(
                sql,
                table_references,
                database,
            )
        )
        return aliases

    def _native_table_function_aliases(
        self,
        sql: str,
        table_references: list[re.Match[str]],
        database: str | None,
    ) -> dict[str, None]:
        aliases: dict[str, None] = {}

        for reference in table_references:
            if not self._is_allowed_native_table_function(
                sql,
                reference,
                database,
            ):
                continue

            opening_parenthesis = self._next_opening_parenthesis(
                sql,
                reference.end(),
            )
            if opening_parenthesis is None:
                continue

            closing_parenthesis = self._matching_parenthesis(
                sql,
                opening_parenthesis,
            )
            if closing_parenthesis is None:
                function_name = self._qualified_name(
                    reference.group("table")
                )
                raise ValueError(
                    f"A chamada nativa {function_name} possui parenteses "
                    "desbalanceados."
                )

            alias_match = re.match(
                rf"\s*(?:as\s+)?(?P<alias>{self._identifier})",
                sql[closing_parenthesis + 1 :],
                re.IGNORECASE,
            )
            if not alias_match:
                continue

            alias = self._normalize_identifier(alias_match.group("alias"))
            if alias not in self._keywords:
                aliases[alias] = None

        return aliases

    def _is_allowed_native_table_function(
        self,
        sql: str,
        reference: re.Match[str],
        database: str | None,
    ) -> bool:
        if database is None:
            return False

        function_name = self._qualified_name(reference.group("table"))
        allowed_functions = self._native_table_functions.get(
            self._database_name(database),
            frozenset(),
        )
        if function_name not in allowed_functions:
            return False

        return self._next_opening_parenthesis(sql, reference.end()) is not None

    def _next_opening_parenthesis(
        self,
        sql: str,
        start: int,
    ) -> int | None:
        index = start

        while index < len(sql) and sql[index].isspace():
            index += 1

        if index >= len(sql) or sql[index] != "(":
            return None

        return index

    def _subquery_aliases(self, sql: str) -> dict[str, None]:
        aliases = {}
        starts = re.finditer(
            r"\b(?:from|join)\s*\(",
            sql,
            re.IGNORECASE,
        )

        for start in starts:
            opening_parenthesis = sql.find("(", start.start(), start.end())
            closing_parenthesis = self._matching_parenthesis(
                sql,
                opening_parenthesis,
            )
            if closing_parenthesis is None:
                continue

            alias_match = re.match(
                rf"\s*(?:as\s+)?(?P<alias>{self._identifier})",
                sql[closing_parenthesis + 1 :],
                re.IGNORECASE,
            )
            if not alias_match:
                continue

            alias = self._normalize_identifier(alias_match.group("alias"))
            if alias not in self._keywords:
                aliases[alias] = None

        return aliases

    def _matching_parenthesis(
        self,
        sql: str,
        opening_parenthesis: int,
    ) -> int | None:
        depth = 0
        index = opening_parenthesis

        while index < len(sql):
            character = sql[index]

            if character == "'":
                index = self._skip_string_literal(sql, index)
                continue

            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    return index

            index += 1

        return None

    def _skip_string_literal(self, sql: str, start: int) -> int:
        index = start + 1

        while index < len(sql):
            if sql[index] != "'":
                index += 1
                continue

            if index + 1 < len(sql) and sql[index + 1] == "'":
                index += 2
                continue

            return index + 1

        return len(sql)

    def _cte_names(self, sql: str) -> set[str]:
        return {
            self._normalize_identifier(match.group("name"))
            for match in self._cte_reference.finditer(sql)
        }

    def parameter_names(self, sql: str) -> set[str]:
        masked_sql = self._mask_literals(sql)
        return {
            match.group("name")
            for match in self._parameter.finditer(masked_sql)
        }

    def _normalize_postgres_parameter_casts(self, sql: str) -> str:
        masked_sql = self._mask_literals(sql)
        matches = list(self._postgres_parameter_cast.finditer(masked_sql))

        if not matches:
            return sql

        parts: list[str] = []
        previous_end = 0

        for match in matches:
            parts.append(sql[previous_end:match.start()])
            parts.append(
                f"CAST(:{match.group('name')} AS {match.group('type')})"
            )
            previous_end = match.end()

        parts.append(sql[previous_end:])
        return "".join(parts)

    def _qualified_identifier_spans(self, sql: str) -> list[tuple[int, int]]:
        return [
            reference.span()
            for reference in self._qualified_identifier.finditer(sql)
        ]

    def _mask_literals(self, sql: str) -> str:
        return self._string_literal.sub(
            lambda match: " " * len(match.group(0)),
            sql,
        )

    def _mask_spans(
        self,
        sql: str,
        spans: list[tuple[int, int]],
    ) -> str:
        characters = list(sql)

        for start, end in spans:
            for index in range(start, end):
                characters[index] = " "

        return "".join(characters)

    def _inside_span(
        self,
        target: tuple[int, int],
        spans: list[tuple[int, int]],
    ) -> bool:
        return any(
            start <= target[0] and target[1] <= end
            for start, end in spans
        )

    def _database_name(self, database: str | None) -> str:
        if database is None:
            return ""

        return str(getattr(database, "value", database)).lower()

    def _table_name(self, identifier: str) -> str:
        parts = identifier.split(".")
        return self._normalize_identifier(parts[-1])

    def _qualified_name(self, identifier: str) -> str:
        return ".".join(
            self._normalize_identifier(part)
            for part in identifier.split(".")
        )

    def _normalize_identifier(self, identifier: str) -> str:
        value = identifier.strip().strip('"`[]')
        return value.lower()

    def _normalize_value(self, value: Any) -> str:
        if value is None:
            return ""

        return " ".join(str(value).strip().casefold().split())

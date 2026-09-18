import io
import json

from hypothesis import assume, given
from hypothesis import strategies as st
from openpyxl import Workbook

from app.core.errors import DomainError
from app.services.source_parser import parse_csv, parse_excel, parse_json


@st.composite
def bounded_workbook(draw: st.DrawFn) -> bytes:
    headers = draw(
        st.lists(
            st.from_regex(r"[a-z]{1,8}", fullmatch=True),
            min_size=1,
            max_size=4,
            unique=True,
        )
    )
    values = draw(
        st.lists(
            st.lists(
                st.one_of(
                    st.integers(min_value=-100, max_value=100),
                    st.text(alphabet="abc123", max_size=8),
                    st.none(),
                ),
                min_size=0,
                max_size=len(headers),
            ),
            min_size=0,
            max_size=6,
        )
    )
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in values:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


@given(
    st.lists(
        st.lists(
            st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789 _-", min_size=1, max_size=12),
            min_size=1,
            max_size=6,
        ),
        min_size=2,
        max_size=20,
    )
)
def test_csv_parser_preserves_row_count_with_bounded_rectangular_data(
    matrix: list[list[str]],
) -> None:
    width = max(len(row) for row in matrix)
    normalized = [row + [""] * (width - len(row)) for row in matrix]
    normalized_headers = [
        value.strip() or f"coluna_{index + 1}"
        for index, value in enumerate(normalized[0])
    ]
    assume(len(normalized_headers) == len(set(normalized_headers)))
    content = (
        ";".join(normalized[0])
        + "\n"
        + "\n".join(";".join(row) for row in normalized[1:])
    ).encode()

    rows, schema = parse_csv(
        content,
        {"delimiter": ";", "encoding": "utf-8"},
        max_rows=20,
        max_columns=12,
    )

    assert len(rows) == max(len(normalized) - 1, 0)
    assert schema["row_count"] == len(rows)
    assert len(schema["columns"]) <= width


@given(
    st.lists(
        st.dictionaries(st.text(min_size=1, max_size=12), st.integers(), max_size=20),
        min_size=1,
        max_size=10,
    )
)
def test_json_parser_accepts_bounded_object_records(records: list[dict[str, int]]) -> None:
    assume(len({key for record in records for key in record}) <= 20)
    rows, schema = parse_json(
        json.dumps(records).encode(),
        {"allow_missing_fields": True},
        max_rows=10,
        max_columns=20,
        max_depth=6,
    )

    assert len(rows) == len(records)
    assert schema["row_count"] == len(records)


def test_json_property_boundary_rejects_nested_arrays_without_explicit_strategy() -> None:
    try:
        parse_json(
            b'{"items":[{"id":1,"tags":["a"]}]}',
            {"root_path": "$.items"},
            max_rows=10,
            max_columns=10,
            max_depth=6,
        )
    except DomainError as exc:
        assert exc.code == "invalid_source_file"
    else:
        raise AssertionError("nested arrays must require an explicit strategy")


@given(bounded_workbook())
def test_excel_parser_stays_within_configured_bounds(content: bytes) -> None:
    rows, schema = parse_excel(
        content,
        {"extension": ".xlsx"},
        max_rows=10,
        max_columns=6,
    )

    assert len(rows) <= 10
    assert schema["row_count"] == len(rows)
    assert len(schema["columns"]) <= 6

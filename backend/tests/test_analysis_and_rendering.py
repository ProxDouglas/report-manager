import json

from app.services.analysis import analyze_rows, protect_rows
from app.services.rendering import render_csv, render_pdf, render_screen, render_xlsx


def test_grouped_metrics_and_renderers() -> None:
    rows = [
        {"categoria": "A", "valor": 10, "cpf": "12345678909"},
        {"categoria": "A", "valor": 20, "cpf": "12345678909"},
        {"categoria": "B", "valor": 7, "cpf": "98765432100"},
    ]
    analyzed = analyze_rows(
        rows,
        {
            "group_by": ["categoria"],
            "metrics": [{"name": "total", "field": "valor", "operation": "sum"}],
        },
        100,
    )
    protected = protect_rows(analyzed)
    assert protected == [{"categoria": "A", "total": 30.0}, {"categoria": "B", "total": 7.0}]
    assert b"categoria" in render_csv(protected)
    assert render_xlsx(protected).startswith(b"PK")
    assert render_pdf("Teste", 1, protected).startswith(b"%PDF")
    screen = json.loads(render_screen(protected))
    assert screen["row_count"] == 2

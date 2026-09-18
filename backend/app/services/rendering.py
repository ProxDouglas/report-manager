from __future__ import annotations

import csv
import io
import json
from copy import copy
from typing import Any

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return columns


def render_screen(rows: list[dict[str, Any]]) -> bytes:
    return json.dumps(
        {"columns": _columns(rows), "rows": rows, "row_count": len(rows)},
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def render_csv(rows: list[dict[str, Any]]) -> bytes:
    columns = _columns(rows)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def render_xlsx(rows: list[dict[str, Any]]) -> bytes:
    columns = _columns(rows)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Relatorio"
    sheet.append(columns)
    for row in rows:
        sheet.append([row.get(column) for column in columns])
    sheet.freeze_panes = "A2"
    for cell in sheet[1]:
        font = copy(cell.font)
        font.bold = True
        cell.font = font
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def render_pdf(title: str, version_number: int, rows: list[dict[str, Any]]) -> bytes:
    columns = _columns(rows)
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm
    )
    styles = getSampleStyleSheet()
    content: list[Any] = [
        Paragraph(title, styles["Title"]),
        Paragraph(f"Versão {version_number}", styles["Normal"]),
        Spacer(1, 8),
    ]
    values = [columns] + [[str(row.get(column, "")) for column in columns] for row in rows]
    table = Table(values, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    content.append(table)
    document.build(content)
    return output.getvalue()


def render_chart(rows: list[dict[str, Any]], configuration: dict[str, Any]) -> bytes:
    import os

    os.environ.setdefault("MPLCONFIGDIR", "/tmp/report-manager-matplotlib")
    os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    chart_type = str(configuration.get("type", "bar")).lower()
    x_field = str(configuration.get("x", ""))
    y_field = str(configuration.get("y", ""))
    labels = [str(row.get(x_field, "")) for row in rows]
    values = [row.get(y_field, 0) for row in rows]
    figure, axis = plt.subplots(figsize=(10, 5))
    if chart_type == "line":
        axis.plot(labels, values, marker="o")
    else:
        axis.bar(labels, values)
    axis.set_xlabel(x_field)
    axis.set_ylabel(y_field)
    axis.tick_params(axis="x", rotation=30)
    figure.tight_layout()
    output = io.BytesIO()
    figure.savefig(output, format="png", dpi=140)
    plt.close(figure)
    return output.getvalue()

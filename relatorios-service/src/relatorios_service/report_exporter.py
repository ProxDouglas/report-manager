import json
from pathlib import Path

import pandas as pd
import plotly.io as plotly_io

from relatorios_service.config import settings
from relatorios_service.schemas import ExportFormat


class ReportExporter:
    def __init__(self) -> None:
        self.base_directory = Path(settings.reports_directory)

    def export(
        self,
        report_id: str,
        dataframe: pd.DataFrame,
        formats: list[ExportFormat],
        chart: dict | None = None,
    ) -> list[dict[str, str]]:
        report_directory = self.base_directory / report_id
        report_directory.mkdir(parents=True, exist_ok=True)
        files = []

        for file_format in formats:
            path = report_directory / f"analysis.{file_format.value}"

            if file_format is ExportFormat.CSV:
                dataframe.to_csv(path, index=False, encoding="utf-8-sig")

            if file_format is ExportFormat.XLSX:
                dataframe.to_excel(path, index=False)

            files.append(
                {
                    "format": file_format.value,
                    "filename": path.name,
                    "url": f"/reports/{report_id}/{file_format.value}",
                }
            )

        if chart is not None:
            self._export_chart(report_directory, report_id, chart, files)

        return files

    def _export_chart(
        self,
        report_directory: Path,
        report_id: str,
        chart: dict,
        files: list[dict[str, str]],
    ) -> None:
        chart_json_path = report_directory / "chart.json"
        chart_html_path = report_directory / "chart.html"

        chart_json_path.write_text(
            json.dumps(chart, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        figure = plotly_io.from_json(json.dumps(chart))
        chart_html_path.write_text(
            plotly_io.to_html(
                figure,
                full_html=True,
                include_plotlyjs=True,
            ),
            encoding="utf-8",
        )

        files.extend(
            [
                {
                    "format": "chart.json",
                    "filename": chart_json_path.name,
                    "url": f"/reports/{report_id}/chart.json",
                },
                {
                    "format": "chart.html",
                    "filename": chart_html_path.name,
                    "url": f"/reports/{report_id}/chart.html",
                },
            ]
        )

    def path_for(self, report_id: str, file_format: ExportFormat) -> Path:
        return self.base_directory / report_id / f"analysis.{file_format.value}"

    def chart_path(self, report_id: str, extension: str) -> Path:
        return self.base_directory / report_id / f"chart.{extension}"

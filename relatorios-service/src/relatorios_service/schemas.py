from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    AUTO = "auto"
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"
    TABLE = "table"


class ExportFormat(str, Enum):
    CSV = "csv"
    XLSX = "xlsx"


class DataParser(str, Enum):
    PASSTHROUGH = "passthrough"
    NUMERIC = "numeric"
    NUMERIC_TEXT = "numeric_text"
    WEEKLY_24H_JSON = "weekly_24h_json"
    COMMA_SEPARATED_24H = "comma_separated_24h"


class DataErrorPolicy(str, Enum):
    QUARANTINE = "quarantine"
    FAIL = "fail"


class SemanticValueType(str, Enum):
    TEXT = "text"
    DATE = "date"
    NUMBER = "number"
    BOOLEAN = "boolean"


class ChartAxis(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class CompositionMode(str, Enum):
    ALIGNED = "aligned"
    SERIES = "series"


class PeriodGranularity(str, Enum):
    DATE = "date"
    MONTH = "month"
    YEAR = "year"


class SemanticMapping(BaseModel):
    table: str
    column: str
    aliases: list[str] = Field(default_factory=list)
    parameter: str | None = None
    value_type: SemanticValueType = SemanticValueType.TEXT
    description: str = ""


class AnalysisRequest(BaseModel):
    question: str = Field(min_length=5)
    chart_type: ChartType | None = None
    export_formats: list[ExportFormat] = Field(default_factory=list)


class ComparisonPeriod(BaseModel):
    label: str
    start: date
    end: date


class PeriodSpec(BaseModel):
    granularity: PeriodGranularity | None = None
    start: date | None = None
    end: date | None = None
    comparisons: list[ComparisonPeriod] = Field(default_factory=list)


class AnalysisComponent(BaseModel):
    id: str = "component_1"
    metric: str = "generic_analysis"
    tables: list[str] = Field(default_factory=list)
    measures: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    period: PeriodSpec | None = None
    label: str | None = None


class CompositionSpec(BaseModel):
    mode: CompositionMode = CompositionMode.ALIGNED
    keys: list[str] = Field(default_factory=list)


class ChartSeries(BaseModel):
    column: str
    chart_type: ChartType = ChartType.AUTO
    axis: ChartAxis = ChartAxis.PRIMARY
    label: str | None = None
    component_id: str | None = None


class ChartSpec(BaseModel):
    chart_type: ChartType = ChartType.AUTO
    x: str | None = None
    color: str | None = None
    series: list[ChartSeries] = Field(default_factory=list)
    title: str | None = None


class AnalysisPlan(BaseModel):
    # Campos legados mantidos para compatibilidade com clientes existentes.
    metric: str = "generic_analysis"
    tables: list[str] = Field(default_factory=list)
    measures: list[str] = Field(default_factory=list)
    group_by: str | None = None
    chart_type: ChartType = ChartType.AUTO
    filters: dict[str, Any] = Field(default_factory=dict)
    requested_exports: list[ExportFormat] = Field(default_factory=list)
    reasoning: str = ""
    components: list[AnalysisComponent] = Field(default_factory=list)
    composition: CompositionSpec = Field(default_factory=CompositionSpec)
    chart: ChartSpec | None = None


class SqlPlan(BaseModel):
    sql: str
    explanation: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)


class MeasureDefinition(BaseModel):
    table: str | None = None
    tables: list[str] = Field(default_factory=list)
    column: str | None = None
    columns: list[str] = Field(default_factory=list)
    parser: DataParser = DataParser.PASSTHROUGH
    input_type: str | None = None
    json_path: list[str] = Field(default_factory=list)
    unit: str | None = None
    hours_per_day: int | None = None
    required_days: list[str] = Field(default_factory=list)
    raw_alias: str | None = None
    date_alias: str | None = None
    on_error: DataErrorPolicy = DataErrorPolicy.FAIL
    example_value: Any | None = None


class ColumnDefinition(BaseModel):
    description: str = ""
    example_value: Any | None = None


class TableDefinition(BaseModel):
    description: str = ""
    columns: dict[str, ColumnDefinition] = Field(default_factory=dict)


class MetricDefinition(BaseModel):
    key: str
    label: str
    description: str
    business_rule: str
    tables: dict[str, TableDefinition] = Field(default_factory=dict)
    allowed_tables: list[str] = Field(default_factory=list)
    known_columns: list[str] = Field(default_factory=list)
    allowed_dimensions: list[str] = Field(default_factory=list)
    allowed_measures: list[str] = Field(default_factory=list)
    measures: dict[str, "MeasureDefinition"] = Field(default_factory=dict)
    semantic_mappings: dict[str, SemanticMapping] = Field(
        default_factory=dict
    )
    synonyms: list[str] = Field(default_factory=list)
    source_mapping: dict[str, str] = Field(default_factory=dict)
    allowed_columns: dict[str, list[str]] = Field(default_factory=dict)
    table_descriptions: dict[str, str] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.tables:
            return

        self.allowed_tables = list(self.tables)
        self.allowed_columns = {
            table: list(definition.columns)
            for table, definition in self.tables.items()
        }
        self.known_columns = list(
            dict.fromkeys(
                column
                for definition in self.tables.values()
                for column in definition.columns
            )
        )
        self.table_descriptions = {
            table: definition.description
            for table, definition in self.tables.items()
        }


class AnalysisResult(BaseModel):
    report_id: str
    answer: str
    plan: AnalysisPlan
    sql: str
    sqls: list[str] = Field(default_factory=list)
    row_count: int
    truncated: bool
    data: list[dict[str, Any]]
    chart: dict[str, Any] | None = None
    files: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)

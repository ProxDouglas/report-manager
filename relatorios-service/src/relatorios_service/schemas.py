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


class AnalysisPlan(BaseModel):
    metric: str
    tables: list[str] = Field(default_factory=list)
    measures: list[str] = Field(default_factory=list)
    group_by: str | None = None
    chart_type: ChartType = ChartType.AUTO
    filters: dict[str, str] = Field(default_factory=dict)
    requested_exports: list[ExportFormat] = Field(default_factory=list)
    reasoning: str = ""


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


class MetricDefinition(BaseModel):
    key: str
    label: str
    description: str
    business_rule: str
    allowed_tables: list[str]
    known_columns: list[str]
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


class AnalysisResult(BaseModel):
    report_id: str
    answer: str
    plan: AnalysisPlan
    sql: str
    row_count: int
    truncated: bool
    data: list[dict[str, Any]]
    chart: dict[str, Any] | None = None
    files: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)

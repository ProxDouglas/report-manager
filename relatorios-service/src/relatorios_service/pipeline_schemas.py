from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Reference = Annotated[str, Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")]
DatasetId = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
Columns = Annotated[list[str], Field(min_length=1, max_length=500)]


class PipelineModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Autonomy(str, Enum):
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"


class PipelineMode(str, Enum):
    SEPARATE = "separate"
    JOINED = "joined"


class PipelineStatus(str, Enum):
    READY = "ready"
    AWAITING_DECISION = "awaiting_decision"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DecisionAction(str, Enum):
    APPROVE = "approve"
    DELEGATE_STEP = "delegate_step"
    DELEGATE_REMAINING = "delegate_remaining"
    CANCEL = "cancel"


class Operation(str, Enum):
    TRIM = "trim"
    NULL_MARKERS = "null_markers"
    CAST = "cast"
    DROP_NULLS = "drop_nulls"
    DEDUPLICATE = "deduplicate"
    FILL_NULLS = "fill_nulls"
    SELECT = "select"
    JOIN = "join"
    FILTER = "filter"
    SPLIT_EXPLODE = "split_explode"
    AGGREGATE = "aggregate"
    BUCKET = "bucket"
    EXTRACT_MEASUREMENTS = "extract_measurements"


class FilterOperator(str, Enum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    NOT_IN = "not_in"
    GT = "gt"
    GE = "ge"
    LT = "lt"
    LE = "le"
    IS_NULL = "is_null"
    NOT_NULL = "not_null"


class FilterMatch(str, Enum):
    ALL = "all"
    ANY = "any"


class AggregateFunction(str, Enum):
    SIZE = "size"
    COUNT = "count"
    NUNIQUE = "nunique"
    SUM = "sum"
    MEAN = "mean"
    MEDIAN = "median"
    MIN = "min"
    MAX = "max"


class BucketScale(str, Enum):
    NUMBER = "number"
    PERCENT = "percent"
    FRACTION = "fraction"
    PERCENT_TEXT = "percent_text"


class PipelineChartType(str, Enum):
    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    SCATTER = "scatter"


class ValueType(str, Enum):
    TEXT = "text"
    INTEGER = "integer"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"


class ErrorPolicy(str, Enum):
    FAIL = "fail"
    NULL = "null"


class NumberFormat(str, Enum):
    STANDARD = "standard"
    BRAZILIAN = "brazilian"


class DateFormat(str, Enum):
    ISO = "%Y-%m-%d"
    ISO_TIME = "%Y-%m-%d %H:%M:%S"
    ISO_T_TIME = "%Y-%m-%dT%H:%M:%S"
    YEAR_SLASH = "%Y/%m/%d"
    DAY_SLASH = "%d/%m/%Y"
    DAY_SLASH_TIME = "%d/%m/%Y %H:%M:%S"
    DAY_DASH = "%d-%m-%Y"


class DuplicateKeep(str, Enum):
    FIRST = "first"
    LAST = "last"
    NONE = "none"


class FillStrategy(str, Enum):
    MEAN = "mean"
    MEDIAN = "median"
    MODE = "mode"
    ZERO = "zero"


class JoinType(str, Enum):
    INNER = "inner"
    LEFT = "left"
    RIGHT = "right"
    OUTER = "outer"


class Cardinality(str, Enum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    MANY_TO_MANY = "many_to_many"


class DatasetInput(PipelineModel):
    alias: Reference
    dataset_id: DatasetId


class Language(str, Enum):
    ENGLISH = "en"
    PORTUGUESE = "pt-BR"


class PipelineRequest(PipelineModel):
    language: Language = Language.ENGLISH
    datasets: list[DatasetInput] = Field(min_length=1, max_length=10)
    prompt: str = Field(default="", max_length=4000)
    mode: PipelineMode = PipelineMode.SEPARATE
    autonomy: Autonomy = Autonomy.SUPERVISED
    allow_data_sample: bool = False

    @model_validator(mode="after")
    def validate_inputs(self):
        aliases = [item.alias for item in self.datasets]
        if len(set(aliases)) != len(aliases):
            raise ValueError("Os aliases dos datasets precisam ser únicos.")
        if self.mode == PipelineMode.JOINED and len(aliases) < 2:
            raise ValueError("O modo joined exige pelo menos dois datasets.")
        return self


class Step(PipelineModel):
    id: Reference
    # A justificativa usa somente metadados; nunca é executada como código.
    reason: str = Field(min_length=1, max_length=1000)


class InputStep(Step):
    input: Reference


class ColumnStep(InputStep):
    columns: Columns

    @model_validator(mode="after")
    def unique_columns(self):
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("Não repita colunas na mesma etapa.")
        return self


class TrimStep(ColumnStep):
    operation: Literal[Operation.TRIM]


class NullMarkersStep(ColumnStep):
    operation: Literal[Operation.NULL_MARKERS]


class CastStep(ColumnStep):
    operation: Literal[Operation.CAST]
    target: ValueType
    errors: ErrorPolicy = ErrorPolicy.FAIL
    number_format: NumberFormat = NumberFormat.STANDARD
    date_format: DateFormat | None = None
    strip_percent: bool = False

    @model_validator(mode="after")
    def explicit_date_format(self):
        if self.target == ValueType.DATE and self.date_format is None:
            raise ValueError("A conversão de datas exige formato explícito.")
        if self.strip_percent and self.target not in {ValueType.INTEGER, ValueType.NUMBER}:
            raise ValueError("strip_percent exige conversão numérica.")
        return self


class DropNullsStep(ColumnStep):
    operation: Literal[Operation.DROP_NULLS]


class DeduplicateStep(ColumnStep):
    operation: Literal[Operation.DEDUPLICATE]
    keep: DuplicateKeep = DuplicateKeep.FIRST


class FillNullsStep(ColumnStep):
    operation: Literal[Operation.FILL_NULLS]
    strategy: FillStrategy


class SelectStep(ColumnStep):
    operation: Literal[Operation.SELECT]


class FilterCondition(PipelineModel):
    column: str
    operator: FilterOperator
    values: list[str | int | Annotated[float, Field(allow_inf_nan=False)] | bool] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def validate_values(self):
        expected = 1
        if self.operator in {FilterOperator.IS_NULL, FilterOperator.NOT_NULL}:
            expected = 0
        elif self.operator in {FilterOperator.IN, FilterOperator.NOT_IN}:
            if not self.values:
                raise ValueError("Filtros de pertinência exigem valores.")
            return self
        if len(self.values) != expected:
            raise ValueError("Quantidade de valores incompatível com o operador.")
        return self


class FilterStep(InputStep):
    operation: Literal[Operation.FILTER]
    conditions: list[FilterCondition] = Field(min_length=1, max_length=30)
    match: FilterMatch = FilterMatch.ALL


class SplitExplodeStep(InputStep):
    operation: Literal[Operation.SPLIT_EXPLODE]
    column: str
    separator: str = Field(min_length=1, max_length=20)
    strip: bool = True


class ExtractMeasurementsStep(InputStep):
    operation: Literal[Operation.EXTRACT_MEASUREMENTS]
    column: str
    pairs: int = Field(ge=1, le=10)
    number_format: NumberFormat = NumberFormat.STANDARD
    errors: ErrorPolicy = ErrorPolicy.FAIL


class AggregateMetric(PipelineModel):
    function: AggregateFunction
    column: str | None = None
    alias: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_column(self):
        if self.function == AggregateFunction.SIZE:
            if self.column is not None:
                raise ValueError("size conta linhas e não recebe coluna.")
        elif self.column is None:
            raise ValueError("A agregação exige uma coluna.")
        return self


class AggregateStep(InputStep):
    operation: Literal[Operation.AGGREGATE]
    group_by: list[str] = Field(default_factory=list, max_length=500)
    metrics: list[AggregateMetric] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_names(self):
        names = self.group_by + [metric.alias for metric in self.metrics]
        if len(names) != len(set(names)):
            raise ValueError("Agrupamentos e aliases devem ser únicos.")
        return self


class BucketStep(InputStep):
    operation: Literal[Operation.BUCKET]
    column: str
    output_column: str = Field(min_length=1, max_length=100)
    scale: BucketScale = BucketScale.NUMBER
    edges: list[Annotated[float, Field(allow_inf_nan=False)]] = Field(min_length=2, max_length=101)
    labels: list[str] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_ranges(self):
        if any(left >= right for left, right in zip(self.edges, self.edges[1:])):
            raise ValueError("Os limites das faixas devem ser estritamente crescentes.")
        if len(self.labels) != len(self.edges) - 1 or len(set(self.labels)) != len(self.labels):
            raise ValueError("Cada faixa exige um rótulo único.")
        if self.scale != BucketScale.NUMBER and (self.edges[0] != 0 or self.edges[-1] != 100):
            raise ValueError("Faixas percentuais devem cobrir de 0 a 100.")
        return self


class JoinStep(Step):
    operation: Literal[Operation.JOIN]
    left: Reference
    right: Reference
    left_on: Columns
    right_on: Columns
    how: JoinType = JoinType.LEFT
    cardinality: Cardinality = Cardinality.MANY_TO_ONE

    @model_validator(mode="after")
    def validate_keys(self):
        if len(self.left_on) != len(self.right_on):
            raise ValueError("As chaves do join precisam ter o mesmo tamanho.")
        if (len(set(self.left_on)) != len(self.left_on)
                or len(set(self.right_on)) != len(self.right_on)):
            raise ValueError("As chaves do join não podem ser repetidas.")
        return self


PipelineStep = Annotated[
    TrimStep | NullMarkersStep | CastStep | DropNullsStep | DeduplicateStep
    | FillNullsStep | SelectStep | JoinStep | FilterStep | SplitExplodeStep
    | AggregateStep | BucketStep | ExtractMeasurementsStep,
    Field(discriminator="operation"),
]


class PipelineChart(PipelineModel):
    reference: Reference
    x: str
    y: str
    chart_type: PipelineChartType = PipelineChartType.BAR


class PipelinePlan(PipelineModel):
    steps: list[PipelineStep] = Field(max_length=30)
    outputs: list[Reference] = Field(min_length=1, max_length=10)
    charts: list[PipelineChart] = Field(default_factory=list, max_length=10)
    limitations: list[str] = Field(default_factory=list, max_length=20)


class PipelineDecision(PipelineModel):
    step_id: Reference
    action: DecisionAction
    replacement: PipelineStep | None = None

    @model_validator(mode="after")
    def validate_replacement(self):
        if self.replacement is not None:
            if self.action != DecisionAction.APPROVE:
                raise ValueError("Somente approve permite ajustar uma etapa.")
            if self.replacement.id != self.step_id:
                raise ValueError("O ajuste deve preservar o identificador da etapa.")
        return self


class DecisionPrompt(PipelineModel):
    step_id: Reference
    question: str = "Você decide esta etapa ou delega a decisão ao sistema?"
    actions: list[DecisionAction] = Field(
        default_factory=lambda: list(DecisionAction),
    )


class StepReport(PipelineModel):
    step_id: Reference
    decided_by: Autonomy
    input_rows: list[int]
    output_rows: int
    null_count: int


class PipelineOutput(PipelineModel):
    reference: Reference
    dataset_id: DatasetId
    row_count: int
    columns: list[str]


class StepRevision(PipelineModel):
    replacement: PipelineStep
    expected_revision: int = Field(ge=0)


class StepPreview(PipelineModel):
    step_id: Reference
    columns: list[str]
    rows: list[list[str | None]]
    row_count: int


class PipelineState(PipelineModel):
    revision: int = Field(default=0, ge=0)
    id: DatasetId
    request: PipelineRequest
    plan: PipelinePlan
    status: PipelineStatus = PipelineStatus.READY
    next_step: int = 0
    pending_decision: DecisionPrompt | None = None
    reports: list[StepReport] = Field(default_factory=list)
    outputs: list[PipelineOutput] = Field(default_factory=list)
    error: str | None = None

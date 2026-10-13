import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd

from relatorios_service.database import DatabaseType
from relatorios_service.schemas import (
    AnalysisComponent,
    AnalysisPlan,
    AnalysisRequest,
    ChartSeries,
    ChartSpec,
    ChartType,
    ColumnDefinition,
    CompositionMode,
    CompositionSpec,
    DataParser,
    ExportFormat,
    MetricDefinition,
    MeasureDefinition,
    PeriodGranularity,
    PeriodSpec,
    SemanticValueType,
    SqlPlan,
    TableDefinition,
)
from relatorios_service.domain.charts import (
    chart_x_dimension,
    default_chart_spec,
    override_chart_type,
)
from relatorios_service.domain.composition import (
    ComponentExecution,
    compose_components,
)
from relatorios_service.domain.measures import (
    derive_composed_measures,
    derive_measures,
    normalize_measure_columns,
    validate_result,
)
from relatorios_service.domain.period import (
    normalize_period_intent,
    question_mentions_month,
)
from relatorios_service.domain.planning import normalize_plan
from relatorios_service.domain.rules import (
    generic_required_tables,
    resolve_tables,
    validate_plan,
    validate_sql_semantics,
)
from relatorios_service.services.parameter_binder import ParameterBinder
from relatorios_service.services.analysis_service import (
    AnalysisService,
)
from relatorios_service.services.normalization import DataNormalizer


ALL_HOURS = " + ".join(f"hor_{hour:02d}" for hour in range(24))


def build_service(audit_log_path: Path | None = None) -> AnalysisService:
    return AnalysisService(
        analytics_repository=Mock(),
        model=Mock(),
        catalog=Mock(),
        exporter=Mock(),
        max_analysis_rows=10000,
        audit_log_path=audit_log_path,
    )


def build_metric() -> MetricDefinition:
    table_names = [
        "distribuicao",
        "funcionario",
        "empresa",
        "filial",
        "configuracao",
        "restr_emp",
        "restr_fil",
        "restr_posto",
        "restr_ccusto",
        "restr_subf",
    ]
    return MetricDefinition(
        key="generic_analysis",
        label="Análise genérica",
        description="Alocação e demanda de colaboradores.",
        business_rule="Regra de teste.",
        tables={
            name: TableDefinition(columns={"id": ColumnDefinition()})
            for name in table_names
        },
        allowed_dimensions=[
            "month",
            "date",
            "branch",
            "workplace",
            "company",
            "employee",
            "cost_center",
            "subfunction",
        ],
        allowed_measures=["allocation_hours", "demand_hours", "employee_count"],
    )


def make_execution(
    component_id: str,
    dataframe: pd.DataFrame,
    measures: list[str] | None = None,
    label: str | None = None,
) -> ComponentExecution:
    return ComponentExecution(
        component=AnalysisComponent(
            id=component_id,
            measures=measures or [],
            label=label,
        ),
        dataframe=dataframe,
        sql="SELECT 1",
        warnings=[],
    )


class PeriodIntentTests(unittest.TestCase):
    def setUp(self):
        self.component = AnalysisComponent(id="component_1", dimensions=["branch"])

    def test_year_in_question_creates_yearly_period_with_exclusive_end(self):
        result = normalize_period_intent(
            self.component,
            "Qual a alocação em 2026?",
        )

        self.assertEqual(result.period.granularity, PeriodGranularity.YEAR)
        self.assertEqual(result.period.start, date(2026, 1, 1))
        self.assertEqual(result.period.end, date(2027, 1, 1))
        self.assertEqual(result.dimensions, ["branch"])

    def test_month_mention_with_year_creates_monthly_period_and_dimension(self):
        result = normalize_period_intent(
            self.component,
            "Mostre a alocação por mês em 2026",
        )

        self.assertEqual(result.period.granularity, PeriodGranularity.MONTH)
        self.assertEqual(result.dimensions, ["branch", "month"])

    def test_explicit_month_overrides_year_period_with_exclusive_month_end(self):
        component = self.component.model_copy(
            update={
                "dimensions": ["date", "month"],
                "period": PeriodSpec(
                    granularity=PeriodGranularity.MONTH,
                    start=date(2026, 1, 1),
                    end=date(2027, 1, 1),
                ),
            }
        )

        result = normalize_period_intent(
            component,
            "Horas alocadas no mês 10 de 2026",
        )

        self.assertEqual(result.period.granularity, PeriodGranularity.MONTH)
        self.assertEqual(result.period.start, date(2026, 10, 1))
        self.assertEqual(result.period.end, date(2026, 11, 1))
        self.assertEqual(result.dimensions, ["date", "month"])

    def test_named_month_creates_specific_month_period(self):
        result = normalize_period_intent(
            self.component,
            "Horas alocadas em outubro de 2026",
        )

        self.assertEqual(result.period.start, date(2026, 10, 1))
        self.assertEqual(result.period.end, date(2026, 11, 1))

    def test_two_years_in_question_leave_period_unchanged(self):
        result = normalize_period_intent(
            self.component,
            "Compare 2025 com 2026",
        )

        self.assertIsNone(result.period)
        self.assertEqual(result.dimensions, ["branch"])

    def test_month_without_year_adds_only_month_dimension(self):
        result = normalize_period_intent(
            self.component,
            "Compare as alocações por mês",
        )

        self.assertIsNone(result.period)
        self.assertEqual(result.dimensions, ["branch", "month"])

    def test_question_without_year_or_month_returns_component_unchanged(self):
        result = normalize_period_intent(
            self.component,
            "Quantos colaboradores existem?",
        )

        self.assertEqual(result, self.component)

    def test_period_ending_on_last_day_is_moved_to_exclusive_end(self):
        component = AnalysisComponent(
            id="component_1",
            period=PeriodSpec(
                granularity=PeriodGranularity.DATE,
                start=date(2026, 1, 1),
                end=date(2026, 12, 31),
            ),
        )

        result = normalize_period_intent(
            component,
            "Alocação em 2026",
        )

        self.assertEqual(result.period.end, date(2027, 1, 1))
        self.assertEqual(result.period.granularity, PeriodGranularity.DATE)

    def test_question_mentions_month_ignores_case_and_accents(self):
        self.assertTrue(question_mentions_month("Quantos MESES?"))
        self.assertTrue(question_mentions_month("Visão mensal"))
        self.assertTrue(question_mentions_month("Qual o mês?"))
        self.assertFalse(
            question_mentions_month("Quantos colaboradores?")
        )


class PlanNormalizationTests(unittest.TestCase):
    def test_plan_without_components_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "não contém componentes"):
            normalize_plan(
                AnalysisPlan(),
                AnalysisRequest(question="Alocação por mês em 2026"),
            )

    def test_analysis_plan_has_no_legacy_top_level_fields(self):
        legacy = {
            "metric",
            "tables",
            "measures",
            "group_by",
            "filters",
            "chart_type",
        }

        self.assertFalse(legacy & AnalysisPlan.model_fields.keys())

    def test_component_period_is_normalized_from_question(self):
        plan = AnalysisPlan(
            components=[
                AnalysisComponent(
                    id="a",
                    tables=["distribuicao"],
                    measures=["allocation_hours"],
                    dimensions=["month"],
                    filters={"company_name": "Acme"},
                ),
            ],
        )

        result = normalize_plan(
            plan,
            AnalysisRequest(question="Alocação por mês em 2026"),
        )

        component = result.components[0]
        self.assertEqual(component.id, "a")
        self.assertEqual(component.dimensions, ["month"])
        self.assertEqual(component.measures, ["allocation_hours"])
        self.assertEqual(component.filters, {"company_name": "Acme"})
        self.assertEqual(component.period.granularity, PeriodGranularity.MONTH)
        self.assertEqual(component.period.start, date(2026, 1, 1))
        self.assertEqual(component.period.end, date(2027, 1, 1))

    def test_duplicate_component_ids_are_rejected(self):
        plan = AnalysisPlan(
            components=[
                AnalysisComponent(id="a"),
                AnalysisComponent(id="a"),
            ],
        )

        with self.assertRaisesRegex(ValueError, "duplicado"):
            normalize_plan(plan)

    def test_blank_component_id_receives_position_based_id(self):
        plan = AnalysisPlan(
            components=[
                AnalysisComponent(id="component_1"),
                AnalysisComponent(id="   "),
            ],
        )

        result = normalize_plan(plan)

        self.assertEqual(
            [component.id for component in result.components],
            ["component_1", "component_2"],
        )

    def test_aligned_without_keys_and_multiple_components_switches_to_series(self):
        plan = AnalysisPlan(
            components=[AnalysisComponent(id="a"), AnalysisComponent(id="b")],
        )

        result = normalize_plan(plan)

        self.assertEqual(result.composition.mode, CompositionMode.SERIES)

    def test_chart_series_label_is_mapped_to_component_id(self):
        plan = AnalysisPlan(
            components=[
                AnalysisComponent(id="c1", label="Posto A"),
                AnalysisComponent(id="c2", label="Posto B"),
            ],
            chart=ChartSpec(
                series=[ChartSeries(column="demand_hours", label="posto a")],
            ),
        )

        result = normalize_plan(plan)

        self.assertEqual(result.chart.series[0].component_id, "c1")

    def test_chart_series_with_unknown_component_id_is_rejected(self):
        plan = AnalysisPlan(
            components=[AnalysisComponent(id="c1")],
            chart=ChartSpec(
                series=[ChartSeries(column="x", component_id="zz")],
            ),
        )

        with self.assertRaisesRegex(ValueError, "inexistente"):
            normalize_plan(plan)


class CompositionTests(unittest.TestCase):
    def test_single_execution_returns_its_dataframe_unchanged(self):
        dataframe = pd.DataFrame(
            {"month": ["2026-01"], "allocation_hours": [10.0]}
        )
        plan = AnalysisPlan(
            composition=CompositionSpec(
                mode=CompositionMode.ALIGNED,
                keys=["month"],
            ),
        )

        result = compose_components(
            [make_execution("a", dataframe)],
            plan,
        )

        pd.testing.assert_frame_equal(result, dataframe)

    def test_series_mode_stacks_rows_and_labels_each_component(self):
        first = make_execution(
            "a",
            pd.DataFrame({"month": ["2026-01", "2026-02"], "allocation_hours": [1.0, 2.0]}),
            label="Posto A",
        )
        second = make_execution(
            "b",
            pd.DataFrame({"month": ["2026-01"], "allocation_hours": [3.0]}),
        )
        plan = AnalysisPlan(
            composition=CompositionSpec(mode=CompositionMode.SERIES),
        )

        result = compose_components([first, second], plan)

        self.assertEqual(len(result), 3)
        self.assertEqual(
            result["analysis_component"].tolist(),
            ["a", "a", "b"],
        )
        self.assertEqual(
            result["analysis_series"].tolist(),
            ["Posto A", "Posto A", "b"],
        )

    def test_aligned_mode_merges_components_with_outer_join_on_keys(self):
        allocation = make_execution(
            "a",
            pd.DataFrame(
                {"month": ["2026-01", "2026-02"], "allocation_hours": [10.0, 20.0]}
            ),
            measures=["allocation_hours"],
        )
        demand = make_execution(
            "b",
            pd.DataFrame(
                {"month": ["2026-02", "2026-03"], "demand_hours": [15.0, 25.0]}
            ),
            measures=["demand_hours"],
        )
        plan = AnalysisPlan(
            composition=CompositionSpec(
                mode=CompositionMode.ALIGNED,
                keys=["month"],
            ),
        )

        result = compose_components([allocation, demand], plan)
        result = result.sort_values("month").reset_index(drop=True)

        self.assertEqual(
            result["month"].tolist(),
            ["2026-01", "2026-02", "2026-03"],
        )
        self.assertTrue(pd.isna(result.loc[2, "allocation_hours"]))
        self.assertTrue(pd.isna(result.loc[0, "demand_hours"]))
        self.assertEqual(result.loc[1, "demand_hours"], 15.0)

    def test_aligned_mode_requires_composition_keys(self):
        plan = AnalysisPlan(
            composition=CompositionSpec(mode=CompositionMode.ALIGNED, keys=[]),
        )
        executions = [
            make_execution("a", pd.DataFrame({"month": ["2026-01"], "x": [1.0]})),
            make_execution("b", pd.DataFrame({"month": ["2026-01"], "y": [1.0]})),
        ]

        with self.assertRaisesRegex(ValueError, "pelo menos uma chave"):
            compose_components(executions, plan)

    def test_aligned_mode_rejects_component_missing_key_column(self):
        plan = AnalysisPlan(
            composition=CompositionSpec(mode=CompositionMode.ALIGNED, keys=["month"]),
        )
        executions = [
            make_execution("a", pd.DataFrame({"month": ["2026-01"], "x": [1.0]})),
            make_execution("b", pd.DataFrame({"y": [1.0]})),
        ]

        with self.assertRaisesRegex(ValueError, "não retornou as chaves"):
            compose_components(executions, plan)

    def test_aligned_mode_rejects_duplicated_composition_keys(self):
        plan = AnalysisPlan(
            composition=CompositionSpec(mode=CompositionMode.ALIGNED, keys=["month"]),
        )
        executions = [
            make_execution(
                "a",
                pd.DataFrame({"month": ["2026-01", "2026-01"], "x": [1.0, 2.0]}),
            ),
            make_execution("b", pd.DataFrame({"month": ["2026-01"], "y": [1.0]})),
        ]

        with self.assertRaisesRegex(ValueError, "mais de uma linha"):
            compose_components(executions, plan)

    def test_aligned_mode_rejects_overlapping_measures(self):
        plan = AnalysisPlan(
            composition=CompositionSpec(mode=CompositionMode.ALIGNED, keys=["month"]),
        )
        executions = [
            make_execution(
                "a",
                pd.DataFrame({"month": ["2026-01"], "allocation_hours": [1.0]}),
                measures=["allocation_hours"],
            ),
            make_execution(
                "b",
                pd.DataFrame({"month": ["2026-01"], "allocation_hours": [2.0]}),
                measures=["allocation_hours"],
            ),
        ]

        with self.assertRaisesRegex(ValueError, "não podem sobrescrever"):
            compose_components(executions, plan)


class DerivedMeasuresTests(unittest.TestCase):
    def test_deficit_is_demand_minus_allocation_and_coverage_is_percentage(self):
        dataframe = pd.DataFrame(
            {"allocation_hours": [8.0, 10.0], "demand_hours": [10.0, 10.0]}
        )

        result = derive_measures(
            dataframe,
            ["allocation_hours", "demand_hours"],
        )

        self.assertEqual(result["deficit_hours"].tolist(), [2.0, 0.0])
        self.assertEqual(result["coverage_percent"].tolist(), [80.0, 100.0])

    def test_zero_demand_yields_missing_coverage(self):
        dataframe = pd.DataFrame(
            {"allocation_hours": [5.0], "demand_hours": [0.0]}
        )

        result = derive_measures(
            dataframe,
            ["allocation_hours", "demand_hours"],
        )

        self.assertTrue(pd.isna(result.loc[0, "coverage_percent"]))
        self.assertEqual(result.loc[0, "deficit_hours"], -5.0)

    def test_derived_measures_require_both_inputs(self):
        dataframe = pd.DataFrame({"allocation_hours": [5.0]})

        result = derive_measures(
            dataframe,
            ["allocation_hours"],
        )

        self.assertNotIn("deficit_hours", result.columns)
        self.assertNotIn("coverage_percent", result.columns)

    def test_composed_measures_are_not_derived_in_series_mode(self):
        dataframe = pd.DataFrame(
            {"allocation_hours": [5.0], "demand_hours": [10.0]}
        )
        plan = AnalysisPlan(
            components=[
                AnalysisComponent(
                    id="a",
                    measures=["allocation_hours", "demand_hours"],
                ),
            ],
            composition=CompositionSpec(mode=CompositionMode.SERIES),
        )

        result = derive_composed_measures(dataframe, plan)

        self.assertNotIn("deficit_hours", result.columns)

    def test_validate_result_ignores_derived_measures_when_checking_columns(self):
        component = AnalysisComponent(
            id="a",
            measures=["allocation_hours", "deficit_hours"],
        )

        validate_result(
            pd.DataFrame({"allocation_hours": [1.0]}),
            component,
        )

    def test_validate_result_reports_missing_base_measure(self):
        component = AnalysisComponent(
            id="a",
            measures=["allocation_hours", "demand_hours"],
        )

        with self.assertRaisesRegex(ValueError, "demand_hours"):
            validate_result(
                pd.DataFrame({"allocation_hours": [1.0]}),
                component,
            )

    def test_measure_columns_are_renamed_case_insensitively(self):
        dataframe = pd.DataFrame({"ALLOCATION_HOURS": [1.0]})

        result = normalize_measure_columns(
            dataframe,
            ["allocation_hours"],
        )

        self.assertEqual(list(result.columns), ["allocation_hours"])


class RequiredTablesAndValidationTests(unittest.TestCase):
    def setUp(self):
        self.metric = build_metric()

    def test_allocation_hours_requires_distribution_table(self):
        component = AnalysisComponent(id="a", measures=["allocation_hours"])

        tables = generic_required_tables(component)

        self.assertIn("distribuicao", tables)

    def test_demand_without_dimension_uses_both_restriction_tables(self):
        component = AnalysisComponent(id="a", measures=["demand_hours"])

        tables = generic_required_tables(component)

        self.assertIn("distribuicao", tables)
        self.assertIn("restr_emp", tables)
        self.assertIn("restr_fil", tables)

    def test_demand_by_branch_uses_only_branch_restriction_table(self):
        component = AnalysisComponent(
            id="a",
            measures=["demand_hours"],
            dimensions=["branch"],
        )

        tables = generic_required_tables(component)

        self.assertIn("restr_fil", tables)
        self.assertNotIn("restr_emp", tables)

    def test_company_filter_requires_company_table(self):
        component = AnalysisComponent(
            id="a",
            filters={"company_name": "Acme"},
        )

        tables = generic_required_tables(component)

        self.assertIn("empresa", tables)

    def test_selected_tables_rejects_unauthorized_table(self):
        component = AnalysisComponent(
            id="a",
            tables=["tabela_secreta"],
            measures=["allocation_hours"],
        )

        with self.assertRaisesRegex(ValueError, "não autorizadas"):
            resolve_tables(component, self.metric)

    def test_component_without_tables_or_sources_is_rejected(self):
        component = AnalysisComponent(id="a")

        with self.assertRaisesRegex(ValueError, "não informa tabelas"):
            resolve_tables(component, self.metric)

    def test_plan_validation_rejects_unknown_dimension(self):
        component = AnalysisComponent(id="a", dimensions=["planeta"])

        with self.assertRaisesRegex(ValueError, "Dimensões não autorizadas"):
            validate_plan(component, self.metric)

    def test_plan_validation_accepts_only_generic_metric(self):
        other_metric = self.metric.model_copy(
            update={"key": "allocation_vs_demand"},
        )

        with self.assertRaisesRegex(ValueError, "generic_analysis"):
            validate_plan(
                AnalysisComponent(id="a"),
                other_metric,
            )


class SqlSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.metric = build_metric()

    def test_allocation_accepts_sum_of_all_hour_columns(self):
        sql = f"SELECT SUM({ALL_HOURS}) AS allocation_hours FROM distribuicao"

        validate_sql_semantics(
            sql,
            self.metric,
            ["allocation_hours"],
        )

    def test_allocation_rejects_partial_hour_sum(self):
        sql = "SELECT SUM(hor_00) AS allocation_hours FROM distribuicao"

        with self.assertRaisesRegex(ValueError, "hor_00 até hor_23"):
            validate_sql_semantics(
                sql,
                self.metric,
                ["allocation_hours"],
            )

    def test_demand_accepts_raw_schedule_with_date(self):
        sql = (
            "SELECT restricao AS demand_schedule, analysis_date "
            "FROM restr_fil"
        )

        validate_sql_semantics(
            sql,
            self.metric,
            ["demand_hours"],
        )

    def test_demand_requires_schedule_date_and_restriction_table(self):
        with self.assertRaisesRegex(ValueError, "Elementos ausentes"):
            validate_sql_semantics(
                "SELECT 1 AS demand_hours",
                self.metric,
                ["demand_hours"],
            )

    def test_demand_rejects_counting_restriction_ids(self):
        sql = (
            "SELECT COUNT(DISTINCT restr_id) AS demand_hours, "
            "restricao AS demand_schedule, analysis_date FROM restr_fil"
        )

        with self.assertRaisesRegex(ValueError, "Não conte restr_id"):
            validate_sql_semantics(
                sql,
                self.metric,
                ["demand_hours"],
            )

    def test_demand_rejects_aggregating_raw_restriction(self):
        sql = (
            "SELECT SUM(restricao) AS demand_schedule, analysis_date "
            "FROM restr_fil"
        )

        with self.assertRaisesRegex(ValueError, "Não agregue restricao"):
            validate_sql_semantics(
                sql,
                self.metric,
                ["demand_hours"],
            )


class DataNormalizationTests(unittest.TestCase):
    def test_weekly_demand_uses_requested_date_dimension(self):
        weekdays = [
            "segunda",
            "terca",
            "quarta",
            "quinta",
            "sexta",
            "sabado",
            "domingo",
        ]
        metric = MetricDefinition(
            key="generic_analysis",
            label="Análise genérica",
            description="Teste de normalização.",
            business_rule="Teste.",
            measures={
                "demand_hours": MeasureDefinition(
                    column="restricao",
                    parser=DataParser.WEEKLY_24H_JSON,
                    json_path=["demanda"],
                    hours_per_day=24,
                    required_days=weekdays,
                    raw_alias="demand_schedule",
                    date_alias="analysis_date",
                ),
            },
        )
        schedule = json.dumps(
            {
                "demanda": {
                    weekday: [1] * 24
                    for weekday in weekdays
                }
            }
        )
        dataframe = pd.DataFrame(
            {
                "date": ["2026-10-12"],
                "month": ["2026-10"],
                "demand_schedule": [schedule],
            }
        )

        result = DataNormalizer().normalize(
            dataframe,
            metric,
            ["demand_hours"],
            ["date", "month"],
        )

        self.assertEqual(result.dataframe.loc[0, "demand_hours"], 24)
        self.assertEqual(result.dataframe.loc[0, "date"], "2026-10-12")


class ParameterConversionTests(unittest.TestCase):
    def setUp(self):
        self.binder = ParameterBinder(Mock())

    def test_date_parameter_accepts_brazilian_and_iso_formats(self):
        for value in ("17/09/2026", "2026-09-17"):
            with self.subTest(value=value):
                result = self.binder.convert_parameter_value(
                    value,
                    SemanticValueType.DATE,
                    "filter_period_start",
                )

                self.assertEqual(result, date(2026, 9, 17))

    def test_invalid_date_parameter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "não contém uma data válida"):
            self.binder.convert_parameter_value(
                "31/02/2026",
                SemanticValueType.DATE,
                "filter_period_start",
            )

    def test_boolean_parameter_accepts_portuguese_words(self):
        true_value = self.binder.convert_parameter_value(
            "sim",
            SemanticValueType.BOOLEAN,
            "filter_active",
        )
        false_value = self.binder.convert_parameter_value(
            "não",
            SemanticValueType.BOOLEAN,
            "filter_active",
        )

        self.assertIs(true_value, True)
        self.assertIs(false_value, False)

    def test_number_parameter_is_converted_to_float(self):
        result = self.binder.convert_parameter_value(
            "10",
            SemanticValueType.NUMBER,
            "filter_limit",
        )

        self.assertEqual(result, 10.0)

    def test_parameter_type_ignores_hints_inside_other_words(self):
        self.assertIsNone(self.binder.infer_parameter_type("filter_legend"))
        self.assertIsNone(self.binder.infer_parameter_type("filter_candidate"))
        self.assertEqual(
            self.binder.infer_parameter_type("filter_end_date"),
            SemanticValueType.DATE,
        )

    def test_parameter_type_is_inferred_from_name(self):
        self.assertEqual(
            self.binder.infer_parameter_type("filter_period_start"),
            SemanticValueType.DATE,
        )
        self.assertIsNone(
            self.binder.infer_parameter_type("filter_company_name"),
        )


class DefaultChartSpecTests(unittest.TestCase):
    def setUp(self):
        self.service = build_service()

    def test_series_mode_uses_analysis_series_as_color_and_temporal_x(self):
        plan = AnalysisPlan(
            components=[
                AnalysisComponent(
                    id="a",
                    label="Posto A",
                    dimensions=["month"],
                    measures=["allocation_hours"],
                ),
                AnalysisComponent(
                    id="b",
                    label="Posto B",
                    dimensions=["month"],
                    measures=["allocation_hours"],
                ),
            ],
            composition=CompositionSpec(mode=CompositionMode.SERIES),
        )
        dataframe = pd.DataFrame(
            {
                "month": ["2026-01", "2026-01"],
                "allocation_hours": [1.0, 2.0],
                "analysis_series": ["Posto A", "Posto B"],
            }
        )

        spec = default_chart_spec(
            dataframe,
            plan,
            ChartType.AUTO,
        )

        self.assertEqual(spec.x, "month")
        self.assertEqual(spec.color, "analysis_series")
        self.assertEqual([item.column for item in spec.series], ["allocation_hours"])

    def test_allocation_and_demand_default_to_bar_and_line(self):
        plan = AnalysisPlan(
            components=[
                AnalysisComponent(
                    id="a",
                    dimensions=["month"],
                    measures=["allocation_hours", "demand_hours"],
                ),
            ],
        )
        dataframe = pd.DataFrame(
            {
                "month": ["2026-01"],
                "allocation_hours": [1.0],
                "demand_hours": [2.0],
            }
        )

        spec = default_chart_spec(
            dataframe,
            plan,
            ChartType.AUTO,
        )

        types = {item.column: item.chart_type for item in spec.series}
        self.assertEqual(
            types,
            {
                "allocation_hours": ChartType.BAR,
                "demand_hours": ChartType.LINE,
            },
        )

    def test_aligned_color_never_repeats_the_temporal_x_dimension(self):
        plan = AnalysisPlan(
            components=[
                AnalysisComponent(
                    id="a",
                    dimensions=["branch", "month"],
                    measures=["allocation_hours"],
                ),
            ],
            composition=CompositionSpec(
                mode=CompositionMode.ALIGNED,
                keys=["branch", "month"],
            ),
        )
        dataframe = pd.DataFrame(
            {
                "branch": ["F1"],
                "month": ["2026-01"],
                "allocation_hours": [1.0],
            }
        )

        spec = default_chart_spec(dataframe, plan, ChartType.AUTO)

        self.assertEqual(spec.x, "month")
        self.assertEqual(spec.color, "branch")

    def test_explicit_chart_type_overrides_series_types(self):
        spec = ChartSpec(
            chart_type=ChartType.AUTO,
            series=[ChartSeries(column="allocation_hours")],
        )

        overridden = override_chart_type(spec, ChartType.LINE)

        self.assertEqual(overridden.chart_type, ChartType.LINE)
        self.assertEqual(overridden.series[0].chart_type, ChartType.LINE)

    def test_auto_chart_type_keeps_spec_unchanged(self):
        spec = ChartSpec(
            chart_type=ChartType.AUTO,
            series=[ChartSeries(column="allocation_hours")],
        )

        self.assertIs(
            override_chart_type(spec, ChartType.AUTO),
            spec,
        )

    def test_chart_x_dimension_prefers_temporal_dimension(self):
        self.assertEqual(
            chart_x_dimension(["branch", "month"]),
            "month",
        )
        self.assertEqual(
            chart_x_dimension(["branch", "workplace"]),
            "branch",
        )
        self.assertIsNone(chart_x_dimension([]))

    def test_export_formats_combine_request_and_plan_without_duplicates(self):
        request = AnalysisRequest(
            question="Gere um relatório",
            export_formats=[ExportFormat.CSV],
        )
        plan = AnalysisPlan(
            requested_exports=[ExportFormat.CSV, ExportFormat.XLSX],
        )

        self.assertEqual(
            self.service._export_formats(request, plan),
            [ExportFormat.CSV, ExportFormat.XLSX],
        )


class AnalysisAuditTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.audit_path = Path(directory.name) / "auditoria.txt"
        self.service = build_service(audit_log_path=self.audit_path)
        self.request = AnalysisRequest(question="Qual a alocação em 2026?")

    def read_events(self) -> list[list[str]]:
        lines = self.audit_path.read_text(encoding="utf-8").splitlines()
        return [line.split(" | ", 3) for line in lines]

    def test_failed_analysis_is_audited_under_the_same_id_and_reraised(self):
        self.service.planner = Mock()
        self.service.planner.create_plan.side_effect = ValueError(
            "Pergunta fora do escopo"
        )

        with self.assertRaisesRegex(ValueError, "Pergunta fora do escopo"):
            self.service.analyze(self.request)

        events = self.read_events()
        self.assertEqual(
            [event[2] for event in events],
            ["analysis.started", "analysis.failed"],
        )
        self.assertEqual(events[0][1], events[1][1])
        started = json.loads(events[0][3])
        self.assertEqual(started["request"]["question"], self.request.question)
        failed = json.loads(events[1][3])
        self.assertEqual(failed["error_type"], "ValueError")
        self.assertEqual(failed["error"], "Pergunta fora do escopo")
        self.assertIn("Traceback (most recent call last)", failed["traceback"])

    def test_successful_analysis_records_each_step_under_the_report_id(self):
        plan = AnalysisPlan(
            components=[
                AnalysisComponent(
                    id="component_1",
                    tables=["funcionario"],
                    dimensions=["month"],
                ),
            ],
        )
        session = MagicMock()
        session.execute_read.return_value = pd.DataFrame(
            {"month": ["2026-01"], "allocation_hours": [10.0]}
        )
        repository = MagicMock()
        repository.open_session.return_value.__enter__.return_value = session
        self.service.analytics_repository = repository
        self.service.planner = Mock()
        self.service.planner.create_plan.return_value = plan
        self.service.catalog.get.return_value = build_metric()
        self.service.sql_generator = Mock()
        self.service.sql_generator.validated_plan.return_value = (
            "SELECT 1",
            SqlPlan(sql="SELECT 1"),
        )
        self.service.chart_builder = Mock()
        self.service.chart_builder.build.return_value = None
        self.service.answers = Mock()
        self.service.answers.create_answer.return_value = "Resposta de teste"
        self.service.exporter.export.return_value = []

        with patch(
            "relatorios_service.services.analysis_service.build_schema_context",
            return_value="schema",
        ):
            result = self.service.analyze(self.request)

        events = self.read_events()
        self.assertEqual(
            [event[2] for event in events],
            [
                "analysis.started",
                "plan.created",
                "query.executed",
                "analysis.composed",
                "answer.created",
                "analysis.completed",
            ],
        )
        self.assertEqual({event[1] for event in events}, {result.report_id})
        executed = json.loads(events[2][3])
        self.assertEqual(executed["component"], "component_1")
        self.assertEqual(executed["rows"], 1)
        completed = json.loads(events[5][3])
        self.assertEqual(completed["row_count"], 1)
        self.assertFalse(completed["truncated"])


if __name__ == "__main__":
    unittest.main()

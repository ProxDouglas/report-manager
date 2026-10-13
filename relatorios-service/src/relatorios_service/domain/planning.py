from ..schemas import (
    AnalysisComponent,
    AnalysisPlan,
    AnalysisRequest,
    CompositionMode,
)

from .period import normalize_period_intent


def normalize_plan(
    plan: AnalysisPlan,
    request: AnalysisRequest | None = None,
) -> AnalysisPlan:
    if not plan.components:
        raise ValueError("O plano não contém componentes de análise.")

    components = list(plan.components)
    normalized_components = []
    component_ids: set[str] = set()

    for position, component in enumerate(components, start=1):
        component_id = component.id.strip()

        if not component_id:
            component_id = f"component_{position}"

        if component_id in component_ids:
            raise ValueError(
                f"O id de componente está duplicado: {component_id}."
            )

        component_ids.add(component_id)

        normalized_component = component.model_copy(
            update={"id": component_id}
        )

        if request is not None:
            normalized_component = normalize_period_intent(
                normalized_component,
                request.question,
            )

        normalized_components.append(normalized_component)

    composition = plan.composition

    if (
        len(normalized_components) > 1
        and composition.mode is CompositionMode.ALIGNED
        and not composition.keys
    ):
        composition = composition.model_copy(
            update={"mode": CompositionMode.SERIES}
        )

    normalized_plan = plan.model_copy(
        update={
            "components": normalized_components,
            "composition": composition,
        }
    )

    return normalize_chart_components(normalized_plan)


def normalize_chart_components(
    plan: AnalysisPlan,
) -> AnalysisPlan:
    if plan.chart is None or not plan.chart.series:
        return plan

    component_ids = {
        component.id
        for component in plan.components
    }
    series = []

    for item in plan.chart.series:
        if item.component_id:
            if item.component_id not in component_ids:
                raise ValueError(
                    "O gráfico referencia um component_id inexistente: "
                    f"{item.component_id}."
                )

            series.append(item)
            continue

        component_id = component_id_by_label(
            item.label,
            plan.components,
        )

        if component_id:
            item = item.model_copy(
                update={"component_id": component_id}
            )

        series.append(item)

    chart = plan.chart.model_copy(update={"series": series})
    return plan.model_copy(update={"chart": chart})


def component_id_by_label(
    label: str | None,
    components: list[AnalysisComponent],
) -> str | None:
    if not label:
        return None

    normalized_label = label.strip().casefold()
    matches = [
        component.id
        for component in components
        if normalized_label in {
            component.id.strip().casefold(),
            (component.label or "").strip().casefold(),
        }
    ]

    if len(matches) == 1:
        return matches[0]

    return None


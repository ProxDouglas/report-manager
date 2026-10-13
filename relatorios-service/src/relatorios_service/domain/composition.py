from dataclasses import dataclass
from typing import Any

import pandas as pd

from ..schemas import (
    AnalysisComponent,
    AnalysisPlan,
    CompositionMode,
)

from .measures import DERIVED_MEASURES

COMPONENT_COLUMN = "analysis_component"
SERIES_COLUMN = "analysis_series"



@dataclass
class ComponentExecution:
    component: AnalysisComponent
    dataframe: pd.DataFrame
    sql: str
    warnings: list[dict[str, Any]]


def compose_components(
    executions: list[ComponentExecution],
    plan: AnalysisPlan,
) -> pd.DataFrame:
    if not executions:
        return pd.DataFrame()

    if len(executions) == 1:
        return executions[0].dataframe

    if plan.composition.mode is CompositionMode.SERIES:
        return stack_components(executions)

    return align_components(executions, plan.composition.keys)


def stack_components(
    executions: list[ComponentExecution],
) -> pd.DataFrame:
    frames = []

    for execution in executions:
        frame = execution.dataframe.copy()
        frame[COMPONENT_COLUMN] = execution.component.id
        frame[SERIES_COLUMN] = (
            execution.component.label or execution.component.id
        )
        frames.append(frame)

    return pd.concat(frames, ignore_index=True, sort=False)


def align_components(
    executions: list[ComponentExecution],
    keys: list[str],
) -> pd.DataFrame:
    if not keys:
        raise ValueError(
            "A composição alinhada exige pelo menos uma chave em "
            "composition.keys."
        )

    frames = []

    for execution in executions:
        missing_keys = [
            key
            for key in keys
            if key not in execution.dataframe.columns
        ]

        if missing_keys:
            names = ", ".join(missing_keys)
            raise ValueError(
                f"O componente {execution.component.id} não retornou "
                f"as chaves de composição: {names}."
            )

        measure_columns = component_measure_columns(
            execution.component,
            execution.dataframe,
        )
        columns = list(dict.fromkeys([*keys, *measure_columns]))
        frame = execution.dataframe[columns].copy()

        if frame.duplicated(keys).any():
            raise ValueError(
                f"O componente {execution.component.id} possui mais de "
                "uma linha para a mesma chave de composição."
            )

        frames.append(frame)

    result = frames[0]

    for frame in frames[1:]:
        overlapping_columns = (
            set(result.columns) & set(frame.columns)
        ) - set(keys)

        if overlapping_columns:
            names = ", ".join(sorted(overlapping_columns))
            raise ValueError(
                "Componentes alinhados não podem sobrescrever medidas: "
                f"{names}."
            )

        result = result.merge(
            frame,
            on=keys,
            how="outer",
            validate="one_to_one",
        )

    return result


def component_measure_columns(
    component: AnalysisComponent,
    dataframe: pd.DataFrame,
) -> list[str]:
    configured = [*component.measures, *DERIVED_MEASURES]
    selected = [
        column
        for column in configured
        if column in dataframe.columns
    ]

    if selected:
        return list(dict.fromkeys(selected))

    return list(dataframe.select_dtypes(include="number").columns)


def component_warnings(
    executions: list[ComponentExecution],
) -> list[dict[str, Any]]:
    warnings = []

    for execution in executions:
        for warning in execution.warnings:
            warnings.append(
                {
                    **warning,
                    "component": execution.component.id,
                }
            )

    return warnings


import re
import unicodedata
from datetime import date
from typing import Any

from ..schemas import (
    AnalysisComponent,
    PeriodGranularity,
    PeriodSpec,
)

_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}
_MONTH_NAME_PATTERN = re.compile(
    rf"\b(?:{'|'.join(_MONTHS)})\b"
)


def normalize_period_intent(
    component: AnalysisComponent,
    question: str,
) -> AnalysisComponent:
    year = question_year(question)
    mentions_month = question_mentions_month(question)
    month_number = question_month_number(question)

    if year is None and not mentions_month:
        return component

    dimensions = list(component.dimensions)
    if mentions_month and "month" not in dimensions:
        dimensions.append("month")

    period = component.period
    if year is None:
        return component.model_copy(update={"dimensions": dimensions})

    if month_number is not None:
        month_start = date(year, month_number, 1)
        month_end = (
            date(year + 1, 1, 1)
            if month_number == 12
            else date(year, month_number + 1, 1)
        )
        if period is None:
            period = PeriodSpec(
                granularity=PeriodGranularity.MONTH,
                start=month_start,
                end=month_end,
            )
        else:
            period = period.model_copy(
                update={
                    "granularity": PeriodGranularity.MONTH,
                    "start": month_start,
                    "end": month_end,
                }
            )
    elif period is None:
        period = PeriodSpec(
            granularity=(
                PeriodGranularity.MONTH
                if mentions_month
                else PeriodGranularity.YEAR
            ),
            start=date(year, 1, 1),
            end=date(year + 1, 1, 1),
        )
    else:
        period_updates: dict[str, Any] = {}

        if period.start is None:
            period_updates["start"] = date(year, 1, 1)

        if period.end is None:
            period_updates["end"] = date(year + 1, 1, 1)

        if (
            period.start == date(year, 1, 1)
            and period.end == date(year, 12, 31)
        ):
            period_updates["end"] = date(year + 1, 1, 1)

        if period.granularity is None:
            period_updates["granularity"] = (
                PeriodGranularity.MONTH
                if mentions_month
                else PeriodGranularity.YEAR
            )

        if period_updates:
            period = period.model_copy(update=period_updates)

    return component.model_copy(
        update={
            "dimensions": dimensions,
            "period": period,
        }
    )


def question_year(question: str) -> int | None:
    years = {
        int(value)
        for value in re.findall(r"\b(19\d{2}|20\d{2})\b", question)
    }

    if len(years) != 1:
        return None

    return next(iter(years))


def question_mentions_month(question: str) -> bool:
    normalized = _normalize_question(question)
    return bool(
        re.search(r"\bmes(?:es)?\b", normalized)
        or re.search(r"\bmensal", normalized)
        or _MONTH_NAME_PATTERN.search(normalized)
    )


def question_month_number(question: str) -> int | None:
    normalized = _normalize_question(question)
    month_numbers = {
        int(value)
        for value in re.findall(r"\bmes\s+(0?[1-9]|1[0-2])\b", normalized)
    }
    month_numbers.update(
        _MONTHS[month]
        for month in _MONTH_NAME_PATTERN.findall(normalized)
    )

    if len(month_numbers) != 1:
        return None

    return next(iter(month_numbers))


def _normalize_question(question: str) -> str:
    normalized = unicodedata.normalize("NFKD", question.casefold())
    return normalized.encode("ascii", "ignore").decode("ascii")


def period_values(period: PeriodSpec) -> list[Any]:
    values: list[Any] = []

    if period.start:
        values.append(period.start)

    if period.end:
        values.append(period.end)

    for comparison in period.comparisons:
        values.extend([comparison.start, comparison.end])

    return values

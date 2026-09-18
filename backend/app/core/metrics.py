from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from threading import Lock

_lock = Lock()
_counters: defaultdict[tuple[str, tuple[tuple[str, str], ...]], float] = defaultdict(float)
_gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
_histograms: defaultdict[tuple[str, tuple[tuple[str, str], ...]], list[float]] = defaultdict(
    list
)
_uuid_path = re.compile(r"/[0-9a-f]{8}-[0-9a-f-]{27,}/?", re.IGNORECASE)


def normalize_path(path: str) -> str:
    return _uuid_path.sub("/{id}/", path).rstrip("/") or "/"


def _key(labels: Mapping[str, object] | None) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((name, str(value)) for name, value in (labels or {}).items()))


def increment(name: str, value: float = 1, labels: Mapping[str, object] | None = None) -> None:
    with _lock:
        _counters[(name, _key(labels))] += value


def set_gauge(name: str, value: float, labels: Mapping[str, object] | None = None) -> None:
    with _lock:
        _gauges[(name, _key(labels))] = value


def observe(name: str, value: float, labels: Mapping[str, object] | None = None) -> None:
    with _lock:
        _histograms[(name, _key(labels))].append(value)


def _labels_text(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    escaped = []
    for name, value in labels:
        safe_value = value.replace("\\", "\\\\").replace('"', '\\"')
        escaped.append(f'{name}="{safe_value}"')
    return "{" + ",".join(escaped) + "}"


def render_prometheus() -> str:
    lines: list[str] = []
    with _lock:
        for (name, labels), value in sorted(_counters.items()):
            lines.append(f"{name}{_labels_text(labels)} {value}")
        for (name, labels), value in sorted(_gauges.items()):
            lines.append(f"{name}{_labels_text(labels)} {value}")
        for (name, labels), values in sorted(_histograms.items()):
            if not values:
                continue
            lines.append(f"{name}_count{_labels_text(labels)} {len(values)}")
            lines.append(f"{name}_sum{_labels_text(labels)} {sum(values)}")
    return "\n".join(lines) + "\n"

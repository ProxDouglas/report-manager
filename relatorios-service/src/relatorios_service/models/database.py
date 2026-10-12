from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DatabaseTableSchema:
    columns: dict[str, str]
    sample_rows: list[dict[str, Any]]
    primary_key: list[str]
    foreign_keys: list[dict[str, Any]]

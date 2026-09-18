from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.db.enums import DataClassification, SensitivityAction

SECRET_NAME_PATTERN = re.compile(
    r"(?:senha|password|passwd|token|secret|api[_-]?key|authorization|private[_-]?key|connection[_-]?string)",
    re.IGNORECASE,
)
PERSONAL_NAME_PATTERN = re.compile(
    r"(?:cpf|cnpj|documento|telefone|phone|email|endereco|address)", re.IGNORECASE
)
CPF_PATTERN = re.compile(r"(?<!\d)\d{3}\.?\d{3}\.?\d{3}-?(\d{2})(?!\d)")
CNPJ_PATTERN = re.compile(r"(?<!\d)\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?(\d{2})(?!\d)")


@dataclass(frozen=True)
class ClassificationDecision:
    classification: DataClassification
    action: SensitivityAction
    confidence: str
    reason: str


def classify_field(field_name: str, data_type: str = "") -> ClassificationDecision:
    if SECRET_NAME_PATTERN.search(field_name):
        return ClassificationDecision(
            DataClassification.SECRET, SensitivityAction.BLOCK, "ALTA", "nome_secreto"
        )
    if PERSONAL_NAME_PATTERN.search(field_name):
        return ClassificationDecision(
            DataClassification.SENSITIVE, SensitivityAction.MASK, "MEDIA", "nome_pessoal"
        )
    if data_type.lower() in {"password", "secret", "credential"}:
        return ClassificationDecision(
            DataClassification.SECRET, SensitivityAction.BLOCK, "ALTA", "tipo_secreto"
        )
    return ClassificationDecision(
        DataClassification.INTERNAL, SensitivityAction.ALLOW, "BAIXA", "padrao_interno"
    )


def mask_sensitive_text(value: str) -> str:
    masked = CPF_PATTERN.sub(lambda match: f"***.***.***-{match.group(1)}", value)
    masked = CNPJ_PATTERN.sub(lambda match: f"**.***.***/****-{match.group(1)}", masked)
    return masked


def scrub_value(value: Any, field_name: str = "") -> Any:
    decision = classify_field(field_name)
    if decision.action is SensitivityAction.BLOCK:
        return "[REDACTED]"
    if isinstance(value, str):
        return mask_sensitive_text(value)
    if isinstance(value, dict):
        return {key: scrub_value(item, str(key)) for key, item in value.items()}
    if isinstance(value, list):
        return [scrub_value(item, field_name) for item in value]
    return value


def scrub_mapping(mapping: dict[str, Any]) -> dict[str, Any]:
    return {key: scrub_value(value, key) for key, value in mapping.items()}


def assert_no_secrets(value: Any) -> None:
    scrubbed = scrub_value(value)
    if isinstance(scrubbed, str) and scrubbed == "[REDACTED]":
        raise ValueError("O conteúdo contém campo secreto bloqueado.")

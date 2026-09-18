from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DomainError, NotFoundError
from app.core.secrets import get_secret_manager
from app.core.sensitive import scrub_mapping
from app.db.enums import AuditResult, LlmProvider
from app.db.models import LlmConfiguration, LlmInvocation, LlmPreset
from app.schemas.llm import LlmConfigurationRequest, PresetCreateRequest
from app.services.audit import record_audit


class LlmProviderAdapter(Protocol):
    def validate(
        self, configuration: LlmConfiguration, preset: LlmPreset, secret: str
    ) -> dict[str, Any]: ...

    def generate(
        self, configuration: LlmConfiguration, preset: LlmPreset, secret: str, prompt: str
    ) -> str: ...


@dataclass(frozen=True)
class HttpProviderAdapter:
    provider: LlmProvider
    base_url: str

    def _request(
        self, method: str, path: str, secret: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
        if self.provider is LlmProvider.ANTHROPIC:
            headers = {
                "x-api-key": secret,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        try:
            response = httpx.request(
                method,
                f"{self.base_url.rstrip('/')}/{path.lstrip('/')}",
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise DomainError(
                "O provedor de IA excedeu o tempo de resposta.", "llm_timeout", 504
            ) from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401 or status == 403:
                raise DomainError(
                    "A API key do provedor de IA foi rejeitada.",
                    "llm_authentication_failed",
                    502,
                ) from exc
            if status == 429:
                raise DomainError(
                    "O provedor de IA limitou as requisições.", "llm_rate_limited", 429
                ) from exc
            if status >= 500:
                raise DomainError(
                    "O provedor de IA está indisponível.", "llm_provider_unavailable", 503
                ) from exc
            raise DomainError(
                "O provedor de IA rejeitou a solicitação.", "llm_provider_failed", 502
            ) from exc
        except httpx.RequestError as exc:
            raise DomainError(
                "Não foi possível alcançar o provedor de IA.",
                "llm_provider_unavailable",
                503,
            ) from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise DomainError(
                "O provedor de IA retornou JSON inválido.", "llm_invalid_response", 502
            ) from exc
        if not isinstance(data, dict):
            raise DomainError(
                "O provedor de IA retornou resposta inválida.", "llm_invalid_response", 502
            )
        return data

    def validate(
        self, configuration: LlmConfiguration, preset: LlmPreset, secret: str
    ) -> dict[str, Any]:
        if self.provider is LlmProvider.GEMINI:
            data = self._request(
                "GET", f"v1beta/models/{preset.model_identifier}?key={secret}", secret, None
            )
            return {
                "validated": True,
                "provider": self.provider,
                "model": data.get("name", preset.model_identifier),
            }
        path = "v1/messages" if self.provider is LlmProvider.ANTHROPIC else "v1/chat/completions"
        payload = self._payload(preset, "Responda apenas com OK.")
        data = self._request("POST", path, secret, payload)
        return {
            "validated": True,
            "provider": self.provider,
            "model": data.get("model", preset.model_identifier),
        }

    def _payload(self, preset: LlmPreset, prompt: str) -> dict[str, Any]:
        return self._payload_for_configuration(None, preset, prompt)

    def _payload_for_configuration(
        self,
        configuration: LlmConfiguration | None,
        preset: LlmPreset,
        prompt: str,
    ) -> dict[str, Any]:
        max_tokens = (
            configuration.max_tokens
            if configuration and configuration.max_tokens
            else preset.max_tokens or 1024
        )
        if self.provider is LlmProvider.ANTHROPIC:
            payload: dict[str, Any] = {
                "model": preset.model_identifier,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if configuration and configuration.temperature is not None:
                payload["temperature"] = configuration.temperature
            return payload
        payload = {
            "model": preset.model_identifier,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        if configuration and configuration.temperature is not None:
            payload["temperature"] = configuration.temperature
        if (
            configuration
            and configuration.reasoning_level
            and self.provider is LlmProvider.OPENAI
            and "reasoning_effort" in preset.capabilities
        ):
            payload["reasoning_effort"] = configuration.reasoning_level
        return payload

    def generate(
        self, configuration: LlmConfiguration, preset: LlmPreset, secret: str, prompt: str
    ) -> str:
        if self.provider is LlmProvider.COPILOT:
            raise DomainError(
                "O contrato de API do Copilot ainda não foi configurado.",
                "llm_provider_unavailable",
                501,
            )
        if self.provider is LlmProvider.GEMINI:
            path = f"v1beta/models/{preset.model_identifier}:generateContent?key={secret}"
            data = self._request(
                "POST", path, secret, {"contents": [{"parts": [{"text": prompt}]}]}
            )
            text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get(
                "text", ""
            )
            return self._require_text(text)
        path = "v1/messages" if self.provider is LlmProvider.ANTHROPIC else "v1/chat/completions"
        data = self._request(
            "POST", path, secret, self._payload_for_configuration(configuration, preset, prompt)
        )
        if self.provider is LlmProvider.ANTHROPIC:
            return self._require_text(data.get("content", [{}])[0].get("text", ""))
        return self._require_text(
            data.get("choices", [{}])[0].get("message", {}).get("content", "")
        )

    @staticmethod
    def _require_text(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise DomainError(
                "O provedor de IA retornou conteúdo vazio ou inválido.",
                "llm_invalid_response",
                502,
            )
        return value


def adapter_for(provider: LlmProvider) -> LlmProviderAdapter:
    if provider is LlmProvider.OPENAI:
        return HttpProviderAdapter(provider, "https://api.openai.com")
    if provider is LlmProvider.ANTHROPIC:
        return HttpProviderAdapter(provider, "https://api.anthropic.com")
    if provider is LlmProvider.DEEPSEEK:
        return HttpProviderAdapter(provider, "https://api.deepseek.com")
    if provider is LlmProvider.GEMINI:
        return HttpProviderAdapter(provider, "https://generativelanguage.googleapis.com")
    return HttpProviderAdapter(provider, "https://api.githubcopilot.com")


def create_preset(db: Session, payload: PresetCreateRequest) -> LlmPreset:
    preset = LlmPreset(
        provider=payload.provider,
        model_identifier=payload.model_identifier,
        name=payload.name,
        capabilities=payload.capabilities,
        reasoning_levels=payload.reasoning_levels,
        max_tokens=payload.max_tokens,
    )
    db.add(preset)
    db.commit()
    db.refresh(preset)
    return preset


def create_configuration(
    db: Session,
    settings: Settings,
    organization_id: UUID,
    user_id: UUID,
    payload: LlmConfigurationRequest,
) -> LlmConfiguration:
    preset = db.get(LlmPreset, payload.preset_id)
    if not preset or not preset.is_active:
        raise NotFoundError("Preset de modelo ativo não encontrado.")
    if payload.reasoning_level and payload.reasoning_level not in preset.reasoning_levels:
        raise DomainError(
            "Nível de reasoning incompatível com o preset.", "invalid_llm_configuration"
        )
    configuration = LlmConfiguration(
        organization_id=organization_id,
        preset_id=preset.id,
        name=payload.name,
        secret_ref=payload.secret_ref,
        reasoning_level=payload.reasoning_level,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        capability_snapshot={
            "provider": preset.provider,
            "model": preset.model_identifier,
            "capabilities": preset.capabilities,
            "reasoning_levels": preset.reasoning_levels,
        },
    )
    db.add(configuration)
    record_audit(
        db,
        action="create_llm_configuration",
        result=AuditResult.SUCCESS,
        organization_id=organization_id,
        actor_user_id=user_id,
        resource_type="llm_configuration",
    )
    db.commit()
    db.refresh(configuration)
    return configuration


def test_configuration(
    db: Session, settings: Settings, configuration_id: UUID, organization_id: UUID, user_id: UUID
) -> dict[str, Any]:
    configuration = db.scalar(
        select(LlmConfiguration).where(
            LlmConfiguration.id == configuration_id,
            LlmConfiguration.organization_id == organization_id,
        )
    )
    if not configuration:
        raise NotFoundError("Configuração de LLM não encontrada.")
    preset = db.get(LlmPreset, configuration.preset_id)
    if not preset or not preset.is_active:
        raise DomainError("Preset de modelo inativo.", "invalid_llm_configuration")
    secret_manager = get_secret_manager(settings)
    secret = secret_manager.get(configuration.secret_ref)
    result = adapter_for(preset.provider).validate(configuration, preset, secret)
    preset.last_validated_at = __import__("datetime").datetime.now(__import__("datetime").UTC)
    configuration.capability_snapshot = {**configuration.capability_snapshot, "last_test": result}
    record_audit(
        db,
        action="test_llm_configuration",
        result=AuditResult.SUCCESS,
        organization_id=organization_id,
        actor_user_id=user_id,
        resource_type="llm_configuration",
        resource_id=str(configuration.id),
    )
    db.commit()
    return {"success": True, "provider": preset.provider, "model": preset.model_identifier}


def generate_proposal(
    db: Session,
    settings: Settings,
    configuration_id: UUID,
    organization_id: UUID,
    user_id: UUID,
    objective: str,
    catalog_context: dict[str, Any],
) -> dict[str, Any]:
    configuration = db.scalar(
        select(LlmConfiguration).where(
            LlmConfiguration.id == configuration_id,
            LlmConfiguration.organization_id == organization_id,
            LlmConfiguration.is_active.is_(True),
        )
    )
    if not configuration:
        raise NotFoundError("Configuração de LLM ativa não encontrada.")
    preset = db.get(LlmPreset, configuration.preset_id)
    if not preset or not preset.is_active:
        raise DomainError("Preset de modelo inativo.", "invalid_llm_configuration")
    secret = get_secret_manager(settings).get(configuration.secret_ref)
    safe_catalog = scrub_mapping(catalog_context)
    prompt = json.dumps(
        {
            "objective": objective,
            "catalog": safe_catalog,
            "instructions": (
                "Retorne somente JSON com name, objective e definition. "
                "Nunca selecione campos secretos."
            ),
        },
        ensure_ascii=False,
    )
    result = adapter_for(preset.provider).generate(configuration, preset, secret, prompt)
    try:
        proposal = json.loads(result)
    except json.JSONDecodeError as exc:
        raise DomainError(
            "A IA retornou uma definição que não é JSON válido.", "llm_invalid_response", 502
        ) from exc
    if not isinstance(proposal, dict) or not isinstance(proposal.get("definition"), dict):
        raise DomainError(
            "A proposta da IA não possui o schema esperado.", "llm_invalid_response", 502
        )
    invocation = LlmInvocation(
        organization_id=organization_id,
        configuration_id=configuration.id,
        provider=preset.provider,
        model_identifier=preset.model_identifier,
        reasoning_level=configuration.reasoning_level,
        status="SUCESSO",
        usage_metadata={
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            "prompt_length": len(prompt),
            "response_length": len(result),
        },
    )
    db.add(invocation)
    record_audit(
        db,
        action="generate_report_proposal",
        result=AuditResult.SUCCESS,
        organization_id=organization_id,
        actor_user_id=user_id,
        resource_type="llm_invocation",
        details={"provider": preset.provider, "model": preset.model_identifier},
    )
    db.commit()
    return proposal

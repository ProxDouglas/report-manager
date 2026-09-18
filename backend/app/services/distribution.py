from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import smtplib
import socket
import time
from base64 import b64encode
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DomainError, NotFoundError
from app.core.metrics import increment
from app.core.secrets import get_secret_manager
from app.db.enums import AuditResult, DestinationStatus, DestinationType, ExecutionStatus
from app.db.models import Artifact, Destination, Execution, OutboxEvent
from app.schemas.destination import DestinationCreateRequest
from app.services.audit import record_audit


def create_destination(
    db: Session, organization_id: UUID, user_id: UUID, payload: DestinationCreateRequest
) -> Destination:
    if payload.destination_type is DestinationType.WEBHOOK:
        validate_webhook_url(str(payload.configuration.get("url", "")))
    destination = Destination(
        organization_id=organization_id,
        created_by_user_id=user_id,
        name=payload.name.strip(),
        destination_type=payload.destination_type,
        status=DestinationStatus.ACTIVE,
        configuration=payload.configuration,
        secret_ref=payload.secret_ref,
    )
    db.add(destination)
    db.commit()
    db.refresh(destination)
    return destination


def _authorized_execution(db: Session, organization_id: UUID, execution_id: UUID) -> Execution:
    execution = db.scalar(
        select(Execution).where(
            Execution.id == execution_id, Execution.organization_id == organization_id
        )
    )
    if not execution or execution.status is not ExecutionStatus.SUCCESS:
        raise DomainError(
            "Somente execuções concluídas podem ser distribuídas.", "invalid_distribution"
        )
    return execution


def _artifact(db: Session, execution_id: UUID, artifact_type: str) -> Artifact:
    artifact = db.scalar(
        select(Artifact)
        .where(Artifact.execution_id == execution_id, Artifact.artifact_type == artifact_type)
        .order_by(Artifact.created_at.desc())
    )
    if not artifact or artifact.content is None:
        raise NotFoundError("Artefato solicitado não está disponível.")
    return artifact


def distribute(
    db: Session,
    settings: Settings,
    organization_id: UUID,
    user_id: UUID,
    destination_id: UUID,
    execution_id: UUID,
) -> dict[str, Any]:
    destination = db.scalar(
        select(Destination).where(
            Destination.id == destination_id, Destination.organization_id == organization_id
        )
    )
    if not destination or destination.status is not DestinationStatus.ACTIVE:
        raise NotFoundError("Destino não encontrado ou pausado.")
    execution = _authorized_execution(db, organization_id, execution_id)
    payload = {
        "execution_id": str(execution.id),
        "report_version_id": str(execution.report_version_id),
        "status": execution.status,
    }
    artifact_type = str(destination.configuration.get("artifact_type", "CSV"))
    artifact = _artifact(db, execution.id, artifact_type)
    try:
        if destination.destination_type is DestinationType.EMAIL:
            _send_email(settings, destination, artifact)
        else:
            _send_webhook(settings, destination, payload, artifact)
    except DomainError as exc:
        event_type = "distribution.email"
        if destination.destination_type is not DestinationType.EMAIL:
            event_type = "distribution.webhook"
        db.add(
            OutboxEvent(
                organization_id=organization_id,
                event_type=event_type,
                payload={"destination_id": str(destination.id), "execution_id": str(execution.id)},
                status="FALHOU",
                attempts=settings.distribution_max_retries,
                last_error=exc.code,
            )
        )
        record_audit(
            db,
            action="distribute_execution",
            result=AuditResult.FAILURE,
            organization_id=organization_id,
            actor_user_id=user_id,
            resource_type="destination",
            resource_id=str(destination.id),
            details={"error_code": exc.code},
        )
        db.commit()
        increment("report_manager_distribution_failures_total", labels={"type": event_type})
        raise
    db.add(
        OutboxEvent(
            organization_id=organization_id,
            event_type="distribution.sent",
            payload={"destination_id": str(destination.id), "execution_id": str(execution.id)},
            status="ENVIADO",
            attempts=1,
        )
    )
    record_audit(
        db,
        action="distribute_execution",
        result=AuditResult.SUCCESS,
        organization_id=organization_id,
        actor_user_id=user_id,
        resource_type="destination",
        resource_id=str(destination.id),
    )
    db.commit()
    return {"success": True, "destination_id": destination.id, "execution_id": execution.id}


def _send_email(settings: Settings, destination: Destination, artifact: Artifact) -> None:
    recipients = destination.configuration.get("recipients", [])
    if not isinstance(recipients, list) or not all(
        isinstance(item, str) and "@" in item for item in recipients
    ):
        raise DomainError("Destinatários de e-mail inválidos.", "invalid_distribution")
    password = get_secret_manager(settings).get(settings.smtp_password_secret_ref)
    message = EmailMessage()
    message["Subject"] = str(destination.configuration.get("subject", "Relatório pronto"))
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = ", ".join(recipients)
    message.set_content("O relatório solicitado está disponível em anexo.")
    message.add_attachment(
        artifact.content,
        maintype=artifact.content_type.split("/", 1)[0],
        subtype=artifact.content_type.split("/", 1)[-1],
        filename=artifact.file_name,
    )
    try:
        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
        ) as server:
            if settings.smtp_use_tls:
                server.starttls()
            server.login(settings.smtp_username, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise DomainError("Não foi possível enviar o e-mail SMTP.", "smtp_failed", 502) from exc


def _send_webhook(
    settings: Settings, destination: Destination, payload: dict[str, Any], artifact: Artifact
) -> None:
    secret = get_secret_manager(settings).get(destination.secret_ref or "")
    content = artifact.content or b""
    body = json.dumps(
        {
            **payload,
            "artifact": {
                "file_name": artifact.file_name,
                "content_type": artifact.content_type,
                "content_base64": b64encode(content).decode("ascii"),
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    url = str(destination.configuration["url"])
    last_error: httpx.HTTPError | None = None
    for attempt in range(settings.distribution_max_retries):
        try:
            response = httpx.post(
                url,
                content=body,
                headers={"Content-Type": "application/json", "X-Report-Signature": signature},
                timeout=settings.webhook_timeout_seconds,
                follow_redirects=False,
            )
            response.raise_for_status()
            return
        except httpx.HTTPError as exc:
            last_error = exc
            increment("report_manager_distribution_retries_total", labels={"type": "webhook"})
            if attempt + 1 < settings.distribution_max_retries:
                time.sleep(2**attempt)
    raise DomainError("Não foi possível entregar o webhook.", "webhook_failed", 502) from last_error


def validate_webhook_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise DomainError("URL de webhook inválida.", "invalid_distribution")
    try:
        port = parsed.port
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        }
    except (OSError, ValueError) as exc:
        raise DomainError(
            "O host do webhook não pôde ser validado.", "invalid_distribution"
        ) from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise DomainError(
                "O webhook não pode apontar para uma rede privada.", "invalid_distribution"
            )

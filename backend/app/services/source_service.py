from __future__ import annotations

from pathlib import PurePath
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.core.secrets import get_secret_manager
from app.db.enums import (
    AuditResult,
    DataClassification,
    GrantTargetType,
    Role,
    SensitivityAction,
    SourceStatus,
    SourceType,
    SourceVersionStatus,
)
from app.db.models import (
    CatalogField,
    CatalogObject,
    DataSource,
    DataSourceVersion,
    SourceGrant,
    utc_now,
)
from app.schemas.source import SourceCreateRequest
from app.services.audit import record_audit
from app.services.connectors import RelationalConnector, validate_public_host
from app.services.source_parser import checksum, parse_file

DATABASE_SOURCE_TYPES = {SourceType.POSTGRESQL, SourceType.ORACLE, SourceType.SQLSERVER}
FILE_SOURCE_TYPES = {SourceType.CSV, SourceType.EXCEL, SourceType.JSON}
ALLOWED_EXTENSIONS = {
    SourceType.CSV: {".csv"},
    SourceType.EXCEL: {".xls", ".xlsx"},
    SourceType.JSON: {".json"},
}


def ensure_source(db: Session, organization_id: UUID, source_id: UUID) -> DataSource:
    source = db.scalar(
        select(DataSource).where(
            DataSource.id == source_id, DataSource.organization_id == organization_id
        )
    )
    if not source:
        raise NotFoundError("Fonte de dados não encontrada.")
    return source


def ensure_source_access(
    db: Session,
    source: DataSource,
    user_id: UUID,
    role: Role | None,
    required_permission: str = "VIEW",
) -> None:
    """Validate source access after tenant resolution and before external I/O."""

    if role in {Role.PLATFORM_OPERATOR, Role.ORGANIZATION_ADMIN}:
        return
    if source.owner_user_id == user_id:
        return
    permissions = {"VIEW": 1, "USE": 2, "MANAGE": 3}
    required_level = permissions.get(required_permission.upper(), 1)
    grants = db.scalars(
        select(SourceGrant).where(
            SourceGrant.data_source_id == source.id,
            or_(
                (SourceGrant.target_type == GrantTargetType.USER)
                & (SourceGrant.target_id == str(user_id)),
                (SourceGrant.target_type == GrantTargetType.ROLE)
                & (SourceGrant.target_id == str(role)),
                (SourceGrant.target_type == GrantTargetType.ORGANIZATION)
                & (SourceGrant.target_id == str(source.organization_id)),
            ),
        )
    ).all()
    if any(permissions.get(grant.permission.upper(), 0) >= required_level for grant in grants):
        return
    raise ForbiddenError("Usuário não possui acesso à fonte de dados.")


def create_source_grant(
    db: Session,
    source: DataSource,
    actor_user_id: UUID,
    target_type: GrantTargetType,
    target_id: str,
    permission: str,
) -> SourceGrant:
    normalized_target = target_id.strip()
    normalized_permission = permission.strip().upper()
    if normalized_permission not in {"VIEW", "USE", "MANAGE"}:
        raise ConflictError("Permissão de fonte inválida.")
    if target_type is GrantTargetType.ORGANIZATION:
        if normalized_target != str(source.organization_id):
            raise ForbiddenError("O grant deve apontar para a própria organização.")
    elif target_type is GrantTargetType.USER:
        from app.db.models import Membership

        try:
            target_user_id = UUID(normalized_target)
        except ValueError as exc:
            raise ConflictError("O usuário do grant é inválido.") from exc
        member = db.scalar(
            select(Membership).where(
                Membership.organization_id == source.organization_id,
                Membership.user_id == target_user_id,
                Membership.is_active.is_(True),
            )
        )
        if not member:
            raise ForbiddenError("O usuário do grant não pertence à organização.")
    elif target_type is GrantTargetType.ROLE:
        try:
            role = Role(normalized_target)
        except ValueError as exc:
            raise ConflictError("Papel inválido para o grant.") from exc
        if role is Role.PLATFORM_OPERATOR:
            raise ForbiddenError("O papel de operador não pode ser concedido no cliente.")
    else:
        raise ConflictError("Tipo de alvo do grant não suportado.")
    existing = db.scalar(
        select(SourceGrant).where(
            SourceGrant.data_source_id == source.id,
            SourceGrant.target_type == target_type,
            SourceGrant.target_id == normalized_target,
        )
    )
    if existing:
        existing.permission = normalized_permission
        grant = existing
    else:
        grant = SourceGrant(
            data_source_id=source.id,
            target_type=target_type,
            target_id=normalized_target,
            permission=normalized_permission,
        )
        db.add(grant)
    record_audit(
        db,
        action="create_source_grant",
        result=AuditResult.SUCCESS,
        organization_id=source.organization_id,
        actor_user_id=actor_user_id,
        resource_type="source_grant",
        details={"target_type": target_type, "permission": normalized_permission},
    )
    db.commit()
    db.refresh(grant)
    return grant


def create_source(
    db: Session, organization_id: UUID, user_id: UUID, payload: SourceCreateRequest
) -> DataSource:
    if payload.source_type in DATABASE_SOURCE_TYPES and not payload.secret_ref:
        raise DomainError("Fonte de banco exige referência de segredo.", "invalid_source")
    if payload.source_type in DATABASE_SOURCE_TYPES and payload.connection:
        validate_public_host(payload.connection.host)
    source = DataSource(
        organization_id=organization_id,
        owner_user_id=user_id,
        name=payload.name.strip(),
        source_type=payload.source_type,
        status=SourceStatus.DRAFT,
        connection_config=payload.connection.model_dump(exclude_none=True)
        if payload.connection
        else {},
        import_config=payload.import_config,
        secret_ref=payload.secret_ref,
    )
    db.add(source)
    record_audit(
        db,
        action="create_source",
        result=AuditResult.SUCCESS,
        organization_id=organization_id,
        actor_user_id=user_id,
        resource_type="source",
        details={"source_type": payload.source_type},
    )
    db.commit()
    db.refresh(source)
    return source


def sanitize_file_name(file_name: str, source_type: SourceType) -> str:
    if not file_name or file_name != PurePath(file_name).name or "\\" in file_name:
        raise DomainError("Nome de arquivo inválido.", "invalid_file_name")
    suffix = PurePath(file_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS[source_type]:
        raise DomainError("Extensão de arquivo não permitida para a fonte.", "invalid_file_type")
    return file_name


def validate_file_signature(file_name: str, content: bytes, source_type: SourceType) -> None:
    suffix = PurePath(file_name).suffix.lower()
    if source_type is SourceType.EXCEL and suffix == ".xlsx" and not content.startswith(b"PK"):
        raise DomainError("O arquivo XLSX não possui assinatura válida.", "invalid_file_type")
    if (
        source_type is SourceType.EXCEL
        and suffix == ".xls"
        and not content.startswith(b"\xd0\xcf\x11\xe0")
    ):
        raise DomainError("O arquivo XLS não possui assinatura válida.", "invalid_file_type")
    if source_type is SourceType.JSON:
        stripped = content.lstrip()
        if not stripped.startswith((b"{", b"[")):
            raise DomainError("O arquivo JSON não possui formato válido.", "invalid_file_type")


def _create_catalog(db: Session, version: DataSourceVersion) -> None:
    raw_objects = version.schema_snapshot.get("objects")
    objects = (
        raw_objects
        if isinstance(raw_objects, list) and raw_objects
        else [
            {
                "name": "dataset",
                "type": "TABLE",
                "columns": version.schema_snapshot.get("columns", []),
            }
        ]
    )
    for raw_object in objects:
        if not isinstance(raw_object, dict):
            continue
        catalog_object = CatalogObject(
            source_version_id=version.id,
            object_name=str(raw_object.get("name", "dataset")),
            object_type=str(raw_object.get("type", "TABLE")),
            description="Estrutura observada na versão da fonte",
        )
        db.add(catalog_object)
        db.flush()
        for column in raw_object.get("columns", []):
            if not isinstance(column, dict) or not column.get("name"):
                continue
            db.add(
                CatalogField(
                    catalog_object_id=catalog_object.id,
                    field_name=str(column["name"]),
                    data_type=str(column.get("type", "unknown")),
                    classification=DataClassification(
                        str(column.get("classification", DataClassification.INTERNAL))
                    ),
                    sensitivity_action=SensitivityAction(
                        str(column.get("action", SensitivityAction.ALLOW))
                    ),
                    confidence=str(column.get("confidence", "BAIXA")),
                    detection_reason=str(column.get("reason", "")),
                )
            )


def create_file_version(
    db: Session,
    settings: Settings,
    source: DataSource,
    user_id: UUID,
    file_name: str,
    content_type: str | None,
    content: bytes,
    import_config: dict[str, Any],
) -> DataSourceVersion:
    if source.source_type not in FILE_SOURCE_TYPES:
        raise DomainError("A fonte não aceita upload de arquivo.", "invalid_source_type")
    if len(content) > settings.source_max_file_bytes:
        raise DomainError(
            "O arquivo excede o tamanho máximo configurado.", "source_limit_exceeded", 413
        )
    safe_name = sanitize_file_name(file_name, source.source_type)
    validate_file_signature(safe_name, content, source.source_type)
    rows, schema = parse_file(
        source.source_type,
        content,
        {**source.import_config, **import_config},
        min(settings.execution_max_rows, settings.source_max_sheet_rows),
        settings.source_max_columns,
        settings.source_max_json_depth,
    )
    if not rows and source.source_type is SourceType.JSON:
        raise DomainError("O JSON não possui registros.", "invalid_source_file")
    previous = db.scalars(
        select(DataSourceVersion)
        .where(DataSourceVersion.data_source_id == source.id)
        .with_for_update()
    ).all()
    for version in previous:
        version.is_latest_valid = False
    next_number = max((version.version_number for version in previous), default=0) + 1
    version = DataSourceVersion(
        data_source_id=source.id,
        version_number=next_number,
        status=SourceVersionStatus.VALID,
        is_latest_valid=True,
        file_name=safe_name,
        content_type=content_type,
        content=content,
        checksum=checksum(content),
        schema_snapshot=schema,
        import_config={**source.import_config, **import_config},
        created_by_user_id=user_id,
    )
    db.add(version)
    db.flush()
    _create_catalog(db, version)
    source.import_config = version.import_config
    source.status = SourceStatus.ACTIVE
    source.last_tested_at = utc_now()
    source.last_test_error = None
    record_audit(
        db,
        action="create_source_version",
        result=AuditResult.SUCCESS,
        organization_id=source.organization_id,
        actor_user_id=user_id,
        resource_type="source_version",
        resource_id=str(version.id),
        details={"version_number": version.version_number, "checksum": version.checksum},
    )
    db.commit()
    db.refresh(version)
    return version


def test_database_source(
    db: Session, settings: Settings, source: DataSource, user_id: UUID
) -> dict[str, Any]:
    if source.source_type not in DATABASE_SOURCE_TYPES:
        version = db.scalar(
            select(DataSourceVersion)
            .where(
                DataSourceVersion.data_source_id == source.id,
                DataSourceVersion.is_latest_valid.is_(True),
            )
            .order_by(DataSourceVersion.version_number.desc())
        )
        if not version:
            raise DomainError("A fonte ainda não possui versão válida.", "source_not_ready")
        return version.schema_snapshot
    connector = RelationalConnector(
        get_secret_manager(settings),
        settings.source_connection_timeout_seconds,
        settings.public_source_ips_only,
    )
    try:
        snapshot = connector.test_connection(source)
        _create_database_version(db, source, user_id, snapshot)
        source.status = SourceStatus.ACTIVE
        source.last_tested_at = utc_now()
        source.last_test_error = None
        record_audit(
            db,
            action="test_source",
            result=AuditResult.SUCCESS,
            organization_id=source.organization_id,
            actor_user_id=user_id,
            resource_type="source",
            resource_id=str(source.id),
            details={"source_type": source.source_type},
        )
        db.commit()
        return snapshot
    except DomainError as exc:
        source.status = SourceStatus.ERROR
        source.last_tested_at = utc_now()
        source.last_test_error = exc.message
        record_audit(
            db,
            action="test_source",
            result=AuditResult.FAILURE,
            organization_id=source.organization_id,
            actor_user_id=user_id,
            resource_type="source",
            resource_id=str(source.id),
        )
        db.commit()
        raise


def _create_database_version(
    db: Session, source: DataSource, user_id: UUID, schema_snapshot: dict[str, Any]
) -> DataSourceVersion:
    previous = db.scalars(
        select(DataSourceVersion)
        .where(DataSourceVersion.data_source_id == source.id)
        .with_for_update()
    ).all()
    for version in previous:
        version.is_latest_valid = False
    version = DataSourceVersion(
        data_source_id=source.id,
        version_number=max((item.version_number for item in previous), default=0) + 1,
        status=SourceVersionStatus.VALID,
        is_latest_valid=True,
        content_type="application/json",
        checksum=None,
        schema_snapshot=schema_snapshot,
        import_config=source.import_config,
        created_by_user_id=user_id,
    )
    db.add(version)
    db.flush()
    _create_catalog(db, version)
    return version


def latest_version(db: Session, source_id: UUID) -> DataSourceVersion | None:
    return db.scalar(
        select(DataSourceVersion)
        .where(
            DataSourceVersion.data_source_id == source_id,
            DataSourceVersion.is_latest_valid.is_(True),
        )
        .order_by(DataSourceVersion.version_number.desc())
    )

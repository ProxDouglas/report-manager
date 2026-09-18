import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select

from app.api.deps import RequestContext, require_roles
from app.core.config import Settings, get_settings
from app.core.errors import DomainError, ForbiddenError, NotFoundError
from app.db.enums import AuditResult, Role, SourceType
from app.db.models import CatalogField, CatalogObject, DataSource, DataSourceVersion, SourceGrant
from app.schemas.source import (
    CatalogFieldUpdateRequest,
    SourceCreateRequest,
    SourceGrantCreateRequest,
    SourceGrantResponse,
    SourceResponse,
    SourceTestResponse,
    SourceVersionResponse,
)
from app.services.audit import record_audit
from app.services.source_service import (
    create_file_version,
    create_source,
    create_source_grant,
    ensure_source,
    ensure_source_access,
    latest_version,
    test_database_source,
)

router = APIRouter(prefix="/sources", tags=["sources"])
source_reader = require_roles(
    Role.ORGANIZATION_ADMIN, Role.REPORT_CREATOR, Role.VIEWER
)
source_writer = require_roles(Role.ORGANIZATION_ADMIN, Role.REPORT_CREATOR)
source_grant_manager = require_roles(Role.ORGANIZATION_ADMIN)


@router.get("", response_model=list[SourceResponse])
def list_sources(context: RequestContext = Depends(source_reader)) -> list[SourceResponse]:  # noqa: B008
    sources = context.db.scalars(
        select(DataSource)
        .where(DataSource.organization_id == context.organization.id)
        .order_by(DataSource.name)
    ).all()
    visible: list[DataSource] = []
    for source in sources:
        try:
            ensure_source_access(context.db, source, context.user.id, context.role)
            visible.append(source)
        except ForbiddenError:
            continue
    return [SourceResponse.model_validate(source) for source in visible]


@router.post("", response_model=SourceResponse, status_code=201)
def create_source_endpoint(
    payload: SourceCreateRequest,
    context: RequestContext = Depends(source_writer),  # noqa: B008
) -> SourceResponse:
    source = create_source(context.db, context.organization.id, context.user.id, payload)
    return SourceResponse.model_validate(source)


@router.post("/upload", response_model=SourceVersionResponse, status_code=201)
def upload_source(
    name: Annotated[str, Form(min_length=2, max_length=160)],
    source_type: Annotated[SourceType, Form()],
    file: Annotated[UploadFile, File()],
    import_config: Annotated[str, Form()] = "{}",
    context: RequestContext = Depends(source_writer),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> SourceVersionResponse:
    if source_type not in {SourceType.CSV, SourceType.EXCEL, SourceType.JSON}:
        raise DomainError("Upload aceita somente CSV, Excel ou JSON.", "invalid_source_type")
    try:
        configuration: dict[str, Any] = json.loads(import_config)
    except json.JSONDecodeError as exc:
        raise DomainError(
            "import_config deve ser um JSON válido.", "invalid_import_config"
        ) from exc
    content = file.file.read(settings.source_max_file_bytes + 1)
    source = create_source(
        context.db,
        context.organization.id,
        context.user.id,
        SourceCreateRequest(name=name, source_type=source_type, import_config=configuration),
    )
    version = create_file_version(
        context.db,
        settings,
        source,
        context.user.id,
        file.filename or "upload",
        file.content_type,
        content,
        configuration,
    )
    return SourceVersionResponse.model_validate(version)


@router.post("/{source_id}/upload", response_model=SourceVersionResponse, status_code=201)
def upload_source_version(
    source_id: UUID,
    file: Annotated[UploadFile, File()],
    import_config: Annotated[str, Form()] = "{}",
    context: RequestContext = Depends(source_writer),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> SourceVersionResponse:
    source = ensure_source(context.db, context.organization.id, source_id)
    ensure_source_access(context.db, source, context.user.id, context.role, "MANAGE")
    try:
        configuration: dict[str, Any] = json.loads(import_config)
    except json.JSONDecodeError as exc:
        raise DomainError(
            "import_config deve ser um JSON válido.", "invalid_import_config"
        ) from exc
    content = file.file.read(settings.source_max_file_bytes + 1)
    version = create_file_version(
        context.db,
        settings,
        source,
        context.user.id,
        file.filename or "upload",
        file.content_type,
        content,
        configuration,
    )
    return SourceVersionResponse.model_validate(version)


@router.post("/{source_id}/test", response_model=SourceTestResponse)
def test_source(
    source_id: UUID,
    context: RequestContext = Depends(source_writer),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> SourceTestResponse:
    source = ensure_source(context.db, context.organization.id, source_id)
    ensure_source_access(context.db, source, context.user.id, context.role, "MANAGE")
    schema = test_database_source(context.db, settings, source, context.user.id)
    return SourceTestResponse(
        success=True, message="Fonte validada com sucesso.", schema_snapshot=schema
    )


@router.get("/{source_id}/versions", response_model=list[SourceVersionResponse])
def list_source_versions(
    source_id: UUID,
    context: RequestContext = Depends(source_reader),  # noqa: B008
) -> list[SourceVersionResponse]:
    source = ensure_source(context.db, context.organization.id, source_id)
    ensure_source_access(context.db, source, context.user.id, context.role)
    versions = context.db.scalars(
        select(DataSourceVersion)
        .where(DataSourceVersion.data_source_id == source_id)
        .order_by(DataSourceVersion.version_number.desc())
    ).all()
    return [SourceVersionResponse.model_validate(version) for version in versions]


@router.get("/{source_id}/catalog")
def source_catalog(
    source_id: UUID,
    context: RequestContext = Depends(source_reader),  # noqa: B008
) -> dict[str, Any]:
    source = ensure_source(context.db, context.organization.id, source_id)
    ensure_source_access(context.db, source, context.user.id, context.role)
    version = latest_version(context.db, source.id)
    if not version:
        raise NotFoundError("A fonte ainda não possui catálogo válido.")
    objects = context.db.scalars(
        select(CatalogObject).where(CatalogObject.source_version_id == version.id)
    ).all()
    result = []
    for catalog_object in objects:
        fields = context.db.scalars(
            select(CatalogField).where(CatalogField.catalog_object_id == catalog_object.id)
        ).all()
        result.append(
            {
                "object_name": catalog_object.object_name,
                "object_type": catalog_object.object_type,
                "fields": [
                    {
                        "id": field.id,
                        "name": field.field_name,
                        "type": field.data_type,
                        "classification": field.classification,
                        "action": field.sensitivity_action,
                        "confidence": field.confidence,
                        "confirmed": field.is_confirmed,
                    }
                    for field in fields
                ],
            }
        )
    return {
        "source_id": source.id,
        "version_id": version.id,
        "version_number": version.version_number,
        "objects": result,
    }


@router.patch("/{source_id}/catalog/fields/{field_id}")
def update_catalog_field(
    source_id: UUID,
    field_id: UUID,
    payload: CatalogFieldUpdateRequest,
    context: RequestContext = Depends(source_writer),  # noqa: B008
) -> dict[str, object]:
    source = ensure_source(context.db, context.organization.id, source_id)
    ensure_source_access(context.db, source, context.user.id, context.role, "MANAGE")
    field = context.db.scalar(
        select(CatalogField)
        .join(CatalogObject, CatalogObject.id == CatalogField.catalog_object_id)
        .join(DataSourceVersion, DataSourceVersion.id == CatalogObject.source_version_id)
        .where(
            CatalogField.id == field_id,
            DataSourceVersion.data_source_id == source.id,
            DataSourceVersion.is_latest_valid.is_(True),
        )
    )
    if not field:
        raise NotFoundError("Campo do catálogo não encontrado.")
    field.classification = payload.classification
    field.sensitivity_action = payload.sensitivity_action
    field.is_confirmed = True
    record_audit(
        context.db,
        action="confirm_catalog_classification",
        result=AuditResult.SUCCESS,
        organization_id=source.organization_id,
        actor_user_id=context.user.id,
        resource_type="catalog_field",
        resource_id=str(field.id),
        details={
            "classification": payload.classification,
            "sensitivity_action": payload.sensitivity_action,
        },
    )
    context.db.commit()
    return {
        "id": field.id,
        "classification": field.classification,
        "action": field.sensitivity_action,
        "confirmed": field.is_confirmed,
    }


@router.get("/{source_id}/versions/{version_id}/diff")
def source_version_diff(
    source_id: UUID,
    version_id: UUID,
    compare_to_version_id: UUID | None = None,
    context: RequestContext = Depends(source_reader),  # noqa: B008
) -> dict[str, object]:
    source = ensure_source(context.db, context.organization.id, source_id)
    ensure_source_access(context.db, source, context.user.id, context.role)
    current = context.db.scalar(
        select(DataSourceVersion).where(
            DataSourceVersion.id == version_id,
            DataSourceVersion.data_source_id == source.id,
        )
    )
    if not current:
        raise NotFoundError("Versão da fonte não encontrada.")
    previous = None
    if compare_to_version_id:
        previous = context.db.scalar(
            select(DataSourceVersion).where(
                DataSourceVersion.id == compare_to_version_id,
                DataSourceVersion.data_source_id == source.id,
            )
        )
    if previous is None:
        previous = context.db.scalar(
            select(DataSourceVersion)
            .where(
                DataSourceVersion.data_source_id == source.id,
                DataSourceVersion.version_number < current.version_number,
            )
            .order_by(DataSourceVersion.version_number.desc())
        )
    current_fields = {
        str(item.get("name")): item
        for item in current.schema_snapshot.get("columns", [])
        if item.get("name")
    }
    previous_fields = {
        str(item.get("name")): item
        for item in (previous.schema_snapshot.get("columns", []) if previous else [])
        if item.get("name")
    }
    added = sorted(set(current_fields) - set(previous_fields))
    removed = sorted(set(previous_fields) - set(current_fields))
    changed = sorted(
        name
        for name in set(current_fields) & set(previous_fields)
        if current_fields[name].get("type") != previous_fields[name].get("type")
        or current_fields[name].get("classification")
        != previous_fields[name].get("classification")
    )
    return {
        "source_id": source.id,
        "version_id": current.id,
        "compare_to_version_id": previous.id if previous else None,
        "added": added,
        "removed": removed,
        "changed": changed,
    }


@router.get("/{source_id}/grants", response_model=list[SourceGrantResponse])
def list_source_grants(
    source_id: UUID,
    context: RequestContext = Depends(source_grant_manager),  # noqa: B008
) -> list[SourceGrantResponse]:
    source = ensure_source(context.db, context.organization.id, source_id)
    grants = context.db.scalars(
        select(SourceGrant)
        .where(SourceGrant.data_source_id == source.id)
        .order_by(SourceGrant.created_at)
    ).all()
    return [SourceGrantResponse.model_validate(grant) for grant in grants]


@router.post("/{source_id}/grants", response_model=SourceGrantResponse, status_code=201)
def add_source_grant(
    source_id: UUID,
    payload: SourceGrantCreateRequest,
    context: RequestContext = Depends(source_grant_manager),  # noqa: B008
) -> SourceGrantResponse:
    source = ensure_source(context.db, context.organization.id, source_id)
    grant = create_source_grant(
        context.db,
        source,
        context.user.id,
        payload.target_type,
        payload.target_id,
        payload.permission,
    )
    return SourceGrantResponse.model_validate(grant)


@router.delete("/{source_id}/grants/{grant_id}")
def delete_source_grant(
    source_id: UUID,
    grant_id: UUID,
    context: RequestContext = Depends(source_grant_manager),  # noqa: B008
) -> dict[str, object]:
    source = ensure_source(context.db, context.organization.id, source_id)
    grant = context.db.scalar(
        select(SourceGrant).where(
            SourceGrant.id == grant_id, SourceGrant.data_source_id == source.id
        )
    )
    if not grant:
        raise NotFoundError("Grant da fonte não encontrado.")
    context.db.delete(grant)
    context.db.commit()
    return {"deleted": True, "id": grant_id}

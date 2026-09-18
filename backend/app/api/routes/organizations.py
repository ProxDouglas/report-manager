from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import RequestContext, require_application_context, require_platform_operator
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.security import hash_password
from app.db.enums import AuditResult, LicenseStatus, OrganizationStatus, Role
from app.db.models import License, Membership, Organization, User
from app.schemas.common import OrganizationResponse
from app.schemas.organization import LicenseChangeRequest, OrganizationCreateRequest
from app.services.audit import record_audit

router = APIRouter(prefix="/organizations", tags=["licensing"])


def organization_response(db: Session, organization: Organization) -> OrganizationResponse:
    license_record = db.scalar(select(License).where(License.organization_id == organization.id))
    return OrganizationResponse.model_validate(
        {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "status": organization.status,
            "license": license_record,
        }
    )


@router.get("/mine", response_model=list[OrganizationResponse])
def my_organizations(
    context: RequestContext = Depends(require_application_context),
) -> list[OrganizationResponse]:  # noqa: B008
    db = context.db
    if context.user.is_platform_operator:
        organizations = db.scalars(select(Organization).order_by(Organization.name)).all()
    else:
        organizations = db.scalars(
            select(Organization)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(Membership.user_id == context.user.id, Membership.is_active.is_(True))
            .order_by(Organization.name)
        ).all()
    return [organization_response(db, organization) for organization in organizations]


@router.get("", response_model=list[OrganizationResponse])
def list_organizations(
    context: RequestContext = Depends(require_platform_operator),
) -> list[OrganizationResponse]:  # noqa: B008
    organizations = context.db.scalars(select(Organization).order_by(Organization.name)).all()
    return [organization_response(context.db, organization) for organization in organizations]


@router.post("", response_model=OrganizationResponse, status_code=201)
def create_organization(
    payload: OrganizationCreateRequest,
    context: RequestContext = Depends(require_platform_operator),  # noqa: B008
) -> OrganizationResponse:
    db = context.db
    if db.scalar(select(Organization.id).where(Organization.slug == payload.slug)):
        raise ConflictError("Já existe uma organização com este slug.")
    normalized_email = payload.admin_email.strip().lower()
    if db.scalar(select(User.id).where(User.email == normalized_email)):
        raise ConflictError("Já existe um usuário com este e-mail.")
    try:
        password_hash = hash_password(payload.temporary_password)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    organization = Organization(
        name=payload.name.strip(), slug=payload.slug, status=OrganizationStatus.ACTIVE
    )
    db.add(organization)
    db.flush()
    admin = User(
        email=normalized_email,
        display_name=payload.admin_name.strip(),
        password_hash=password_hash,
        must_change_password=True,
    )
    db.add(admin)
    db.flush()
    db.add(
        Membership(organization_id=organization.id, user_id=admin.id, role=Role.ORGANIZATION_ADMIN)
    )
    db.add(
        License(
            organization_id=organization.id,
            status=LicenseStatus.ACTIVE,
            starts_on=payload.starts_on or date.today(),
            ends_on=payload.ends_on,
        )
    )
    record_audit(
        db,
        action="create_organization",
        result=AuditResult.SUCCESS,
        actor_user_id=context.user.id,
        organization_id=organization.id,
        resource_type="organization",
        resource_id=str(organization.id),
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            "Não foi possível criar a organização com os dados informados."
        ) from exc
    db.refresh(organization)
    return organization_response(db, organization)


@router.post("/{organization_id}/suspend", response_model=OrganizationResponse)
def suspend_organization(
    organization_id: UUID,
    payload: LicenseChangeRequest,
    context: RequestContext = Depends(require_platform_operator),  # noqa: B008
) -> OrganizationResponse:
    license_record = context.db.scalar(
        select(License).where(License.organization_id == organization_id)
    )
    organization = context.db.get(Organization, organization_id)
    if not organization or not license_record:
        raise NotFoundError("Organização ou licença não encontrada.")
    license_record.status = LicenseStatus.SUSPENDED
    license_record.reason = payload.reason
    organization.status = OrganizationStatus.SUSPENDED
    record_audit(
        context.db,
        action="suspend_license",
        result=AuditResult.SUCCESS,
        actor_user_id=context.user.id,
        organization_id=organization_id,
        resource_type="license",
        resource_id=str(license_record.id),
        details={"reason": payload.reason},
    )
    context.db.commit()
    return organization_response(context.db, organization)


@router.post("/{organization_id}/reactivate", response_model=OrganizationResponse)
def reactivate_organization(
    organization_id: UUID,
    payload: LicenseChangeRequest,
    context: RequestContext = Depends(require_platform_operator),  # noqa: B008
) -> OrganizationResponse:
    license_record = context.db.scalar(
        select(License).where(License.organization_id == organization_id)
    )
    organization = context.db.get(Organization, organization_id)
    if not organization or not license_record:
        raise NotFoundError("Organização ou licença não encontrada.")
    license_record.status = LicenseStatus.ACTIVE
    license_record.reason = payload.reason
    organization.status = OrganizationStatus.ACTIVE
    record_audit(
        context.db,
        action="reactivate_license",
        result=AuditResult.SUCCESS,
        actor_user_id=context.user.id,
        organization_id=organization_id,
        resource_type="license",
        resource_id=str(license_record.id),
        details={"reason": payload.reason},
    )
    context.db.commit()
    return organization_response(context.db, organization)

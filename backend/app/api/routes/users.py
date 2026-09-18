from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import RequestContext, require_roles
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.security import hash_password
from app.db.enums import AuditResult, Role
from app.db.models import Membership, User
from app.schemas.user import MembershipChangeRequest, MembershipResponse, UserCreateRequest
from app.services.audit import record_audit

router = APIRouter(prefix="/users", tags=["identity"])
admin = require_roles(Role.ORGANIZATION_ADMIN)


def membership_response(membership: Membership, user: User) -> MembershipResponse:
    return MembershipResponse.model_validate(
        {
            "id": membership.id,
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": membership.role,
            "is_active": membership.is_active,
        }
    )


@router.get("", response_model=list[MembershipResponse])
def list_users(context: RequestContext = Depends(admin)) -> list[MembershipResponse]:  # noqa: B008
    rows = context.db.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == context.organization.id)
        .order_by(func.lower(User.display_name))
    ).all()
    return [membership_response(membership, user) for membership, user in rows]


@router.post("", response_model=MembershipResponse, status_code=201)
def create_user(
    payload: UserCreateRequest, context: RequestContext = Depends(admin)
) -> MembershipResponse:  # noqa: B008
    email = payload.email.strip().lower()
    user = context.db.scalar(select(User).where(User.email == email))
    if user:
        membership = context.db.scalar(
            select(Membership).where(
                Membership.organization_id == context.organization.id, Membership.user_id == user.id
            )
        )
        if membership:
            raise ConflictError("Usuário já pertence à organização.")
    else:
        try:
            password_hash = hash_password(payload.temporary_password)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        user = User(
            email=email,
            display_name=payload.display_name.strip(),
            password_hash=password_hash,
            must_change_password=True,
        )
        context.db.add(user)
        context.db.flush()
    if payload.role is Role.PLATFORM_OPERATOR:
        raise ConflictError("Operador da plataforma não pode ser atribuído neste fluxo.")
    membership = Membership(
        organization_id=context.organization.id, user_id=user.id, role=payload.role
    )
    context.db.add(membership)
    record_audit(
        context.db,
        action="create_membership",
        result=AuditResult.SUCCESS,
        organization_id=context.organization.id,
        actor_user_id=context.user.id,
        resource_type="membership",
        details={"role": payload.role},
    )
    try:
        context.db.commit()
    except IntegrityError as exc:
        context.db.rollback()
        raise ConflictError("Não foi possível criar o usuário.") from exc
    context.db.refresh(membership)
    return membership_response(membership, user)


@router.patch("/{membership_id}", response_model=MembershipResponse)
def change_membership(
    membership_id: UUID, payload: MembershipChangeRequest, context: RequestContext = Depends(admin)
) -> MembershipResponse:  # noqa: B008
    membership = context.db.scalar(
        select(Membership).where(
            Membership.id == membership_id, Membership.organization_id == context.organization.id
        )
    )
    if not membership:
        raise NotFoundError("Membership não encontrado.")
    if payload.role is Role.PLATFORM_OPERATOR:
        raise ConflictError("Operador da plataforma não pode ser atribuído neste fluxo.")
    membership.role = payload.role
    membership.is_active = payload.is_active
    user = context.db.get(User, membership.user_id)
    record_audit(
        context.db,
        action="change_membership",
        result=AuditResult.SUCCESS,
        organization_id=context.organization.id,
        actor_user_id=context.user.id,
        resource_type="membership",
        resource_id=str(membership.id),
        details={"role": payload.role, "is_active": payload.is_active},
    )
    context.db.commit()
    if not user:
        raise NotFoundError("Usuário do membership não encontrado.")
    return membership_response(membership, user)

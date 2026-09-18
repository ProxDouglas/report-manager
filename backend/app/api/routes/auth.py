from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_session
from app.core.config import Settings, get_settings
from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError, ValidationError
from app.core.security import hash_password, hash_token, new_session_token, verify_password
from app.db.enums import AuditResult, Role
from app.db.models import License, Membership, Organization, User, UserSession, utc_now
from app.db.session import get_db
from app.schemas.auth import BootstrapRequest, ChangePasswordRequest, LoginRequest
from app.schemas.common import MessageResponse, OrganizationResponse, SessionResponse, UserResponse
from app.services.audit import record_audit

router = APIRouter(prefix="/auth", tags=["identity"])
dummy_password_hash = (
    "$argon2id$v=19$m=65536,t=3,p=4$d+tCG/UBBTbKAfv9Cbx8GA$"
    "K8+7z/C8uSk8IydU4+VUP3IgS6kSmiw+7O7gu0JVnQQ"
)


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


def session_response(db: Session, user: User, session: UserSession) -> SessionResponse:
    if user.is_platform_operator:
        organizations = db.scalars(select(Organization).order_by(Organization.name)).all()
    else:
        organizations = db.scalars(
            select(Organization)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(Membership.user_id == user.id, Membership.is_active.is_(True))
            .order_by(Organization.name)
        ).all()
    active_role = Role.PLATFORM_OPERATOR if user.is_platform_operator else None
    if active_role is None and session.active_organization_id:
        active_role = db.scalar(
            select(Membership.role).where(
                Membership.organization_id == session.active_organization_id,
                Membership.user_id == user.id,
                Membership.is_active.is_(True),
            )
        )
    return SessionResponse(
        user=UserResponse.model_validate(user),
        organizations=[organization_response(db, item) for item in organizations],
        active_organization_id=session.active_organization_id,
        active_role=active_role,
    )


@router.post("/bootstrap", response_model=SessionResponse, status_code=201)
def bootstrap(
    payload: BootstrapRequest,
    response: Response,
    settings: Settings = Depends(get_settings),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> SessionResponse:
    if not settings.allow_bootstrap:
        raise ForbiddenError("Bootstrap desativado neste ambiente.")
    if db.scalar(select(User.id).limit(1)):
        raise ConflictError("O operador inicial já foi criado.")
    email = payload.email.strip().lower()
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=password_hash,
        must_change_password=False,
        is_platform_operator=True,
    )
    db.add(user)
    record_audit(db, action="bootstrap_operator", result=AuditResult.SUCCESS, actor_user_id=None)
    db.commit()
    db.refresh(user)
    session = create_session(db, user, settings)
    response.set_cookie(
        settings.session_cookie_name,
        session[0],
        httponly=True,
        secure=settings.app_env != "local",
        samesite="lax",
    )
    return session_response(db, user, session[1])


def create_session(db: Session, user: User, settings: Settings) -> tuple[str, UserSession]:
    token = new_session_token()
    memberships = db.scalars(
        select(Membership)
        .where(Membership.user_id == user.id, Membership.is_active.is_(True))
        .limit(1)
    ).all()
    active_organization_id = memberships[0].organization_id if memberships else None
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        active_organization_id=active_organization_id,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return token, session


@router.post("/login", response_model=SessionResponse)
def login(
    payload: LoginRequest,
    response: Response,
    settings: Settings = Depends(get_settings),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> SessionResponse:
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if not user:
        verify_password(dummy_password_hash, payload.password)
        raise UnauthorizedError("Credenciais inválidas.")
    now = datetime.now(UTC)
    if user.locked_until and user.locked_until > now:
        raise UnauthorizedError("Acesso temporariamente bloqueado.")
    if not verify_password(user.password_hash, payload.password):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.auth_max_login_attempts:
            user.locked_until = now + timedelta(seconds=settings.auth_login_window_seconds)
            user.failed_login_count = 0
        record_audit(db, action="login", result=AuditResult.FAILURE, actor_user_id=user.id)
        db.commit()
        raise UnauthorizedError("Credenciais inválidas.")
    user.failed_login_count = 0
    user.locked_until = None
    record_audit(db, action="login", result=AuditResult.SUCCESS, actor_user_id=user.id)
    db.commit()
    token, session = create_session(db, user, settings)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.app_env != "local",
        samesite="lax",
    )
    return session_response(db, user, session)


@router.post("/logout", response_model=MessageResponse)
def logout(
    response: Response,
    current: tuple[UserSession, User] = Depends(get_current_session),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> MessageResponse:
    session, user = current
    session.revoked_at = utc_now()
    record_audit(db, action="logout", result=AuditResult.SUCCESS, actor_user_id=user.id)
    db.commit()
    response.delete_cookie(settings.session_cookie_name)
    return MessageResponse(message="Sessão encerrada.")


@router.get("/me", response_model=SessionResponse)
def me(
    current: tuple[UserSession, User] = Depends(get_current_session),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> SessionResponse:
    return session_response(db, current[1], current[0])


@router.post("/change-password", response_model=SessionResponse)
def change_password(
    payload: ChangePasswordRequest,
    current: tuple[UserSession, User] = Depends(get_current_session),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> SessionResponse:
    session, user = current
    if not verify_password(user.password_hash, payload.current_password):
        raise UnauthorizedError("Senha atual inválida.")
    try:
        user.password_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise ForbiddenError(str(exc)) from exc
    user.must_change_password = False
    record_audit(db, action="change_password", result=AuditResult.SUCCESS, actor_user_id=user.id)
    db.commit()
    return session_response(db, user, session)


@router.post("/select-organization/{organization_id}", response_model=SessionResponse)
def select_organization(
    organization_id: UUID,
    current: tuple[UserSession, User] = Depends(get_current_session),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> SessionResponse:
    session, user = current
    organization = db.get(Organization, organization_id)
    membership = db.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == user.id,
            Membership.is_active.is_(True),
        )
    )
    if not organization or (not membership and not user.is_platform_operator):
        raise ForbiddenError("Usuário não pode selecionar esta organização.")
    session.active_organization_id = organization_id
    db.commit()
    return session_response(db, user, session)

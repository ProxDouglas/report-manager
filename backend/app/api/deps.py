from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import hash_token
from app.db.enums import LicenseStatus, OrganizationStatus, Role
from app.db.models import License, Membership, Organization, User, UserSession
from app.db.session import get_db


@dataclass(frozen=True)
class RequestContext:
    db: Session
    user: User
    organization_value: Organization | None
    membership: Membership | None
    license: License | None
    session: UserSession
    correlation_id: str | None = None

    @property
    def organization(self) -> Organization:
        if not self.organization_value:
            raise ForbiddenError("Selecione uma organização válida.")
        return self.organization_value

    @property
    def role(self) -> Role | None:
        if self.user.is_platform_operator:
            return Role.PLATFORM_OPERATOR
        return self.membership.role if self.membership else None


def _session_token(request: Request) -> str | None:
    cookie_name = request.app.state.settings.session_cookie_name
    cookie_token = request.cookies.get(cookie_name)
    if cookie_token:
        return cookie_token
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def get_current_session(
    request: Request, db: Session = Depends(get_db)
) -> tuple[UserSession, User]:  # noqa: B008
    token = _session_token(request)
    if not token:
        raise UnauthorizedError()
    session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == hash_token(token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > datetime.now(UTC),
        )
    )
    if not session:
        raise UnauthorizedError("Sessão expirada ou inválida.")
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise UnauthorizedError("Sessão inválida.")
    return session, user


def get_current_user(current: tuple[UserSession, User] = Depends(get_current_session)) -> User:  # noqa: B008
    return current[1]


def get_context(
    request: Request,
    organization_header: str | None = Header(default=None, alias="X-Organization-Id"),
    current: tuple[UserSession, User] = Depends(get_current_session),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> RequestContext:
    session, user = current
    selected_id = organization_header or (
        str(session.active_organization_id) if session.active_organization_id else None
    )
    organization: Organization | None = None
    membership: Membership | None = None
    license: License | None = None

    if selected_id:
        try:
            parsed_id = UUID(selected_id)
        except ValueError as exc:
            raise ForbiddenError("Organização selecionada inválida.") from exc
        organization = db.get(Organization, parsed_id)
        if not organization or organization.status is OrganizationStatus.ARCHIVED:
            raise ForbiddenError("Organização indisponível.")
        membership = db.scalar(
            select(Membership).where(
                Membership.organization_id == organization.id,
                Membership.user_id == user.id,
                Membership.is_active.is_(True),
            )
        )
        if not membership and not user.is_platform_operator:
            raise ForbiddenError("Usuário não pertence à organização selecionada.")
        license = db.scalar(select(License).where(License.organization_id == organization.id))
    elif not user.is_platform_operator:
        membership = db.scalar(
            select(Membership)
            .where(Membership.user_id == user.id, Membership.is_active.is_(True))
            .limit(1)
        )
        if membership:
            organization = db.get(Organization, membership.organization_id)
            license = db.scalar(
                select(License).where(License.organization_id == membership.organization_id)
            )

    correlation_id = getattr(request.state, "correlation_id", None)
    if correlation_id:
        db.info["correlation_id"] = correlation_id
    return RequestContext(db, user, organization, membership, license, session, correlation_id)


def require_application_context(context: RequestContext = Depends(get_context)) -> RequestContext:  # noqa: B008
    if context.user.must_change_password:
        raise ForbiddenError("Altere a senha inicial antes de utilizar a plataforma.")
    if not context.organization_value or not context.license:
        raise ForbiddenError("Selecione uma organização válida.")
    today = date.today()
    license_is_current = (
        context.license.status is LicenseStatus.ACTIVE
        and context.license.starts_on <= today
        and (context.license.ends_on is None or context.license.ends_on >= today)
    )
    if not license_is_current:
        raise ForbiddenError("A licença da organização não está ativa.")
    return context


def require_platform_operator(context: RequestContext = Depends(get_context)) -> RequestContext:  # noqa: B008
    if not context.user.is_platform_operator:
        raise ForbiddenError("Ação restrita ao operador da plataforma.")
    return context


def require_roles(*roles: Role) -> Callable[..., RequestContext]:
    def dependency(
        context: RequestContext = Depends(require_application_context),
    ) -> RequestContext:
        if context.user.is_platform_operator:
            return context
        if not context.role or context.role not in roles:
            raise ForbiddenError("Usuário não possui a permissão necessária.")
        return context

    return dependency

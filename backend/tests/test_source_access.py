from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError
from app.db.enums import GrantTargetType, Role
from app.db.models import SourceGrant
from app.services.source_service import create_source_grant, ensure_source_access


def test_source_grants_allow_only_the_configured_scope(database: Session) -> None:
    from app.db.enums import OrganizationStatus, SourceStatus, SourceType
    from app.db.models import DataSource, Membership, Organization, User

    organization = Organization(
        name="Acme", slug=f"acme-{uuid4()}", status=OrganizationStatus.ACTIVE
    )
    owner = User(
        email=f"owner-{uuid4()}@example.com",
        display_name="Owner",
        password_hash="hash",
        must_change_password=False,
    )
    viewer = User(
        email=f"viewer-{uuid4()}@example.com",
        display_name="Viewer",
        password_hash="hash",
        must_change_password=False,
    )
    database.add_all([organization, owner, viewer])
    database.flush()
    source = DataSource(
        organization_id=organization.id,
        owner_user_id=owner.id,
        name="Fonte",
        source_type=SourceType.CSV,
        status=SourceStatus.ACTIVE,
    )
    database.add(source)
    database.add(
        Membership(
            organization_id=organization.id,
            user_id=viewer.id,
            role=Role.VIEWER,
        )
    )
    database.commit()

    with pytest.raises(ForbiddenError):
        ensure_source_access(database, source, viewer.id, Role.VIEWER, "VIEW")

    grant = create_source_grant(
        database,
        source,
        owner.id,
        GrantTargetType.USER,
        str(viewer.id),
        "USE",
    )
    assert grant.permission == "USE"
    ensure_source_access(database, source, viewer.id, Role.VIEWER, "VIEW")
    ensure_source_access(database, source, viewer.id, Role.VIEWER, "USE")
    with pytest.raises(ForbiddenError):
        ensure_source_access(database, source, viewer.id, Role.VIEWER, "MANAGE")

    grant.permission = "MANAGE"
    database.commit()
    ensure_source_access(database, source, viewer.id, Role.VIEWER, "MANAGE")
    ensure_source_access(database, source, viewer.id, Role.PLATFORM_OPERATOR, "MANAGE")
    assert database.scalar(select(SourceGrant).where(SourceGrant.id == grant.id))

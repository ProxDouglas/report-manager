"""Add source grants and worker readiness heartbeat."""

from alembic import op
import sqlalchemy as sa


revision = "0003_source_grants_hb"
down_revision = "0002_business_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # The initial migration uses Base.metadata.create_all, so these objects can
    # already exist in a fresh database. Keep this migration safe for both an
    # old database and a database created from the current metadata.
    if "source_grants" not in tables:
        op.create_table(
            "source_grants",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("data_source_id", sa.Uuid(), nullable=False),
            sa.Column("target_type", sa.String(length=12), nullable=False),
            sa.Column("target_id", sa.String(length=160), nullable=False),
            sa.Column("permission", sa.String(length=40), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "data_source_id", "target_type", "target_id", name="uq_source_grant_target"
            ),
        )

    source_indexes = {
        index["name"] for index in inspector.get_indexes("source_grants")
    }
    if "ix_source_grants_source_target" not in source_indexes:
        op.create_index(
            "ix_source_grants_source_target",
            "source_grants",
            ["data_source_id", "target_type", "target_id"],
        )

    if "worker_heartbeats" not in tables:
        op.create_table(
            "worker_heartbeats",
            sa.Column("worker_name", sa.String(length=120), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.PrimaryKeyConstraint("worker_name"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "worker_heartbeats" in tables:
        op.drop_table("worker_heartbeats")
    if "source_grants" in tables:
        source_indexes = {
            index["name"] for index in inspector.get_indexes("source_grants")
        }
        if "ix_source_grants_source_target" in source_indexes:
            op.drop_index("ix_source_grants_source_target", table_name="source_grants")
        op.drop_table("source_grants")

"""Align the source grant discriminator with the application enum length."""

from alembic import op
import sqlalchemy as sa


revision = "0004_source_grant_len"
down_revision = "0003_source_grants_hb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = sa.inspect(op.get_bind()).get_columns("source_grants")
    target_type = next(column for column in columns if column["name"] == "target_type")
    current_length = getattr(target_type["type"], "length", None)
    if current_length != 12:
        op.alter_column(
            "source_grants",
            "target_type",
            existing_type=sa.String(length=current_length),
            type_=sa.String(length=12),
            existing_nullable=False,
        )


def downgrade() -> None:
    columns = sa.inspect(op.get_bind()).get_columns("source_grants")
    target_type = next(column for column in columns if column["name"] == "target_type")
    current_length = getattr(target_type["type"], "length", None)
    if current_length != 40:
        op.alter_column(
            "source_grants",
            "target_type",
            existing_type=sa.String(length=current_length),
            type_=sa.String(length=40),
            existing_nullable=False,
        )

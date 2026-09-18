"""Add partial uniqueness constraints for active versions."""

from alembic import op
import sqlalchemy as sa


revision = "0002_business_constraints"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    source_indexes = {index["name"] for index in inspector.get_indexes("data_source_versions")}
    report_indexes = {index["name"] for index in inspector.get_indexes("report_versions")}

    if "uq_source_latest_valid" not in source_indexes:
        op.create_index(
            "uq_source_latest_valid",
            "data_source_versions",
            ["data_source_id"],
            unique=True,
            postgresql_where=sa.text("is_latest_valid = true"),
        )
    if "uq_report_published_version" not in report_indexes:
        op.create_index(
            "uq_report_published_version",
            "report_versions",
            ["report_id"],
            unique=True,
            postgresql_where=sa.text("status = 'PUBLICADO'"),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    report_indexes = {index["name"] for index in inspector.get_indexes("report_versions")}
    source_indexes = {index["name"] for index in inspector.get_indexes("data_source_versions")}
    if "uq_report_published_version" in report_indexes:
        op.drop_index("uq_report_published_version", table_name="report_versions")
    if "uq_source_latest_valid" in source_indexes:
        op.drop_index("uq_source_latest_valid", table_name="data_source_versions")

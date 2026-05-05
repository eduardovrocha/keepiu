"""Add is_admin to users and index on processing_stage

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_contents_processing_stage",
        "contents",
        ["processing_stage"],
    )


def downgrade() -> None:
    op.drop_index("ix_contents_processing_stage", table_name="contents")
    op.drop_column("users", "is_admin")

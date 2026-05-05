"""Add instagram_agent_processed flag to contents

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contents",
        sa.Column(
            "instagram_agent_processed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_contents_instagram_agent_processed",
        "contents",
        ["instagram_agent_processed"],
    )


def downgrade() -> None:
    op.drop_index("ix_contents_instagram_agent_processed", table_name="contents")
    op.drop_column("contents", "instagram_agent_processed")

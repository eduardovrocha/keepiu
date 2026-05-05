"""Add processing_stage to contents

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contents",
        sa.Column(
            "processing_stage",
            sa.String(50),
            nullable=True,
            server_default="queued",
        ),
    )


def downgrade() -> None:
    op.drop_column("contents", "processing_stage")

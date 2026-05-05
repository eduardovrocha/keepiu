"""Add last_reprocess_at to contents

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contents", sa.Column("last_reprocess_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("contents", "last_reprocess_at")

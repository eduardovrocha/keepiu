"""Add task_metrics table

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_metrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("task_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_task_metrics_task_name", "task_metrics", ["task_name"])
    op.create_index("ix_task_metrics_created_at", "task_metrics", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_task_metrics_created_at", table_name="task_metrics")
    op.drop_index("ix_task_metrics_task_name", table_name="task_metrics")
    op.drop_table("task_metrics")

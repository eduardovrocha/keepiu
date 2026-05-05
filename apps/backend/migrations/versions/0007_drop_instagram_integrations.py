"""Drop instagram_integrations table (OAuth integration removed)

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("instagram_integrations")


def downgrade() -> None:
    op.create_table(
        "instagram_integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("instagram_user_id", sa.String(100), nullable=False),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("token_expires_at", sa.DateTime, nullable=True),
        sa.Column("connected_at", sa.DateTime, nullable=False),
        sa.Column("last_used_at", sa.DateTime, nullable=True),
    )
    op.create_index(
        "ix_instagram_integrations_user_id",
        "instagram_integrations",
        ["user_id"],
    )

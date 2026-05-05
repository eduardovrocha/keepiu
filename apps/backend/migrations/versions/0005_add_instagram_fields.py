"""Add Instagram fields to contents and create instagram_integrations table

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen status column to accommodate 'needs_instagram_connection'
    op.alter_column(
        "contents", "status",
        type_=sa.String(50),
        existing_type=sa.String(20),
        nullable=False,
    )

    # Instagram-specific columns on contents
    op.add_column("contents", sa.Column("source_platform", sa.String(50), nullable=True))
    op.add_column("contents", sa.Column("external_id", sa.String(200), nullable=True))
    op.add_column("contents", sa.Column("caption", sa.Text, nullable=True))
    op.add_column("contents", sa.Column("tone", sa.String(100), nullable=True))
    op.add_column("contents", sa.Column("niche", sa.String(100), nullable=True))
    op.add_column("contents", sa.Column("cta", sa.String(500), nullable=True))
    op.add_column("contents", sa.Column("confidence_score_ocr", sa.Float, nullable=True))
    op.add_column("contents", sa.Column("language_detected", sa.String(20), nullable=True))
    op.add_column("contents", sa.Column("sentiment_score", sa.Float, nullable=True))

    op.create_index("ix_contents_source_platform", "contents", ["source_platform"])

    # Instagram OAuth integrations
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


def downgrade() -> None:
    op.drop_table("instagram_integrations")

    op.drop_index("ix_contents_source_platform", table_name="contents")
    op.drop_column("contents", "sentiment_score")
    op.drop_column("contents", "language_detected")
    op.drop_column("contents", "confidence_score_ocr")
    op.drop_column("contents", "cta")
    op.drop_column("contents", "niche")
    op.drop_column("contents", "tone")
    op.drop_column("contents", "caption")
    op.drop_column("contents", "external_id")
    op.drop_column("contents", "source_platform")

    op.alter_column(
        "contents", "status",
        type_=sa.String(20),
        existing_type=sa.String(50),
        nullable=False,
    )

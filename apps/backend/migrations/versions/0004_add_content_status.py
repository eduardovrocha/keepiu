"""add status, processing_started_at and processed_at to contents

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-03 00:03:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add status column — default 'queued' for all existing rows
    op.add_column(
        "contents",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="queued",
        ),
    )
    op.create_index("ix_contents_status", "contents", ["status"])

    # Add pipeline timestamps
    op.add_column(
        "contents",
        sa.Column("processing_started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "contents",
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )

    # Backfill: items already processed (processed=true) get status='completed'
    op.execute(
        """
        UPDATE contents
        SET status = 'completed',
            processed_at = updated_at
        WHERE processed = true
          AND (processing_error IS NULL OR processing_error = '')
        """
    )

    # Items with a processing_error that are marked processed → failed
    op.execute(
        """
        UPDATE contents
        SET status = 'failed'
        WHERE processed = true
          AND processing_error IS NOT NULL
          AND processing_error != ''
        """
    )


def downgrade() -> None:
    op.drop_index("ix_contents_status", table_name="contents")
    op.drop_column("contents", "status")
    op.drop_column("contents", "processing_started_at")
    op.drop_column("contents", "processed_at")

"""Add ingestion channel fields and whatsapp_phone to users

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── contents table ────────────────────────────────────────────────────────
    op.add_column("contents", sa.Column("ingestion_channel", sa.String(20), nullable=True))
    op.add_column("contents", sa.Column("external_message_id", sa.String(120), nullable=True))
    op.add_column("contents", sa.Column("external_user_id", sa.String(120), nullable=True))
    op.add_column("contents", sa.Column("sender_name", sa.String(255), nullable=True))

    op.create_index("ix_contents_ingestion_channel", "contents", ["ingestion_channel"])
    op.create_index("ix_contents_external_user_id", "contents", ["external_user_id"])

    # Backfill existing Telegram content
    op.execute("UPDATE contents SET ingestion_channel = 'telegram' WHERE ingestion_channel IS NULL")
    op.execute(
        "UPDATE contents SET external_message_id = telegram_message_id::text "
        "WHERE telegram_message_id IS NOT NULL AND external_message_id IS NULL"
    )

    # ── users table ───────────────────────────────────────────────────────────
    op.add_column("users", sa.Column("whatsapp_phone", sa.String(30), nullable=True))
    op.create_index("ix_users_whatsapp_phone", "users", ["whatsapp_phone"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_whatsapp_phone", table_name="users")
    op.drop_column("users", "whatsapp_phone")

    op.drop_index("ix_contents_external_user_id", table_name="contents")
    op.drop_index("ix_contents_ingestion_channel", table_name="contents")
    op.drop_column("contents", "sender_name")
    op.drop_column("contents", "external_user_id")
    op.drop_column("contents", "external_message_id")
    op.drop_column("contents", "ingestion_channel")

"""add system_settings table

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-03 00:02:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

# Keys seeded on creation; values are intentionally NULL until set via UI or env.
_SEED_KEYS = [
    ("telegram_bot_url", False),
    ("openai_api_key", True),
    ("telegram_bot_token", True),
    ("telegram_webhook_secret", True),
]


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_system_settings_key", "system_settings", ["key"])

    # Seed default keys with NULL values
    for key, is_secret in _SEED_KEYS:
        op.execute(
            f"INSERT INTO system_settings (key, is_secret) "
            f"VALUES ('{key}', {'true' if is_secret else 'false'}) "
            f"ON CONFLICT (key) DO NOTHING"
        )


def downgrade() -> None:
    op.drop_index("ix_system_settings_key", table_name="system_settings")
    op.drop_table("system_settings")

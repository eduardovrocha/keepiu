"""add HNSW vector index and created_at index

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-03 00:01:00.000000
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # HNSW index for fast approximate nearest-neighbour search on embeddings.
    # Requires pgvector >= 0.5.0 (shipped in pgvector/pgvector:pg16 image).
    # m=16, ef_construction=64 are sensible defaults for up to ~1M rows.
    op.execute(
        """
        CREATE INDEX content_embeddings_vector_hnsw_idx
        ON content_embeddings
        USING hnsw (vector vector_l2_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # Standard B-tree index to speed up ORDER BY created_at DESC queries
    # used in contents listing and dashboard stats.
    # Already created in 0001 but included here as guard for existing DBs
    # that were created before this migration series.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_contents_created_at
        ON contents (created_at)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS content_embeddings_vector_hnsw_idx")
    op.execute("DROP INDEX IF EXISTS ix_contents_created_at")

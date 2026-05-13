"""v021a corpus_chunks embedding vector(1024) + HNSW

Revision ID: c5f2154f8fb3
Revises: b1d742f07a46
Create Date: 2026-05-13 12:20:02.864898

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5f2154f8fb3'
down_revision: Union[str, Sequence[str], None] = 'b1d742f07a46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. pgvector extension must exist (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Convert the embedding column from ARRAY(Float) placeholder to vector(1024).
    # The USING clause casts existing rows (none in practice for a fresh DB) and
    # satisfies the type change for non-empty tables.
    op.execute(
        "ALTER TABLE corpus_chunks "
        "ALTER COLUMN embedding TYPE vector(1024) "
        "USING embedding::vector(1024);"
    )

    # 3. HNSW cosine index for semantic ANN (ADR-001).
    # m=16, ef_construction=64 are pgvector defaults — sufficient for ≤5k chunks.
    op.execute(
        "CREATE INDEX idx_corpus_chunks_hnsw ON corpus_chunks "
        "USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_corpus_chunks_hnsw;")
    # Revert embedding to ARRAY(Float) so Plan A's downgrade path stays clean.
    op.execute(
        "ALTER TABLE corpus_chunks "
        "ALTER COLUMN embedding TYPE float8[] "
        "USING embedding::float8[];"
    )

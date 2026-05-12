"""v021a corpus_chunks table

Revision ID: 0abf792e8ba7
Revises: 001
Create Date: 2026-05-13

corpus_chunks holds versioned scraped + redacted-internal corpus rows
backing Stream A (scrape) + Stream B (redaction) + Stream C (retrieval).
valid_from / valid_to range supports point-in-time queries (ADR-002).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0abf792e8ba7"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure pgvector extension is present (already enabled in v0.2.0a but idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "corpus_chunks",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source_id", sa.Text, nullable=False),
        sa.Column("source_type", sa.Text, nullable=False),
        sa.Column("section_path", sa.Text, nullable=False),
        sa.Column("citation", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("valid_to", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("embedding", sa.dialects.postgresql.ARRAY(sa.Float), nullable=True),  # placeholder; pgvector column added by Plan C
        sa.Column("metadata", sa.dialects.postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_index(
        "idx_corpus_chunks_current",
        "corpus_chunks",
        ["source_type", "source_id"],
        postgresql_where=sa.text("valid_to IS NULL"),
    )
    # GIN index for sparse retrieval (Postgres ts_rank_cd — see spec §6.0 naming note)
    op.execute(
        "CREATE INDEX idx_corpus_chunks_fulltext ON corpus_chunks "
        "USING GIN (to_tsvector('english', body));"
    )
    # HNSW index is added by Plan C (after embedding column is converted from ARRAY(Float) to vector(1024))


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_corpus_chunks_fulltext;")
    op.drop_index("idx_corpus_chunks_current", table_name="corpus_chunks")
    op.drop_table("corpus_chunks")

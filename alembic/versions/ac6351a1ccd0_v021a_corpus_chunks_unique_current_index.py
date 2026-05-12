"""v021a corpus_chunks unique current index

Revision ID: ac6351a1ccd0
Revises: bf24fe8528f5
Create Date: 2026-05-12

Defense-in-depth — adds a partial UNIQUE index enforcing the ADR-002 invariant:
at most one `valid_to IS NULL` row per (source_type, source_id, section_path).
Coexists with the non-unique `idx_corpus_chunks_current` index from Task 1 —
the old one helps query selection on the (source_type, source_id) prefix,
the new one enforces the invariant against concurrent upserts that could
otherwise both pass the existence check and both INSERT.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ac6351a1ccd0"
down_revision = "bf24fe8528f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX idx_corpus_chunks_unique_current "
        "ON corpus_chunks (source_type, source_id, section_path) "
        "WHERE valid_to IS NULL;"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_corpus_chunks_unique_current;")

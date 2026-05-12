"""v021a corpus_chunks check constraints

Revision ID: bf24fe8528f5
Revises: 0abf792e8ba7
Create Date: 2026-05-12

Defense-in-depth — adds CHECK constraints matching the patterns from 001_baseline.py
(matter.classification enum + lineage_event.this_hash regex). Catches application-bypass
writes (ad-hoc psql, external services not using the gateway models, SQL data fixes).
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "bf24fe8528f5"
down_revision = "0abf792e8ba7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_corpus_chunks_source_type",
        "corpus_chunks",
        "source_type IN ('ldc','ordinance','fl_ag_opinion','internal_opinion','procedure','calendar')",
    )
    op.create_check_constraint(
        "ck_corpus_chunks_sha256_hex",
        "corpus_chunks",
        "sha256 ~ '^[0-9a-f]{64}$'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_corpus_chunks_sha256_hex", "corpus_chunks", type_="check")
    op.drop_constraint("ck_corpus_chunks_source_type", "corpus_chunks", type_="check")

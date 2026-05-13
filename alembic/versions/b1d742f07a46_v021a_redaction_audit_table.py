"""v021a redaction_audit table

Revision ID: b1d742f07a46
Revises: ac6351a1ccd0
Create Date: 2026-05-13

redaction_audit: every detected redaction span gets one row. reviewer_upn=NULL
means pending review (per ADR-007). Only rows with reviewer_upn IS NOT NULL are
applied to corpus_chunks. FK to corpus_chunks(id) allows direct join from a
redacted chunk back to all spans contributing to it.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b1d742f07a46"
down_revision = "ac6351a1ccd0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "redaction_audit",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("source_doc_id", sa.Text, nullable=False),  # internal opinion identifier
        sa.Column(
            "chunk_id",
            sa.BigInteger,
            sa.ForeignKey("corpus_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),  # NULL until chunk is INSERTed post-review
        sa.Column("original_span_start", sa.Integer, nullable=False),
        sa.Column("original_span_end", sa.Integer, nullable=False),
        sa.Column("original_text", sa.Text, nullable=False),  # span content (encryption-at-rest optional v0.2.1b)
        sa.Column("redaction_reason", sa.Text, nullable=False),  # enum string per RedactionReason
        sa.Column("detector", sa.Text, nullable=False),  # "regex:ssn" | "llm:mxbai-chat" | "human"
        sa.Column("reviewer_upn", sa.Text, nullable=True),  # NULL = pending
        sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "idx_redaction_audit_pending",
        "redaction_audit",
        ["created_at"],
        postgresql_where=sa.text("reviewer_upn IS NULL"),
    )
    op.create_index(
        "idx_redaction_audit_source_doc",
        "redaction_audit",
        ["source_doc_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_redaction_audit_source_doc", table_name="redaction_audit")
    op.drop_index("idx_redaction_audit_pending", table_name="redaction_audit")
    op.drop_table("redaction_audit")

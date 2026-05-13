"""Apply approved redactions and ingest redacted chunks into corpus_chunks (source_type='internal_opinion')."""
from __future__ import annotations

import pytest

from services.redaction.ingest import apply_and_ingest


@pytest.fixture
async def fresh_db(db_pool):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE redaction_audit, corpus_chunks RESTART IDENTITY CASCADE"
        )
    return db_pool


@pytest.mark.integration
async def test_apply_redacts_only_approved_spans(fresh_db):
    text = "Hello John Smith aged 42 phone 941-555-0100 SSN 123-45-6789 end."
    # Pre-insert two audit rows; only one approved.
    async with fresh_db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO redaction_audit (source_doc_id, original_span_start, original_span_end,
                original_text, redaction_reason, detector, reviewer_upn, reviewed_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """,
            "doc-1", 6, 16, "John Smith", "pii_name", "llm:phi4", "reviewer@x",
        )
        await conn.execute(
            """
            INSERT INTO redaction_audit (source_doc_id, original_span_start, original_span_end,
                original_text, redaction_reason, detector, reviewer_upn)
            VALUES ($1, $2, $3, $4, $5, $6, NULL)
            """,
            "doc-1", 51, 62, "123-45-6789", "pii_ssn_or_id", "regex:ssn",
        )
        chunk_id = await apply_and_ingest(
            conn,
            source_doc_id="doc-1",
            original_text=text,
            section_path="Memorandum / Background",
            citation="Manatee County Attorney Opinion stub-doc-1 (2024)",
        )
        assert chunk_id is not None

        row = await conn.fetchrow("SELECT body, source_type FROM corpus_chunks WHERE id = $1", chunk_id)
    assert row["source_type"] == "internal_opinion"
    # John Smith redacted; SSN NOT redacted (not approved)
    assert "[REDACTED:pii_name]" in row["body"]
    assert "John Smith" not in row["body"]
    assert "123-45-6789" in row["body"]


@pytest.mark.integration
async def test_apply_with_no_approved_spans_still_creates_chunk(fresh_db):
    """If nothing is approved, original text is ingested verbatim — but with source_type='internal_opinion'."""
    async with fresh_db.acquire() as conn:
        chunk_id = await apply_and_ingest(
            conn, source_doc_id="doc-2", original_text="Clean text.",
            section_path="x", citation="x",
        )
        row = await conn.fetchrow("SELECT body FROM corpus_chunks WHERE id = $1", chunk_id)
    assert row["body"] == "Clean text."


@pytest.mark.integration
async def test_apply_links_redaction_audit_rows_to_chunk(fresh_db):
    """After ingest, approved audit rows should have chunk_id set."""
    text = "Hello John Smith end."
    async with fresh_db.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO redaction_audit (source_doc_id, original_span_start, original_span_end,
                original_text, redaction_reason, detector, reviewer_upn, reviewed_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """,
            "doc-3", 6, 16, "John Smith", "pii_name", "llm:phi4", "reviewer@x",
        )
        chunk_id = await apply_and_ingest(
            conn, source_doc_id="doc-3", original_text=text,
            section_path="x", citation="x",
        )
        row = await conn.fetchrow(
            "SELECT chunk_id FROM redaction_audit WHERE source_doc_id = 'doc-3' AND reviewer_upn IS NOT NULL"
        )
    assert row["chunk_id"] == chunk_id

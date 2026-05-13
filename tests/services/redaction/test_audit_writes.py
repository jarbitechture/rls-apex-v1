"""Audit-write logic: detected spans → redaction_audit rows with reviewer_upn=NULL."""
from __future__ import annotations

import pytest

from services.redaction.detectors.regex_detectors import DetectedSpan
from services.redaction.audit import write_pending_spans, approve_span, list_pending


@pytest.fixture
async def fresh_audit(db_pool):
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE redaction_audit RESTART IDENTITY CASCADE")
    return db_pool


@pytest.mark.integration
async def test_write_pending_spans_inserts_with_null_reviewer(fresh_audit):
    spans = [
        DetectedSpan(start=10, end=21, text="123-45-6789",
                     reason="pii_ssn_or_id", detector="regex:ssn"),
        DetectedSpan(start=30, end=44, text="(941) 555-0142",
                     reason="pii_contact", detector="regex:phone"),
    ]
    async with fresh_audit.acquire() as conn:
        inserted = await write_pending_spans(conn, source_doc_id="stub-x-1", spans=spans)
        assert inserted == 2
        rows = await conn.fetch("SELECT * FROM redaction_audit ORDER BY id")
    assert all(r["reviewer_upn"] is None for r in rows)
    assert all(r["chunk_id"] is None for r in rows)
    assert {r["redaction_reason"] for r in rows} == {"pii_ssn_or_id", "pii_contact"}


@pytest.mark.integration
async def test_approve_sets_reviewer_and_reviewed_at(fresh_audit):
    span = DetectedSpan(start=0, end=5, text="hello",
                        reason="other", detector="regex:test")
    async with fresh_audit.acquire() as conn:
        await write_pending_spans(conn, "doc-x", [span])
        pending_before = await list_pending(conn, source_doc_id="doc-x")
        assert len(pending_before) == 1

        await approve_span(conn, pending_before[0]["id"], reviewer_upn="reviewer@manatee.local")

        row = await conn.fetchrow("SELECT * FROM redaction_audit WHERE id = $1", pending_before[0]["id"])
    assert row["reviewer_upn"] == "reviewer@manatee.local"
    assert row["reviewed_at"] is not None


@pytest.mark.integration
async def test_list_pending_excludes_approved(fresh_audit):
    s1 = DetectedSpan(start=0, end=5, text="aaaaa", reason="other", detector="t")
    s2 = DetectedSpan(start=10, end=15, text="bbbbb", reason="other", detector="t")
    async with fresh_audit.acquire() as conn:
        await write_pending_spans(conn, "doc-x", [s1, s2])
        rows = await list_pending(conn, source_doc_id="doc-x")
        await approve_span(conn, rows[0]["id"], "r@x")
        remaining = await list_pending(conn, source_doc_id="doc-x")
    assert len(remaining) == 1

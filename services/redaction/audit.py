"""redaction_audit table operations: write pending spans, list, approve."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import asyncpg

from .detectors.regex_detectors import DetectedSpan


async def write_pending_spans(
    conn: asyncpg.Connection,
    source_doc_id: str,
    spans: Iterable[DetectedSpan],
) -> int:
    """Insert each span as a pending audit row. Returns count inserted."""
    spans = list(spans)
    if not spans:
        return 0
    await conn.executemany(
        """
        INSERT INTO redaction_audit (
            source_doc_id, original_span_start, original_span_end,
            original_text, redaction_reason, detector
        ) VALUES ($1, $2, $3, $4, $5, $6)
        """,
        [(source_doc_id, s.start, s.end, s.text, s.reason, s.detector) for s in spans],
    )
    return len(spans)


async def list_pending(
    conn: asyncpg.Connection,
    source_doc_id: str | None = None,
) -> list[dict]:
    """Return pending (reviewer_upn IS NULL) audit rows, optionally filtered by source_doc_id."""
    if source_doc_id is not None:
        rows = await conn.fetch(
            """
            SELECT id, source_doc_id, original_span_start, original_span_end,
                   original_text, redaction_reason, detector, created_at
            FROM redaction_audit
            WHERE reviewer_upn IS NULL AND source_doc_id = $1
            ORDER BY id
            """,
            source_doc_id,
        )
    else:
        rows = await conn.fetch(
            """
            SELECT id, source_doc_id, original_span_start, original_span_end,
                   original_text, redaction_reason, detector, created_at
            FROM redaction_audit
            WHERE reviewer_upn IS NULL
            ORDER BY id
            """
        )
    return [dict(r) for r in rows]


async def approve_span(
    conn: asyncpg.Connection,
    audit_id: int,
    reviewer_upn: str,
) -> None:
    """Mark an audit row as reviewed-and-approved."""
    await conn.execute(
        """
        UPDATE redaction_audit
        SET reviewer_upn = $1, reviewed_at = $2
        WHERE id = $3 AND reviewer_upn IS NULL
        """,
        reviewer_upn, datetime.now(timezone.utc), audit_id,
    )

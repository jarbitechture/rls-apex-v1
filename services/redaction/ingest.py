"""Apply approved redactions and ingest into corpus_chunks.

Per spec ADR-007 stage 4: spans with reviewer_upn IS NOT NULL are applied;
pending spans are left in audit and skipped. The redacted text is INSERTed
into corpus_chunks as source_type='internal_opinion'. The approved audit
rows are back-linked via chunk_id.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import asyncpg


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def apply_and_ingest(
    conn: asyncpg.Connection,
    source_doc_id: str,
    original_text: str,
    section_path: str,
    citation: str,
) -> int:
    """Apply approved spans to original_text and INSERT a corpus_chunks row.

    Returns the new chunk's id. Approved redaction_audit rows are back-linked
    via chunk_id. Steps 3+4 (INSERT + back-link UPDATE) execute inside a single
    transaction to prevent orphaned corpus_chunks rows if the back-link fails.
    """
    # 1. Fetch approved spans for this doc, sorted by start desc (splice from end → start)
    approved = await conn.fetch(
        """
        SELECT id, original_span_start, original_span_end, redaction_reason
        FROM redaction_audit
        WHERE source_doc_id = $1 AND reviewer_upn IS NOT NULL
        ORDER BY original_span_start DESC
        """,
        source_doc_id,
    )

    # 2. Splice in [REDACTED:<reason>] from end to start (preserves earlier offsets)
    redacted = original_text
    for r in approved:
        start = r["original_span_start"]
        end = r["original_span_end"]
        reason = r["redaction_reason"]
        redacted = redacted[:start] + f"[REDACTED:{reason}]" + redacted[end:]

    # 3+4. Transactional write: INSERT chunk then back-link audit rows atomically.
    # If the UPDATE fails the INSERT is rolled back — no orphaned corpus_chunks rows.
    async with conn.transaction():
        chunk_id = await conn.fetchval(
            """
            INSERT INTO corpus_chunks (
                source_id, source_type, section_path, citation, body, sha256, valid_from
            ) VALUES ($1, 'internal_opinion', $2, $3, $4, $5, $6)
            RETURNING id
            """,
            f"internal.opinion.{source_doc_id}",
            section_path,
            citation,
            redacted,
            _sha256(redacted),
            datetime.now(timezone.utc),
        )

        if approved:
            await conn.execute(
                "UPDATE redaction_audit SET chunk_id = $1 WHERE id = ANY($2)",
                chunk_id,
                [r["id"] for r in approved],
            )

    return chunk_id

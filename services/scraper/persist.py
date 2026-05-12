"""Versioned write to corpus_chunks. Per spec ADR-002:
- Same sha256 (already-current row): no-op.
- New sha256 for same source_id + source_type + section_path: set old row valid_to=NOW; insert new row valid_from=NOW.
- Initial insert: valid_from=NOW, valid_to=NULL.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import asyncpg

from .normalize import Chunk


async def upsert_chunks(conn: asyncpg.Connection, chunks: Iterable[Chunk]) -> dict:
    """Versioned upsert. Returns counts of {added, superseded, unchanged}.

    Wraps the entire batch in a transaction so that the UPDATE+INSERT pair in
    the supersede branch is atomic — concurrent readers never see zero current
    rows between the two statements, and a crash mid-batch can't leave an
    entity inconsistent.
    """
    added = superseded = unchanged = 0
    now = datetime.now(timezone.utc)  # batched-coherent timestamp for the whole call

    async with conn.transaction():
        for chunk in chunks:
            # Find current (valid_to IS NULL) row for this logical entity
            existing = await conn.fetchrow(
                """
                SELECT id, sha256
                FROM corpus_chunks
                WHERE source_id = $1 AND source_type = $2 AND section_path = $3 AND valid_to IS NULL
                """,
                chunk.source_id, chunk.source_type, chunk.section_path,
            )

            if existing is None:
                # Initial insert
                await conn.execute(
                    """
                    INSERT INTO corpus_chunks (
                        source_id, source_type, section_path, citation, body, sha256, valid_from
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    chunk.source_id, chunk.source_type, chunk.section_path,
                    chunk.citation, chunk.body, chunk.sha256, now,
                )
                added += 1
            elif existing["sha256"] == chunk.sha256:
                unchanged += 1
            else:
                # Supersede: close old row, insert new
                await conn.execute(
                    "UPDATE corpus_chunks SET valid_to = $1 WHERE id = $2",
                    now, existing["id"],
                )
                await conn.execute(
                    """
                    INSERT INTO corpus_chunks (
                        source_id, source_type, section_path, citation, body, sha256, valid_from
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    chunk.source_id, chunk.source_type, chunk.section_path,
                    chunk.citation, chunk.body, chunk.sha256, now,
                )
                superseded += 1

    return {"added": added, "superseded": superseded, "unchanged": unchanged}


async def query_at_time(
    conn: asyncpg.Connection,
    source_id: str,
    at: datetime,
    source_type: str | None = None,
) -> list[dict]:
    """Point-in-time query: return rows valid at the given moment.

    `source_type` is optional today (source_ids are namespaced), but the param
    future-proofs the signature so callers can scope queries when source_id
    collisions become possible across source families.
    """
    rows = await conn.fetch(
        """
        SELECT source_id, source_type, section_path, citation, body, sha256, valid_from, valid_to
        FROM corpus_chunks
        WHERE source_id = $1
          AND ($2::text IS NULL OR source_type = $2)
          AND valid_from <= $3
          AND (valid_to IS NULL OR valid_to > $3)
        ORDER BY section_path
        """,
        source_id, source_type, at,
    )
    return [dict(r) for r in rows]

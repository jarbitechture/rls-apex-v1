"""Versioned write logic — same sha256 is no-op; new sha256 supersedes; point-in-time query returns the right version."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from services.scraper.normalize import Chunk
from services.scraper.persist import upsert_chunks, query_at_time


@pytest.fixture
async def fresh_db(db_pool):
    """Acquire an asyncpg connection from the migrated db_pool; truncate corpus_chunks."""
    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE corpus_chunks")
        yield conn


@pytest.mark.asyncio
@pytest.mark.integration
async def test_same_sha256_is_noop(fresh_db):
    chunk = Chunk(body="t1", source_id="s1", source_type="ldc",
                  section_path="p1", citation="c1", sha256="a"*64)
    await upsert_chunks(fresh_db, [chunk])
    await upsert_chunks(fresh_db, [chunk])  # idempotent re-write
    rows = await fresh_db.fetch("SELECT COUNT(*) FROM corpus_chunks WHERE source_id = $1", "s1")
    assert rows[0]["count"] == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_new_sha256_supersedes_previous(fresh_db):
    old = Chunk(body="t1", source_id="s1", source_type="ldc",
                section_path="p1", citation="c1", sha256="a"*64)
    new = Chunk(body="t2", source_id="s1", source_type="ldc",
                section_path="p1", citation="c1", sha256="b"*64)
    await upsert_chunks(fresh_db, [old])
    await upsert_chunks(fresh_db, [new])
    rows = await fresh_db.fetch("SELECT sha256, valid_to FROM corpus_chunks WHERE source_id = $1 ORDER BY valid_from", "s1")
    assert len(rows) == 2
    assert rows[0]["sha256"] == "a"*64
    assert rows[0]["valid_to"] is not None  # superseded
    assert rows[1]["sha256"] == "b"*64
    assert rows[1]["valid_to"] is None      # current


@pytest.mark.asyncio
@pytest.mark.integration
async def test_point_in_time_query_returns_correct_version(fresh_db):
    # Write old chunk
    old = Chunk(body="t1", source_id="s1", source_type="ldc",
                section_path="p1", citation="c1", sha256="a"*64)
    await upsert_chunks(fresh_db, [old])
    # Capture anchor moment
    anchor = datetime.now(timezone.utc)
    # Write new chunk (supersedes)
    new = Chunk(body="t2", source_id="s1", source_type="ldc",
                section_path="p1", citation="c1", sha256="b"*64)
    await upsert_chunks(fresh_db, [new])
    # Query at the anchor moment should return the OLD chunk
    hits = await query_at_time(fresh_db, source_id="s1", at=anchor)
    assert len(hits) == 1
    assert hits[0]["sha256"] == "a"*64


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mixed_branches_in_one_call(fresh_db):
    """One upsert_chunks call mixing all 3 branches — assert counter dict."""
    # Seed: one existing row that will stay unchanged + one that will be superseded
    existing_unchanged = Chunk(body="x", source_id="s1", source_type="ldc",
                               section_path="p_unchanged", citation="c1", sha256="a"*64)
    existing_to_supersede = Chunk(body="old", source_id="s1", source_type="ldc",
                                  section_path="p_supersede", citation="c1", sha256="b"*64)
    await upsert_chunks(fresh_db, [existing_unchanged, existing_to_supersede])

    # Now upsert: the unchanged one (same sha), a new sha for the supersede entity,
    # and a brand-new entity
    brand_new = Chunk(body="new!", source_id="s1", source_type="ldc",
                      section_path="p_added", citation="c1", sha256="c"*64)
    new_sha_for_supersede = Chunk(body="new", source_id="s1", source_type="ldc",
                                  section_path="p_supersede", citation="c1", sha256="d"*64)
    result = await upsert_chunks(fresh_db, [existing_unchanged, new_sha_for_supersede, brand_new])
    assert result == {"added": 1, "superseded": 1, "unchanged": 1}, f"got: {result}"

"""Scrape orchestrator (Task 12) — mocks source modules, asserts upsert_chunks + ROI emit per source.

Strategy
--------
- Patch `services.scraper.service.importlib.import_module` so every source key
  resolves to a fake module whose `fetch_and_chunk` yields a deterministic
  pair of Chunks. Per-source resolution is by source-key, not real network.
- Patch `services.scraper.service._get_roi_client` to return a stub whose
  `emit_now` captures the event dict (sync, in-process). This avoids any
  asyncio.create_task wiring from the real RoiClient and keeps assertions on
  the dispatched event payload itself, which is what Rule #18 governs.
- Patch `services.scraper.service._maybe_connect` to return a fresh standalone
  asyncpg.Connection built from the `postgresql` fixture's `info`. The SUT
  calls `await conn.close()` in its `finally` block, so we must hand it a real
  connection (not a pool proxy) — closing a pool proxy aborts the pool's
  underlying socket.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from services.scraper.normalize import Chunk


@pytest.fixture
async def standalone_conn(db_pool, postgresql):
    """Fresh asyncpg.Connection on the migrated test DB. Safe for SUT to close()."""
    # db_pool dependency: ensures alembic migrations have run on this DB
    _ = db_pool
    conn = await asyncpg.connect(
        user=postgresql.info.user,
        password="",
        host=postgresql.info.host,
        port=postgresql.info.port,
        database=postgresql.info.dbname,
    )
    # Start each test from a clean corpus_chunks table — orchestrator's `added`
    # count is what we assert; pre-existing rows would skew it.
    await conn.execute("TRUNCATE corpus_chunks CASCADE")
    try:
        yield conn
    finally:
        if not conn.is_closed():
            await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_scrape_job_calls_upsert_and_emits_per_source(
    monkeypatch, standalone_conn
):
    """Each source's fetch_and_chunk → upsert_chunks → emit_now must fire.

    Asserts:
      - 5 ROI events emitted (one per source in SOURCES)
      - Every event satisfies the Rule #18 field contract
      - Aggregate `totals.added` ≥ 1 (the underlying upsert actually wrote rows)
      - `per_source` covers exactly the 5 SOURCES keys
    """
    from services.scraper import service as svc

    # ── 1. Fake module whose fetch_and_chunk yields 2 chunks ──────────────────
    # Each source uses a distinct source_id so the second source doesn't see
    # the first as already-inserted (which would shift added→unchanged).
    def make_fake_fetch(source_key: str):
        async def fake_fetch():
            yield Chunk(
                body=f"body-{source_key}-1",
                source_id=f"{source_key}.entity.1",
                source_type="ldc",
                section_path=f"{source_key}/p1",
                citation=f"{source_key} §1 (2024)",
                sha256=("a" * 63) + source_key[0],  # 64-char hex-ish unique-per-source
            )
            yield Chunk(
                body=f"body-{source_key}-2",
                source_id=f"{source_key}.entity.2",
                source_type="ldc",
                section_path=f"{source_key}/p2",
                citation=f"{source_key} §2 (2024)",
                sha256=("b" * 63) + source_key[0],
            )
        return fake_fetch

    def fake_import_module(dotted_path: str):
        # dotted_path looks like "services.scraper.sources.<source_key>"
        source_key = dotted_path.rsplit(".", 1)[-1]
        fake_module = MagicMock()
        fake_module.fetch_and_chunk = make_fake_fetch(source_key)
        return fake_module

    monkeypatch.setattr(
        "services.scraper.service.importlib.import_module", fake_import_module
    )

    # ── 2. Stub ROI client (sync emit_now capture) ────────────────────────────
    emit_calls: list[dict] = []
    fake_client = MagicMock()
    fake_client.emit_now = lambda evt: emit_calls.append(evt)
    monkeypatch.setattr(
        "services.scraper.service._get_roi_client", lambda: fake_client
    )

    # ── 3. Hand the SUT our standalone connection (it will close it) ──────────
    monkeypatch.setattr(
        "services.scraper.service._maybe_connect",
        AsyncMock(return_value=standalone_conn),
    )

    # ── 4. Run orchestrator ───────────────────────────────────────────────────
    result = await svc.run_scrape_job()

    # ── 5. ROI emit cardinality (one per source in SOURCES) ───────────────────
    assert len(emit_calls) == 5, f"expected 5 emits (one per source), got {len(emit_calls)}"

    # ── 6. Every event matches the Rule #18 contract ──────────────────────────
    sources_seen: set[str] = set()
    for evt in emit_calls:
        assert evt["event_kind"] == "tool_invocation"
        assert evt["workflow"]   == "rls_apex.scrape"
        assert evt["tool"]       == "rls_apex"
        assert evt["surface"]    == "other"
        assert evt["task_type"]  == "data_analysis"
        assert evt["user_id"]    == "system.scraper"
        assert evt["dept"]       == "system"
        assert evt["role_band"]  == "system"
        assert isinstance(evt["duration_s"], float)
        assert isinstance(evt["success"], bool)
        assert "extra" in evt and "source" in evt["extra"]
        sources_seen.add(evt["extra"]["source"])

    assert sources_seen == {
        "municode_ldc", "municode_ch2_26", "mymanatee_ldr",
        "mymanatee_calendar", "fl_ag_opinions",
    }, f"emits missing source coverage: {sources_seen}"

    # ── 7. Result aggregate ──────────────────────────────────────────────────
    assert result["status"] == "ok"
    assert result["totals"]["added"] >= 1, "upsert_chunks should have inserted rows"
    assert set(result["per_source"].keys()) == {
        "municode_ldc", "municode_ch2_26", "mymanatee_ldr",
        "mymanatee_calendar", "fl_ag_opinions",
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_run_scrape_job_isolates_per_source_failure(
    monkeypatch, standalone_conn
):
    """One source raising must not abort the run — other sources still emit
    + their ROI event records success=True, while the failing source records
    success=False with zeroed counts.
    """
    from services.scraper import service as svc

    failing_source = "mymanatee_ldr"

    async def good_fetch():
        yield Chunk(
            body="ok-body",
            source_id="ok.entity.1",
            source_type="ldc",
            section_path="ok/p1",
            citation="ok §1 (2024)",
            sha256="c" * 64,
        )

    async def boom_fetch():
        raise RuntimeError("simulated source outage")
        yield  # pragma: no cover  — keeps this an async generator

    def fake_import_module(dotted_path: str):
        source_key = dotted_path.rsplit(".", 1)[-1]
        fake_module = MagicMock()
        fake_module.fetch_and_chunk = boom_fetch if source_key == failing_source else good_fetch
        return fake_module

    monkeypatch.setattr(
        "services.scraper.service.importlib.import_module", fake_import_module
    )

    emit_calls: list[dict] = []
    fake_client = MagicMock()
    fake_client.emit_now = lambda evt: emit_calls.append(evt)
    monkeypatch.setattr(
        "services.scraper.service._get_roi_client", lambda: fake_client
    )
    monkeypatch.setattr(
        "services.scraper.service._maybe_connect",
        AsyncMock(return_value=standalone_conn),
    )

    result = await svc.run_scrape_job()

    # All 5 sources still got an emit
    assert len(emit_calls) == 5

    # The failing source's event is success=False with zeroed counts
    by_source = {evt["extra"]["source"]: evt for evt in emit_calls}
    assert by_source[failing_source]["success"] is False
    assert by_source[failing_source]["extra"]["added"] == 0
    assert by_source[failing_source]["extra"]["superseded"] == 0
    assert by_source[failing_source]["extra"]["unchanged"] == 0

    # At least one other source succeeded
    other_successes = [
        evt for src, evt in by_source.items()
        if src != failing_source and evt["success"] is True
    ]
    assert other_successes, "no source succeeded — fixture wired wrong?"

    # Aggregate reports per-source — failing source contributes 0 to totals
    assert result["per_source"][failing_source]["success"] is False
    assert result["status"] == "ok"

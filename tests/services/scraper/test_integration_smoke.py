"""Integration smoke for v0.2.1a Stream A — full pipeline against real fixtures.

Runs ``run_scrape_job`` with only the HTTP layer mocked (returns fixture HTML)
so the real source-module parsers, ``persist.upsert_chunks`` versioning, and
ROI emit all execute. This is one level above ``test_orchestrator.py``, which
mocks the source modules themselves; here every source module is exercised
end-to-end with its actual ``parse_*`` / ``chunk_html_section`` logic.

Strategy
--------
- Monkeypatch ``requests.get`` (every source imports ``requests`` then calls
  ``requests.get(...)`` at call time — verified, this attribute-swap is live).
  Match the URL by substring and return a fake response carrying real fixture
  bytes.
- Reuse the ``standalone_conn`` pattern from ``test_orchestrator.py``: a real
  asyncpg connection on the ephemeral test DB after alembic migrations, with
  ``corpus_chunks`` truncated. The SUT closes the connection itself.
- Stub ``_get_roi_client`` with a ``MagicMock`` whose ``emit_now`` captures
  events — avoids any httpx dispatch and lets us assert per-source cardinality.

Assertions
----------
- ``result["status"] == "ok"``
- All 5 sources appear in ``per_source``
- ``corpus_chunks`` has rows from at least: ``calendar`` (= 11 holidays, the
  one chunk-count we can verify deterministically from the fixture), ``ldc``,
  ``ordinance``, ``fl_ag_opinion``
- 5 ROI emits, one per source, ``success=True`` for at least the calendar
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest


FIXTURES = Path(__file__).parent / "fixtures"

# Each entry: substring that uniquely identifies a source's SEED_URL → fixture file.
# Verified against `grep SEED_URL services/scraper/sources/*.py` 2026-05-12.
_URL_TO_FIXTURE: dict[str, str] = {
    "code_of_ordinances":              "municode_ch2_26_section.html",
    "land_development_code":           "municode_ldc_section_6_4.html",
    "view-land-development-regulations": "mymanatee_ldr_page.html",
    "county_holidays":                 "mymanatee_calendar_2026.html",
    "myfloridalegal":                  "fl_ag_opinion_sample.html",
}


def _fake_response_for(url: str) -> MagicMock:
    """Build a fake ``requests.Response`` matching ``url`` to a fixture by substring."""
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status = MagicMock(return_value=None)
    response.encoding = "utf-8"

    for keyword, fixture_name in _URL_TO_FIXTURE.items():
        if keyword in url:
            response.text = (FIXTURES / fixture_name).read_text()
            return response

    # No matching fixture — return empty 200 so the source parses to zero chunks
    # rather than raising. Surfaces as 0 added in the per_source counters.
    response.text = "<html></html>"
    return response


@pytest.fixture
async def smoke_conn(db_pool, postgresql):
    """Fresh asyncpg.Connection on the migrated test DB, ``corpus_chunks`` truncated.

    Mirrors ``test_orchestrator.standalone_conn``. The SUT calls ``await
    conn.close()`` in its ``finally`` block, so we hand it a real standalone
    connection (not a pool proxy).
    """
    _ = db_pool  # ensure alembic migrations have run
    conn = await asyncpg.connect(
        user=postgresql.info.user,
        password="",
        host=postgresql.info.host,
        port=postgresql.info.port,
        database=postgresql.info.dbname,
    )
    await conn.execute("TRUNCATE corpus_chunks")
    try:
        yield conn
    finally:
        if not conn.is_closed():
            await conn.close()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_full_pipeline_against_real_fixtures(
    monkeypatch, smoke_conn, postgresql
):
    """End-to-end: fake HTTP → real source parsers → real persist → real corpus_chunks."""
    import requests

    from services.scraper import service as svc

    # ── 1. Mock the HTTP layer ──────────────────────────────────────────────
    def fake_get(url, **kwargs):  # signature matches requests.get(url, **kwargs)
        return _fake_response_for(url)

    monkeypatch.setattr(requests, "get", fake_get)

    # ── 2. Stub ROI client (avoid real httpx dispatch) ──────────────────────
    emit_calls: list[dict] = []
    fake_client = MagicMock()
    fake_client.emit_now = lambda evt: emit_calls.append(evt)
    monkeypatch.setattr(
        "services.scraper.service._get_roi_client", lambda: fake_client
    )

    # ── 3. Hand the SUT our standalone connection (it will close it) ────────
    monkeypatch.setattr(
        "services.scraper.service._maybe_connect",
        AsyncMock(return_value=smoke_conn),
    )

    # ── 4. Run the orchestrator end-to-end ──────────────────────────────────
    result = await svc.run_scrape_job()

    # ── 5. Aggregate shape ──────────────────────────────────────────────────
    assert result["status"] == "ok", f"orchestrator status: {result}"
    assert set(result["per_source"].keys()) == {
        "municode_ldc",
        "municode_ch2_26",
        "mymanatee_ldr",
        "mymanatee_calendar",
        "fl_ag_opinions",
    }

    # ── 6. ROI emit cardinality (Rule #18) ──────────────────────────────────
    assert len(emit_calls) == 5, f"expected 5 ROI emits, got {len(emit_calls)}"
    sources_seen = {evt["extra"]["source"] for evt in emit_calls}
    assert sources_seen == set(result["per_source"].keys())

    # ── 7. Real rows landed in corpus_chunks ────────────────────────────────
    # Open a separate verification connection — the SUT closed ``smoke_conn``.
    verify = await asyncpg.connect(
        user=postgresql.info.user,
        password="",
        host=postgresql.info.host,
        port=postgresql.info.port,
        database=postgresql.info.dbname,
    )
    try:
        rows = await verify.fetch(
            "SELECT source_type, COUNT(*) AS n FROM corpus_chunks GROUP BY source_type"
        )
    finally:
        await verify.close()

    by_type = {r["source_type"]: r["n"] for r in rows}

    # Deterministic: the calendar fixture has exactly 11 `holiday-date` spans
    # and the parser emits one chunk per holiday with source_type='calendar'.
    assert by_type.get("calendar", 0) == 11, (
        f"expected 11 calendar holidays, got by_type={by_type}, "
        f"per_source={result['per_source']}"
    )

    # Floor: at least one chunk from each of the other source_types.
    # (Exact paragraph counts depend on chunk_html_section's splitting, which
    #  test_normalize.py covers — here we only require non-empty.)
    for st in ("ldc", "ordinance", "fl_ag_opinion"):
        assert by_type.get(st, 0) >= 1, (
            f"expected >= 1 row of source_type={st!r}, got by_type={by_type}"
        )

    # ── 8. mymanatee_calendar emit must record success ──────────────────────
    # All 11 holidays share the same (source_id, source_type, section_path),
    # so persist.upsert_chunks supersedes the previous row on each insert:
    # the first holiday is `added`, the remaining 10 are `superseded`. The
    # invariant we assert is added + superseded == 11 (every holiday produced
    # one durable row in corpus_chunks — the 11 we counted at step 7).
    by_source = {evt["extra"]["source"]: evt for evt in emit_calls}
    cal_evt = by_source["mymanatee_calendar"]
    assert cal_evt["success"] is True
    assert cal_evt["extra"]["added"] + cal_evt["extra"]["superseded"] == 11, (
        f"calendar should have produced 11 row-writes total, got {cal_evt['extra']}"
    )

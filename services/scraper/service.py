"""Stream A scraper service. Exposes /health on port 30200 for W8 polling.

Scrape jobs are triggered by systemd timer (see scraper.timer); the FastAPI
app itself is long-running so /health is always reachable. /health returns
last-run-per-source (from corpus_chunks max(created_at)) + breaker_states
(from the per-host breaker registry). DB connection failures do not 500
the endpoint — the response is always 200 with `null` last-run values when
Postgres is unreachable, so W8 can distinguish "scraper alive, DB down" from
"scraper down".

run_scrape_job(): orchestrator invoked by the systemd-timer one-shot. Iterates
SOURCES, calls each source module's async fetch_and_chunk, persists via
persist.upsert_chunks, and emits one ROI tool_invocation event per source
(Operating Rule #18). Per-source failures are isolated — one source raising
does not abort the rest of the run. Telemetry is fire-and-forget
(RoiClient.emit_now); a failed dispatch never blocks the scrape.
"""
from __future__ import annotations

import importlib
import logging
import os
import time
from datetime import datetime, timezone

import asyncpg
from fastapi import FastAPI

from apps.gateway.sidecar._client import EVENT_KIND_TOOL_INVOCATION, RoiClient
from services.scraper.breaker import breaker_status_all
from services.scraper.config import SOURCES
from services.scraper.persist import upsert_chunks


logger = logging.getLogger("rls_apex.scraper")

app = FastAPI(title="rls-apex-scraper", version="0.2.1a")


# Maps the dotted source_id prefix written by source modules
# (e.g. "fl_ag.2020-09", "municode.ldc.26_05") to the SOURCES dict key
# used in last_run_per_source. The SQL-split shortcut in the plan body
# breaks for fl_ag (no second dot before the year), so the mapping is
# explicit here and the per-row classification happens in Python.
SOURCE_ID_PREFIX_TO_KEY: dict[str, str] = {
    "municode.ldc":       "municode_ldc",
    "municode.ch2_26":    "municode_ch2_26",
    "mymanatee.ldr":      "mymanatee_ldr",
    "mymanatee.calendar": "mymanatee_calendar",
    "fl_ag":              "fl_ag_opinions",
}


async def _maybe_connect() -> asyncpg.Connection | None:
    """Open an asyncpg connection from DB_* env vars; return None if not configured or unreachable.

    Repo convention uses DB_USER / DB_HOST / DB_PORT / DB_NAME / DB_PASSWORD
    (see tests/conftest.py and alembic.ini), not the single DATABASE_URL
    used by the plan body. Returning None on failure keeps /health a
    pure liveness probe.
    """
    try:
        return await asyncpg.connect(
            user=os.environ.get("DB_USER", "postgres"),
            password=os.environ.get("DB_PASSWORD", ""),
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "5432")),
            database=os.environ.get("DB_NAME", "rls_apex"),
        )
    except Exception:
        return None


@app.get("/health")
async def health() -> dict:
    """W8-pollable /health. Always returns 200 with the same shape."""
    last_run_per_source: dict[str, str | None] = {name: None for name in SOURCES}

    conn = await _maybe_connect()
    if conn is not None:
        try:
            rows = await conn.fetch(
                """
                SELECT source_id, MAX(created_at) AS last_run
                FROM corpus_chunks
                GROUP BY source_id
                """
            )
            for r in rows:
                sid = r["source_id"]
                # Find the longest matching prefix so e.g. "municode.ldc.26_05"
                # routes to municode_ldc rather than a bare "municode" key.
                matched_key: str | None = None
                matched_len = -1
                for prefix, key in SOURCE_ID_PREFIX_TO_KEY.items():
                    if sid.startswith(prefix) and len(prefix) > matched_len:
                        matched_key = key
                        matched_len = len(prefix)
                if matched_key is None or matched_key not in last_run_per_source:
                    continue
                last_run_ts = r["last_run"]
                if last_run_ts is None:
                    continue
                new_iso = last_run_ts.isoformat()
                existing = last_run_per_source[matched_key]
                # Keep the latest timestamp across all source_ids that share a prefix
                if existing is None or new_iso > existing:
                    last_run_per_source[matched_key] = new_iso
        except Exception:
            # Query-time failures (table missing, permission, etc.) must not 500.
            pass
        finally:
            await conn.close()

    return {
        "status": "healthy",
        "last_run_per_source": last_run_per_source,
        "breaker_states": breaker_status_all(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


# ─── Scrape job orchestrator (Task 12) ────────────────────────────────────────

# Module-level singleton — tests monkeypatch _get_roi_client to inject a fake.
_roi_client: RoiClient | None = None


def _get_roi_client() -> RoiClient:
    """Lazy-construct a RoiClient pointing at the configured sidecar endpoint.

    NOTE: the orchestrator is a systemd-timer one-shot, so we deliberately do
    NOT call start_drain_loop() here — fallback JSONL accumulates locally on
    the scraper host and the long-running gateway RoiClient drains it. Keeps
    the orchestrator's process lifetime bounded by the actual scrape work.
    """
    global _roi_client
    if _roi_client is None:
        endpoint = os.environ.get(
            "ROI_SIDECAR_ENDPOINT", "http://localhost:8001/events"
        )
        _roi_client = RoiClient(endpoint=endpoint)
    return _roi_client


# Source-key → dotted module path. Kept explicit so a typo in SOURCES doesn't
# silently route to a synthetic module path that imports fine but is wrong.
SOURCE_MODULES: dict[str, str] = {
    "municode_ldc":       "services.scraper.sources.municode_ldc",
    "municode_ch2_26":    "services.scraper.sources.municode_ch2_26",
    "mymanatee_ldr":      "services.scraper.sources.mymanatee_ldr",
    "mymanatee_calendar": "services.scraper.sources.mymanatee_calendar",
    "fl_ag_opinions":     "services.scraper.sources.fl_ag_opinions",
}


async def run_scrape_job() -> dict:
    """Run the full scrape pass across all 5 sources. Returns aggregate counters.

    Per-source ROI events are emitted via RoiClient.emit_now (fire-and-forget,
    Operating Rule #18). A failing source does not abort the run — its counts
    are zeroed and its ROI event records success=False.
    """
    conn = await _maybe_connect()
    if conn is None:
        logger.error("scraper aborting: DB unavailable")
        return {"status": "aborted", "reason": "db_unreachable"}

    client = _get_roi_client()
    totals = {"added": 0, "superseded": 0, "unchanged": 0}
    per_source: dict[str, dict] = {}

    try:
        for source_name in SOURCES:
            start_ts = time.monotonic()
            module_path = SOURCE_MODULES[source_name]
            try:
                module = importlib.import_module(module_path)
                chunks = []
                async for chunk in module.fetch_and_chunk():
                    chunks.append(chunk)
                result = await upsert_chunks(conn, chunks)
                success = True
            except Exception as exc:
                logger.exception("source %s failed: %s", source_name, exc)
                result = {"added": 0, "superseded": 0, "unchanged": 0}
                success = False

            duration = time.monotonic() - start_ts
            per_source[source_name] = {
                **result,
                "success": success,
                "duration_s": duration,
            }
            for k in totals:
                totals[k] += result.get(k, 0)

            # Fire-and-forget ROI emit per source (Rule #18 — never blocks).
            try:
                client.emit_now({
                    "event_kind": EVENT_KIND_TOOL_INVOCATION,
                    "workflow":   "rls_apex.scrape",
                    "tool":       "rls_apex",
                    "surface":    "other",
                    "task_type":  "data_analysis",
                    "user_id":    "system.scraper",
                    "dept":       "system",
                    "role_band":  "system",
                    "duration_s": duration,
                    "success":    success,
                    "extra":      {"source": source_name, **result},
                })
            except Exception as exc:  # belt-and-suspenders: never block on telemetry
                logger.debug("ROI emit failed for %s: %s", source_name, exc)
    finally:
        await conn.close()

    return {
        "status": "ok",
        "totals": totals,
        "per_source": per_source,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=30200, log_level="info")

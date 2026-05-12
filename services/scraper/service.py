"""Stream A scraper service. Exposes /health on port 30200 for W8 polling.

Scrape jobs are triggered by systemd timer (see scraper.timer); the FastAPI
app itself is long-running so /health is always reachable. /health returns
last-run-per-source (from corpus_chunks max(created_at)) + breaker_states
(from the per-host breaker registry). DB connection failures do not 500
the endpoint — the response is always 200 with `null` last-run values when
Postgres is unreachable, so W8 can distinguish "scraper alive, DB down" from
"scraper down".
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import asyncpg
from fastapi import FastAPI

from services.scraper.breaker import breaker_status_all
from services.scraper.config import SOURCES

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=30200, log_level="info")

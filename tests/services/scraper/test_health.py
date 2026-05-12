"""Stream A scraper /health endpoint — shape + source coverage.

The endpoint is a pure liveness probe: it never 500s even when Postgres
is unreachable. These tests don't depend on the db_pool fixture; they
exercise the ASGI app directly so the response shape is verified
independent of DB state.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from services.scraper.service import app


@pytest.mark.asyncio
async def test_health_returns_200_and_shape():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "last_run_per_source" in body
    assert "breaker_states" in body
    assert "checked_at" in body
    assert isinstance(body["last_run_per_source"], dict)
    assert isinstance(body["breaker_states"], dict)


@pytest.mark.asyncio
async def test_health_includes_all_5_sources():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/health")
    last_run = r.json()["last_run_per_source"]
    assert set(last_run.keys()) >= {
        "municode_ldc",
        "municode_ch2_26",
        "mymanatee_ldr",
        "mymanatee_calendar",
        "fl_ag_opinions",
    }

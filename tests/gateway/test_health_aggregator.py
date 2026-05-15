"""W8 — health_aggregator unit tests against mocked /health endpoints.

Uses patch.object(httpx.AsyncClient, "get", AsyncMock(side_effect=...))
because pytest-httpx is not installed (Override #1).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from apps.gateway.health_aggregator import (
    HealthAggregator,
    HealthSnapshot,
    TOOL_HEALTH_ENDPOINTS,
)


def _responder(url_to_result: dict) -> AsyncMock:
    """Build a per-URL mock for httpx.AsyncClient.get.

    url_to_result values:
      ("response", status_code, body_dict)  → return httpx.Response
      ("raise", exception_instance)         → raise the exception
    """
    async def _get(url, *args, **kwargs):
        kind, *rest = url_to_result[str(url)]
        if kind == "raise":
            raise rest[0]
        status, body = rest
        return httpx.Response(status, json=body)

    return AsyncMock(side_effect=_get)


@pytest.mark.asyncio
async def test_snapshot_starts_empty():
    """Before any poll, snapshot has empty tools dict and unknown status."""
    agg = HealthAggregator(endpoints=TOOL_HEALTH_ENDPOINTS, poll_interval_seconds=30)
    snap = agg.snapshot()
    assert isinstance(snap, HealthSnapshot)
    assert snap.tools == {}


@pytest.mark.asyncio
async def test_poll_once_records_all_endpoint_states():
    """9 endpoints polled — 1 with 503 makes overall_status degraded."""
    mapping: dict[str, tuple] = {}
    for name, url in TOOL_HEALTH_ENDPOINTS.items():
        if name == "embedding_service":
            mapping[url] = ("response", 503, {"status": "degraded", "breaker_state": "open"})
        else:
            mapping[url] = ("response", 200, {"status": "healthy"})

    agg = HealthAggregator(endpoints=TOOL_HEALTH_ENDPOINTS, poll_interval_seconds=30)
    with patch.object(httpx.AsyncClient, "get", _responder(mapping)):
        await agg.poll_once()

    snap = agg.snapshot()
    assert len(snap.tools) == len(TOOL_HEALTH_ENDPOINTS)
    assert snap.tools["embedding_service"]["status"] == "degraded"
    assert snap.tools["list_rls_precedents"]["status"] == "healthy"
    assert snap.overall_status == "degraded"


@pytest.mark.asyncio
async def test_poll_once_marks_unreachable_as_degraded():
    """ConnectError on one endpoint → that tool status=unreachable + overall degraded."""
    mapping: dict[str, tuple] = {}
    for name, url in TOOL_HEALTH_ENDPOINTS.items():
        if name == "scraper_service":
            mapping[url] = ("raise", httpx.ConnectError("connection refused"))
        else:
            mapping[url] = ("response", 200, {"status": "healthy"})

    agg = HealthAggregator(endpoints=TOOL_HEALTH_ENDPOINTS, poll_interval_seconds=30)
    with patch.object(httpx.AsyncClient, "get", _responder(mapping)):
        await agg.poll_once()

    snap = agg.snapshot()
    assert snap.tools["scraper_service"]["status"] == "unreachable"
    assert snap.overall_status == "degraded"


@pytest.mark.asyncio
async def test_all_healthy_yields_healthy_overall():
    """All 9 endpoints return 200 healthy → overall_status=healthy."""
    mapping = {url: ("response", 200, {"status": "healthy"}) for url in TOOL_HEALTH_ENDPOINTS.values()}

    agg = HealthAggregator(endpoints=TOOL_HEALTH_ENDPOINTS, poll_interval_seconds=30)
    with patch.object(httpx.AsyncClient, "get", _responder(mapping)):
        await agg.poll_once()

    snap = agg.snapshot()
    assert snap.overall_status == "healthy"
    assert len(snap.tools) == len(TOOL_HEALTH_ENDPOINTS)


@pytest.mark.asyncio
async def test_background_task_polls_repeatedly():
    """run_forever fires poll_once on each tick — at least 3 calls in 0.16s at 0.05s interval."""
    agg = HealthAggregator(endpoints=TOOL_HEALTH_ENDPOINTS, poll_interval_seconds=0.05)
    agg.poll_once = AsyncMock()
    task = asyncio.create_task(agg.run_forever())
    await asyncio.sleep(0.16)  # at least 3 ticks
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert agg.poll_once.call_count >= 3

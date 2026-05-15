"""W8 — degraded-path integration tests for GET /api/health/aggregated.

Tests the end-to-end path through the FastAPI endpoint via ASGITransport.
The lifespan does NOT run in ASGITransport context, so _health_aggregator is
None at module level. Each test:
  1. Constructs a real HealthAggregator.
  2. Patches httpx.AsyncClient.get to control what poll_once() records.
  3. Calls await agg.poll_once() while the httpx patch is active.
  4. Releases the httpx patch (important — avoids KeyError when the test
     client calls ac.get on the ASGI app over ASGITransport).
  5. Injects the aggregator via patch("apps.gateway.main._health_aggregator")
     so the endpoint handler reads it at request time.
  6. Fires the real HTTP request and asserts on status_code and body.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient, ASGITransport

from apps.gateway.main import app as gateway_app
from apps.gateway.health_aggregator import HealthAggregator, TOOL_HEALTH_ENDPOINTS


def _responder(url_to_result: dict) -> AsyncMock:
    """Build a per-URL mock for httpx.AsyncClient.get.

    Mirrors the helper shape from tests/gateway/test_health_aggregator.py.

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
async def test_one_unit_unreachable_yields_503():
    """One unit unreachable → 503 + that tool has status=='unreachable'.

    A still-healthy tool (list_rls_precedents) is asserted as 'healthy'.
    Target: check_urgency_rules raises ConnectError (still in 6-endpoint set).
    """
    mapping: dict[str, tuple] = {}
    for name, url in TOOL_HEALTH_ENDPOINTS.items():
        if name == "check_urgency_rules":
            mapping[url] = ("raise", httpx.ConnectError("connection refused"))
        else:
            mapping[url] = ("response", 200, {"status": "healthy"})

    agg = HealthAggregator(endpoints=TOOL_HEALTH_ENDPOINTS, poll_interval_seconds=30)
    with patch.object(httpx.AsyncClient, "get", _responder(mapping)):
        await agg.poll_once()
    # httpx patch released here — test client routes through ASGITransport normally

    with patch("apps.gateway.main._health_aggregator", agg):
        async with AsyncClient(
            transport=ASGITransport(app=gateway_app), base_url="http://test"
        ) as ac:
            r = await ac.get("/api/health/aggregated")

    assert r.status_code == 503
    body = r.json()
    assert body["tools"]["check_urgency_rules"]["status"] == "unreachable"
    assert body["tools"]["list_rls_precedents"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_all_healthy_yields_200():
    """All units healthy → 200 + status=='healthy'."""
    mapping = {
        url: ("response", 200, {"status": "healthy"})
        for url in TOOL_HEALTH_ENDPOINTS.values()
    }

    agg = HealthAggregator(endpoints=TOOL_HEALTH_ENDPOINTS, poll_interval_seconds=30)
    with patch.object(httpx.AsyncClient, "get", _responder(mapping)):
        await agg.poll_once()

    with patch("apps.gateway.main._health_aggregator", agg):
        async with AsyncClient(
            transport=ASGITransport(app=gateway_app), base_url="http://test"
        ) as ac:
            r = await ac.get("/api/health/aggregated")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"


@pytest.mark.asyncio
async def test_embedding_service_breaker_open_surfaced():
    """embedding_service returns 503 with breaker_state='open' → 503 + breaker_state preserved."""
    mapping: dict[str, tuple] = {}
    for name, url in TOOL_HEALTH_ENDPOINTS.items():
        if name == "embedding_service":
            mapping[url] = (
                "response",
                503,
                {"status": "degraded", "breaker_state": "open"},
            )
        else:
            mapping[url] = ("response", 200, {"status": "healthy"})

    agg = HealthAggregator(endpoints=TOOL_HEALTH_ENDPOINTS, poll_interval_seconds=30)
    with patch.object(httpx.AsyncClient, "get", _responder(mapping)):
        await agg.poll_once()

    with patch("apps.gateway.main._health_aggregator", agg):
        async with AsyncClient(
            transport=ASGITransport(app=gateway_app), base_url="http://test"
        ) as ac:
            r = await ac.get("/api/health/aggregated")

    assert r.status_code == 503
    body = r.json()
    assert body["tools"]["embedding_service"]["breaker_state"] == "open"
    assert body["tools"]["embedding_service"]["status"] == "degraded"

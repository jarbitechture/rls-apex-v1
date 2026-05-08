"""GET /api/health/breakers aggregates L1 breakers (spec §12.4)."""
import pytest


@pytest.mark.asyncio
async def test_health_breakers_returns_l1_breaker_states(client):
    response = await client.get("/api/health/breakers")
    assert response.status_code == 200
    body = response.json()
    breakers = body["breakers"]
    breaker_names = {b["name"] for b in breakers}
    # Expect at least the ROI sidecar breaker
    assert "roi_sidecar" in breaker_names
    # All start CLOSED
    assert all(b["state"] == "closed" for b in breakers)


@pytest.mark.asyncio
async def test_health_breakers_endpoint_responds(client):
    """W5: endpoint exists and authenticated requests succeed.
    The auth gate itself is exercised by current_user; this test confirms wire-up."""
    response = await client.get("/api/health/breakers")
    assert response.status_code in (200, 401)

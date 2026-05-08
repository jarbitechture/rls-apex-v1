"""GET /api/cao/brief — canned brief for v0.2.0b CAO view."""
from __future__ import annotations

import pytest

from apps.gateway.sidecar._client import validate_event_for_persistence


@pytest.fixture
def capture_emit_roi(monkeypatch):
    captured: list[dict] = []
    def _fake(event): captured.append(event)
    import apps.gateway.main as gw
    monkeypatch.setattr(gw, "emit_roi", _fake)
    return captured


@pytest.mark.asyncio
async def test_cao_brief_returns_canned_shape(client, capture_emit_roi):
    r = await client.get("/api/cao/brief?rlsId=RLS-25-067")
    assert r.status_code == 200
    body = r.json()
    assert body["rlsId"] == "RLS-25-067"
    assert isinstance(body["summary"], list) and len(body["summary"]) >= 3
    assert isinstance(body["keyFacts"], list)
    assert "risk" in body
    assert isinstance(body["suggestedNextSteps"], list)


@pytest.mark.asyncio
async def test_cao_brief_emits_roi_event(client, capture_emit_roi):
    r = await client.get("/api/cao/brief?rlsId=RLS-25-067")
    assert r.status_code == 200
    assert len(capture_emit_roi) == 1
    event = capture_emit_roi[0]
    validate_event_for_persistence(event)
    assert event["workflow"] == "rls_apex.cao_brief"
    assert event["tool"] == "rls_apex"

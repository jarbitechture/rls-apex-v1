"""ROI sidecar endpoint-contract guard (found by #52 spec-miner, 2026-05-18).

Contract: a caller passes the sidecar BASE URL; RoiClient appends `/v1/events`
(apps/gateway/sidecar/_client.py: `self.endpoint = endpoint.rstrip("/")`,
then `POST f"{self.endpoint}/v1/events"`). The gateway and mcp_tools honor
this (ROI_EVENTS_URL default has no path). The redaction + scraper services
defaulted to a `/events`-suffixed URL -> POSTed to `…/events/v1/events`
(404), silently masked by the breaker's JSONL fallback (Rule #18 telemetry
loss in prod).

No tests/services/__init__.py — rootdir-based pytest collection
(reference_rls_apex_pytest_discovery).
"""
from __future__ import annotations

import importlib

import pytest

# (module, singleton-global name) for every service that builds its own RoiClient.
_SERVICES = [
    ("services.redaction.pipeline", "_roi_client"),
    ("services.scraper.service", "_roi_client"),
]


class _NoFsQueue:
    """Stub _FallbackQueue: skip the privileged /var/log mkdir that fires on
    RoiClient construction (unrelated to the endpoint contract under test)."""

    def __init__(self, path: object) -> None:
        self.path = path


@pytest.mark.parametrize("modname,global_name", _SERVICES)
def test_default_roi_endpoint_does_not_double_append_events(
    monkeypatch: pytest.MonkeyPatch, modname: str, global_name: str
) -> None:
    monkeypatch.setattr(
        "apps.gateway.sidecar._client._FallbackQueue", _NoFsQueue
    )
    monkeypatch.delenv("ROI_SIDECAR_ENDPOINT", raising=False)
    mod = importlib.import_module(modname)
    setattr(mod, global_name, None)  # reset the lazy singleton
    client = mod._get_roi_client()

    # The base must NOT carry the path the client itself appends.
    assert not client.endpoint.endswith("/events"), (
        f"{modname} default endpoint {client.endpoint!r} carries '/events'; "
        "RoiClient appends '/v1/events' -> POST to /events/v1/events (404)"
    )
    # Effective POST target is exactly one versioned path segment.
    assert f"{client.endpoint}/v1/events" == "http://localhost:8001/v1/events"

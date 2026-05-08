"""TDD — Task 1: emit_roi call sites produce events that pass validate_event_for_persistence.

These tests monkeypatch `apps.gateway.main.emit_roi` to capture the dict passed by
/api/intake and /api/validate, then assert each captured event passes the pre-flight
schema validation.  They fail RED against the current call sites (missing workflow,
dept, role_band, task_type; invalid tool value) and turn GREEN once those call sites
are corrected.
"""
from __future__ import annotations

import pytest

from apps.gateway.sidecar._client import validate_event_for_persistence


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def capture_emit(monkeypatch):
    """Monkeypatch emit_roi and return a list that collects every dict passed to it."""
    calls: list[dict] = []

    def _fake_emit(event: dict) -> None:
        calls.append(event)

    import apps.gateway.main as _main
    monkeypatch.setattr(_main, "emit_roi", _fake_emit)
    return calls


# ─── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_intake_emits_persistable_event(client, capture_emit):
    """Verify the dict that /api/intake passes to emit_roi is a valid persistable event.

    This test patches emit_roi and validates the captured dict against
    validate_event_for_persistence directly. It does NOT exercise the async
    _dispatch path or the JSONL fallback queue — those are covered by
    tests/test_roi_emit_e2e.py and tests/test_sidecar_uses_shared_breaker.py.
    """
    response = await client.post("/api/intake", json={"text": "permit denial"})
    assert response.status_code == 200, response.text

    assert capture_emit, "emit_roi was never called by /api/intake"
    event = capture_emit[0]

    validate_event_for_persistence(event)

    # Field-level assertions for telemetry contract
    assert event["tool"] == "rls_apex", f"expected tool=rls_apex, got {event['tool']!r}"
    assert event["workflow"] == "rls_apex.intake", f"expected workflow=rls_apex.intake, got {event['workflow']!r}"
    assert event["task_type"] == "data_analysis", f"expected task_type=data_analysis, got {event['task_type']!r}"
    assert event["dept"] == "DEV", f"expected dept=DEV, got {event['dept']!r}"
    assert event["role_band"] == "professional", f"expected role_band=professional, got {event['role_band']!r}"


@pytest.mark.asyncio
async def test_validate_emits_persistable_event(client, capture_emit):
    """Verify the dict that /api/validate passes to emit_roi is a valid persistable event.

    This test patches emit_roi and validates the captured dict against
    validate_event_for_persistence directly. It does NOT exercise the async
    _dispatch path or the JSONL fallback queue — those are covered by
    tests/test_roi_emit_e2e.py and tests/test_sidecar_uses_shared_breaker.py.

    Also asserts that blocking_count lives under `extra`, not as a top-level key
    (top-level blocking_count violates additionalProperties: false).
    """
    payload = {
        "rlsPayload": {
            "type": "Advisory",
            "title": "Test RLS",
            "department": "County Attorney",
        }
    }
    response = await client.post("/api/validate", json=payload)
    assert response.status_code == 200, response.text

    assert capture_emit, "emit_roi was never called by /api/validate"
    event = capture_emit[0]

    validate_event_for_persistence(event)

    assert event["tool"] == "rls_apex", f"expected tool=rls_apex, got {event['tool']!r}"
    assert event["workflow"] == "rls_apex.validate", f"expected workflow=rls_apex.validate, got {event['workflow']!r}"
    assert event["task_type"] == "validation", f"expected task_type=validation, got {event['task_type']!r}"
    assert event["dept"] == "DEV", f"expected dept=DEV, got {event['dept']!r}"
    assert event["role_band"] == "professional", f"expected role_band=professional, got {event['role_band']!r}"

    # blocking_count must NOT be a top-level key (additionalProperties: false)
    assert "blocking_count" not in event, (
        "blocking_count must be nested under event['extra'], not a top-level field"
    )
    # It must be present under extra
    assert "extra" in event, "event must have an 'extra' key"
    assert "blocking_count" in event["extra"], (
        f"blocking_count must be in event['extra']; got extra={event['extra']!r}"
    )

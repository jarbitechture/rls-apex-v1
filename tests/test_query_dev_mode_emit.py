"""Task 6 — /api/query DEV_MODE path must emit a ROI event after stream close.

Verifies Operating Rule #18 compliance for the query endpoint. The emit must:
- Fire after the SSE stream is exhausted (not before).
- Include all 8 required schema fields (event_kind, workflow, user_id, dept,
  role_band, task_type, tool, success).
- Use tool='rls_apex', workflow='rls_apex.query', success=True on happy path.
- Never block the streaming response.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

import apps.gateway.main as gateway_main
from apps.gateway.sidecar._client import validate_event_for_persistence


@pytest.mark.asyncio
async def test_query_dev_mode_emits_valid_roi_event(client) -> None:
    """DEV_MODE /api/query emits a compliant ROI event after stream exhaustion."""
    captured: list[dict] = []

    def _fake_emit_roi(event: dict) -> None:
        captured.append(event)

    with (
        patch.object(gateway_main, "DEV_MODE", True),
        patch.object(gateway_main, "emit_roi", _fake_emit_roi),
    ):
        response = await client.post(
            "/api/query",
            json={"q": "What are the procurement rules for contracts over $50k?"},
        )

    # Stream consumed fully — response should be 200 with SSE content-type
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    # ROI event must have been emitted exactly once
    assert len(captured) == 1, (
        f"Expected 1 ROI event, got {len(captured)}: {captured!r}"
    )
    event = captured[0]

    # Must pass the pre-flight schema validator
    validate_event_for_persistence(event)

    # Field value assertions per ADR-001 + ADR-003
    assert event["tool"] == "rls_apex", f"tool must be 'rls_apex', got {event['tool']!r}"
    assert event["workflow"] == "rls_apex.query", (
        f"workflow must be 'rls_apex.query', got {event['workflow']!r}"
    )
    assert event["event_kind"] == "tool_invocation", (
        f"event_kind must be 'tool_invocation', got {event['event_kind']!r}"
    )
    assert event["success"] is True, "success must be True on happy path"
    assert event["user_id"] == "test@local", (
        f"user_id must match fixture UPN, got {event['user_id']!r}"
    )

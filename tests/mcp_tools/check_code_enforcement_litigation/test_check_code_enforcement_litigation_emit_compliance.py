"""E1 — check_code_enforcement_litigation emit shapes validated against ROI schema.

These tests patch server.roi.emit at the instance level (bypassing the emitter's
internal validate_event_for_persistence call) to independently verify that the
server's payload construction produces a schema-compliant event.

L1 has no DB dependency — no @pytest.mark.integration needed.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.gateway.sidecar._client import validate_event_for_persistence
import mcp_tools.check_code_enforcement_litigation.server as server


def _make_actor(actor_id: str = "tester@manatee.local") -> MagicMock:
    actor = MagicMock()
    actor.actor_id = actor_id
    return actor


# ---------------------------------------------------------------------------
# Test 1: applicable=True success path — valid NOV date present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l1_emit_success_passes_schema():
    """Applicable CE case with a valid NOV date: emit payload must pass ROI schema."""
    actor = _make_actor()
    captured: list[dict] = []

    async def capture(event_kind: str, payload: dict) -> None:
        captured.append({"event_kind": event_kind, **payload})

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock(side_effect=capture)),
    ):
        result = await server.check_code_enforcement_litigation(
            rls_payload={
                "factualBackground": "NOV-2026-117 dated 2026-01-15 was issued.",
            },
            matter_type="code_enforcement_litigation",
        )

    assert result["applicable"] is True
    assert len(captured) == 1, f"Expected 1 ROI event, got {len(captured)}"
    event = captured[0]

    # Core E1 assertion — must not raise.
    validate_event_for_persistence(event)

    assert event["success"] is True
    assert event["event_kind"] == "tool_invocation"


# ---------------------------------------------------------------------------
# Test 2: applicable=False path — non-CE matter_type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_l1_emit_non_applicable_passes_schema():
    """Non-CE matter_type (applicable=False path): emit payload must pass ROI schema."""
    actor = _make_actor()
    captured: list[dict] = []

    async def capture(event_kind: str, payload: dict) -> None:
        captured.append({"event_kind": event_kind, **payload})

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock(side_effect=capture)),
    ):
        result = await server.check_code_enforcement_litigation(
            rls_payload={"factualBackground": "routine variance request"},
            matter_type="permit_or_zoning",
        )

    assert result["applicable"] is False
    assert len(captured) == 1, f"Expected 1 ROI event, got {len(captured)}"
    event = captured[0]

    # Core E1 assertion — must not raise.
    validate_event_for_persistence(event)

    assert event["success"] is True
    assert event["event_kind"] == "tool_invocation"
    assert event.get("extra", {}).get("applicable") is False

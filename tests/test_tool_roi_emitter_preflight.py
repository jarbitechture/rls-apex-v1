"""W1 — ToolRoiEmitter must validate events pre-flight and stop adding non-schema fields."""
from __future__ import annotations

import pytest

from mcp_tools._lib.roi_emit import ToolRoiEmitter


@pytest.mark.asyncio
async def test_emitter_rejects_event_missing_required_fields():
    """Pre-flight guard raises ValueError when emitting an event lacking required schema fields."""
    emitter = ToolRoiEmitter(tool_name="classify_matter")
    incomplete_payload = {"actor_id": "test@manatee.local"}
    with pytest.raises(ValueError, match="missing required fields"):
        await emitter.emit("tool_invocation", incomplete_payload)


@pytest.mark.asyncio
async def test_emitter_does_not_add_ts_field(monkeypatch):
    """Schema additionalProperties: false rejects 'ts'; emitter must not add it."""
    captured: list[dict] = []

    async def _fake_post(self, event):
        captured.append(event)

    monkeypatch.setattr(ToolRoiEmitter, "_post", _fake_post)
    emitter = ToolRoiEmitter(tool_name="classify_matter")
    full_payload = {
        "workflow": "rls_apex.mcp.classify_matter",
        "user_id": "test@manatee.local",
        "dept": "DEV",
        "role_band": "professional",
        "task_type": "data_analysis",
        "tool": "rls_apex",
        "success": True,
    }
    await emitter.emit("tool_invocation", full_payload)
    assert captured, "emit() did not call _post"
    assert "ts" not in captured[0], f"emitter still adds 'ts': {captured[0]!r}"

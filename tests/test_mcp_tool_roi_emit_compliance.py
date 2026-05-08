"""W5 — Parametrized compliance: every MCP tool must emit a fully-valid ROI event.

Tests cover the happy path (success=True) and the error path (success=False) for
each of the three MCP tool servers. Each tool must include all 8 required keys
(event_kind, workflow, user_id, dept, role_band, task_type, tool, success) with
correct values per ADR-001 (Option C) and ADR-003.

These tests start RED (Tasks 3-5 turn them GREEN one tool at a time).
"""
from __future__ import annotations

import importlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.gateway.sidecar._client import validate_event_for_persistence
from mcp_tools._lib.roi_emit import ToolRoiEmitter

# (module_path, helper_name, tool_name, sample_input, expected_workflow)
_TOOL_CASES = [
    (
        "mcp_tools.classify_matter.server",
        "classify_text",
        "classify_matter",
        "Need legal review on a permit denial",
        "rls_apex.mcp.classify_matter",
    ),
    (
        "mcp_tools.validate_rls_structure.server",
        "validate_dict",
        "validate_rls_structure",
        {"type": "Advisory", "title": "Test", "department": "County Attorney"},
        "rls_apex.mcp.validate_rls_structure",
    ),
    (
        "mcp_tools.extract_fields.server",
        "extract_text",
        "extract_fields",
        "Need legal review on parcel 12345",
        "rls_apex.mcp.extract_fields",
    ),
]


def _make_actor(actor_id: str = "test@manatee.local") -> MagicMock:
    actor = MagicMock()
    actor.actor_id = actor_id
    return actor


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module_path,helper_name,tool_name,sample_input,expected_workflow",
    _TOOL_CASES,
    ids=[c[2] for c in _TOOL_CASES],
)
async def test_tool_emits_valid_roi_event_on_success(
    module_path: str,
    helper_name: str,
    tool_name: str,
    sample_input: Any,
    expected_workflow: str,
) -> None:
    """Happy path: tool emits a fully-valid ROI event when invocation succeeds."""
    mod = importlib.import_module(module_path)
    tool_fn = getattr(mod, tool_name)

    captured: list[dict] = []

    async def _fake_emit(self, event_kind: str, payload: dict) -> None:  # noqa: ARG001
        full_event = {"event_kind": event_kind, **payload}
        captured.append(full_event)

    actor = _make_actor()

    with (
        patch.object(ToolRoiEmitter, "emit", _fake_emit),
        patch(f"{module_path}.require_actor", return_value=actor),
    ):
        if isinstance(sample_input, str):
            await tool_fn(sample_input)
        else:
            await tool_fn(sample_input)

    assert captured, f"{tool_name}: no ROI event emitted on success"
    event = captured[0]

    # Must pass the pre-flight validator
    validate_event_for_persistence(event)

    # Specific field assertions per ADR-001 + ADR-003
    assert event["tool"] == "rls_apex", (
        f"{tool_name}: event['tool'] must be 'rls_apex', got {event['tool']!r}"
    )
    assert event["workflow"] == expected_workflow, (
        f"{tool_name}: workflow mismatch: {event['workflow']!r} != {expected_workflow!r}"
    )
    assert event["user_id"] == actor.actor_id, (
        f"{tool_name}: user_id must be actor.actor_id"
    )
    assert event["success"] is True, f"{tool_name}: success must be True on happy path"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module_path,helper_name,tool_name,sample_input,expected_workflow",
    _TOOL_CASES,
    ids=[c[2] for c in _TOOL_CASES],
)
async def test_tool_emits_valid_roi_event_on_exception(
    module_path: str,
    helper_name: str,
    tool_name: str,
    sample_input: Any,
    expected_workflow: str,
) -> None:
    """Error path (W9): tool emits success=False and re-raises when helper raises."""
    mod = importlib.import_module(module_path)
    tool_fn = getattr(mod, tool_name)

    captured: list[dict] = []

    async def _fake_emit(self, event_kind: str, payload: dict) -> None:  # noqa: ARG001
        full_event = {"event_kind": event_kind, **payload}
        captured.append(full_event)

    actor = _make_actor()

    with (
        patch.object(ToolRoiEmitter, "emit", _fake_emit),
        patch(f"{module_path}.require_actor", return_value=actor),
        patch(f"{module_path}.{helper_name}", side_effect=RuntimeError("boom")),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            if isinstance(sample_input, str):
                await tool_fn(sample_input)
            else:
                await tool_fn(sample_input)

    assert captured, f"{tool_name}: no ROI event emitted on exception"
    event = captured[0]

    # Must pass the pre-flight validator (all 8 keys required even on error path)
    validate_event_for_persistence(event)

    assert event["tool"] == "rls_apex", (
        f"{tool_name}: event['tool'] must be 'rls_apex' on error path"
    )
    assert event["workflow"] == expected_workflow, (
        f"{tool_name}: workflow mismatch on error path"
    )
    assert event["success"] is False, (
        f"{tool_name}: success must be False when helper raises"
    )

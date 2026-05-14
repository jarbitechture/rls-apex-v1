"""E1 — get_policy_snippets emit shapes validated against ROI schema.

These tests patch ToolRoiEmitter.emit at class level (bypassing the emitter's
internal validate_event_for_persistence call) to independently verify that the
server's payload construction produces a schema-compliant event. Lock #7: the
failure-path event must be emitted before the exception re-raises.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.gateway.sidecar._client import validate_event_for_persistence
import mcp_tools.get_policy_snippets.server as server
from mcp_tools._lib.corpus.retriever import HybridRetriever
from mcp_tools._lib.corpus.types import Hit
from mcp_tools._lib.roi_emit import ToolRoiEmitter


def _make_actor(actor_id: str = "tester@manatee.local") -> MagicMock:
    actor = MagicMock()
    actor.actor_id = actor_id
    return actor


def _make_hit(source_id: str, source_type: str) -> Hit:
    return Hit(
        id=hash(source_id) % (2**31),
        source_id=source_id,
        source_type=source_type,
        citation=f"Citation for {source_id}",
        body=f"Body text for {source_id}.",
        score=0.85,
        metadata={},
    )


# ---------------------------------------------------------------------------
# Test 1: success-path emit passes ROI schema validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_policy_snippets_emit_success_passes_schema():
    """Success-path emit payload must satisfy validate_event_for_persistence."""
    actor = _make_actor()

    hits = [
        _make_hit("ldc.art2.s3", "ldc"),
        _make_hit("proc.2023.001", "procedure"),
        _make_hit("ord.2022.014", "ordinance"),
    ]

    mock_retriever = MagicMock(spec=HybridRetriever)
    mock_retriever.search = AsyncMock(return_value=hits)

    async def _fake_get_retriever():
        return mock_retriever

    captured: list[dict] = []

    async def _capture_emit(self, event_kind: str, payload: dict) -> None:  # noqa: ARG001
        captured.append({"event_kind": event_kind, **payload})

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server, "_get_retriever", _fake_get_retriever),
        patch.object(ToolRoiEmitter, "emit", _capture_emit),
    ):
        await server.get_policy_snippets(
            topic_or_field="floodplain setback requirements",
            rls_id="RLS-2024-001",
            k=3,
        )

    assert len(captured) == 1, f"Expected 1 ROI event, got {len(captured)}"
    event = captured[0]

    # Must not raise — this is the core E1 assertion.
    validate_event_for_persistence(event)

    # Spot-check the success flag so the test is non-vacuous.
    assert event["success"] is True
    assert event["event_kind"] == "rag_hit"


# ---------------------------------------------------------------------------
# Test 2: failure-path emit passes ROI schema validation (Lock #7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_policy_snippets_emit_failure_passes_schema():
    """Lock #7: success=False event emitted BEFORE re-raise must pass schema."""
    actor = _make_actor()

    async def _broken_get_retriever():
        raise RuntimeError("embed service unreachable")

    captured: list[dict] = []

    async def _capture_emit(self, event_kind: str, payload: dict) -> None:  # noqa: ARG001
        captured.append({"event_kind": event_kind, **payload})

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server, "_get_retriever", _broken_get_retriever),
        patch.object(ToolRoiEmitter, "emit", _capture_emit),
    ):
        with pytest.raises(RuntimeError, match="embed service unreachable"):
            await server.get_policy_snippets(
                topic_or_field="floodplain setback requirements",
                k=3,
            )

    failure_events = [e for e in captured if e.get("success") is False]
    assert failure_events, "Must emit success=False event before re-raising"

    # Must not raise — this is the core E1 assertion.
    validate_event_for_persistence(failure_events[0])

    assert failure_events[0]["event_kind"] == "rag_hit"

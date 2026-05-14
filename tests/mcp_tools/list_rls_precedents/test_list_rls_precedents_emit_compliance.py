"""E1 — list_rls_precedents emit shapes validated against ROI schema.

These tests patch ToolRoiEmitter.emit at class level (bypassing the emitter's
internal validate_event_for_persistence call) to independently verify that the
server's payload construction produces a schema-compliant event. Lock #7: the
failure-path event must be emitted before the exception re-raises.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.gateway.sidecar._client import validate_event_for_persistence
import mcp_tools.list_rls_precedents.server as server
from mcp_tools._lib.corpus.retriever import HybridRetriever
from mcp_tools._lib.corpus.types import Hit
from mcp_tools._lib.roi_emit import ToolRoiEmitter


def _make_actor(actor_id: str = "tester@manatee.local") -> MagicMock:
    actor = MagicMock()
    actor.actor_id = actor_id
    return actor


def _make_hit(source_id: str, source_type: str, matter_type: str | None = None) -> Hit:
    meta: dict = {}
    if matter_type is not None:
        meta["matter_type"] = matter_type
    return Hit(
        id=hash(source_id) % (2**31),
        source_id=source_id,
        source_type=source_type,
        citation=f"Citation for {source_id}",
        body=f"Body text for {source_id}.",
        score=0.85,
        metadata=meta,
    )


# ---------------------------------------------------------------------------
# Test 1: success-path emit passes ROI schema validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_rls_precedents_emit_success_passes_schema():
    """Success-path emit payload must satisfy validate_event_for_persistence."""
    actor = _make_actor()

    raw_hits = [
        _make_hit("op.2024.01", "internal_opinion", matter_type="variance"),
        _make_hit("ag.2020.05", "fl_ag_opinion"),
    ]

    mock_retriever = MagicMock(spec=HybridRetriever)
    mock_retriever.search = AsyncMock(return_value=raw_hits)

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
        await server.list_rls_precedents(query="variance setback", k=10, matter_type="variance")

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
async def test_list_rls_precedents_emit_failure_passes_schema():
    """Lock #7: success=False event emitted BEFORE re-raise must pass schema."""
    actor = _make_actor()

    async def _broken_get_retriever():
        raise RuntimeError("DB connection lost")

    captured: list[dict] = []

    async def _capture_emit(self, event_kind: str, payload: dict) -> None:  # noqa: ARG001
        captured.append({"event_kind": event_kind, **payload})

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server, "_get_retriever", _broken_get_retriever),
        patch.object(ToolRoiEmitter, "emit", _capture_emit),
    ):
        with pytest.raises(RuntimeError, match="DB connection lost"):
            await server.list_rls_precedents(query="variance setback", k=10)

    failure_events = [e for e in captured if e.get("success") is False]
    assert failure_events, "Must emit success=False event before re-raising"

    # Must not raise — this is the core E1 assertion.
    validate_event_for_persistence(failure_events[0])

    assert failure_events[0]["event_kind"] == "rag_hit"

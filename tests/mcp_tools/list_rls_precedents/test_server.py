"""list_rls_precedents MCP tool — unit tests.

Plan C Task 6. Four tests covering:
1. Source filter pinned to precedent types.
2. matter_type post-filter (internal_opinion filtered; fl_ag_opinion passes through).
3. ROI rag_hit event emitted with hit_count + matter_type in extra.
4. success=False emitted BEFORE raising on retriever failure (Lock #7).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import mcp_tools.list_rls_precedents.server as server
from mcp_tools._lib.corpus.retriever import HybridRetriever
from mcp_tools._lib.corpus.types import Hit
from mcp_tools._lib.roi_emit import ToolRoiEmitter


def _make_actor(actor_id: str = "tester@manatee.local") -> MagicMock:
    actor = MagicMock()
    actor.actor_id = actor_id
    return actor


def _make_hit(
    source_id: str,
    source_type: str,
    matter_type: str | None = None,
) -> Hit:
    meta: dict = {}
    if matter_type is not None:
        meta["matter_type"] = matter_type
    return Hit(
        id=hash(source_id) % (2**31),
        source_id=source_id,
        source_type=source_type,
        citation=f"Citation for {source_id}",
        body=f"Body text for {source_id}.",
        score=0.9,
        metadata=meta,
    )


# ---------------------------------------------------------------------------
# Test 1: source_filter is pinned to PRECEDENT_SOURCES
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_rls_precedents_filters_to_precedent_sources():
    """Retriever must be called with source_filter=PRECEDENT_SOURCES."""
    actor = _make_actor()

    mock_retriever = MagicMock(spec=HybridRetriever)
    mock_retriever.search = AsyncMock(return_value=[])

    async def _fake_get_retriever():
        return mock_retriever

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server, "_get_retriever", _fake_get_retriever),
        patch.object(ToolRoiEmitter, "emit", AsyncMock()),
    ):
        await server.list_rls_precedents(query="variance setback hearing", k=5)

    mock_retriever.search.assert_called_once()
    call_kwargs = mock_retriever.search.call_args
    used_filter = call_kwargs.kwargs.get(
        "source_filter", call_kwargs.args[2] if len(call_kwargs.args) > 2 else None
    )
    assert set(used_filter) == {"internal_opinion", "fl_ag_opinion"}, (
        f"source_filter must be pinned to PRECEDENT_SOURCES, got: {used_filter}"
    )


# ---------------------------------------------------------------------------
# Test 2: matter_type post-filter behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_rls_precedents_filters_by_matter_type():
    """internal_opinion hits must match matter_type; fl_ag_opinion always passes."""
    actor = _make_actor()

    raw_hits = [
        _make_hit("op.2023.01", "internal_opinion", matter_type="variance"),
        _make_hit("op.2023.02", "internal_opinion", matter_type="easement"),  # wrong type
        _make_hit("ag.2021.01", "fl_ag_opinion", matter_type=None),           # always passes
        _make_hit("op.2023.03", "internal_opinion", matter_type="variance"),
    ]

    mock_retriever = MagicMock(spec=HybridRetriever)
    mock_retriever.search = AsyncMock(return_value=raw_hits)

    async def _fake_get_retriever():
        return mock_retriever

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server, "_get_retriever", _fake_get_retriever),
        patch.object(ToolRoiEmitter, "emit", AsyncMock()),
    ):
        result = await server.list_rls_precedents(
            query="variance procedure", k=10, matter_type="variance"
        )

    returned_ids = {h["source_id"] for h in result["hits"]}
    # op.2023.02 has matter_type="easement" — must be excluded
    assert "op.2023.02" not in returned_ids, (
        "internal_opinion with wrong matter_type must be filtered out"
    )
    # fl_ag_opinion always passes
    assert "ag.2021.01" in returned_ids, (
        "fl_ag_opinion must always pass through the matter_type filter"
    )
    # variance opinions retained
    assert "op.2023.01" in returned_ids
    assert "op.2023.03" in returned_ids


# ---------------------------------------------------------------------------
# Test 3: ROI rag_hit event with hit_count + matter_type in extra
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_rls_precedents_emits_rag_hit():
    """Must emit event_kind='rag_hit' with hit_count and matter_type in extra."""
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
        await server.list_rls_precedents(
            query="public hearing access", k=10, matter_type="variance"
        )

    assert len(captured) == 1, f"Expected 1 ROI event, got {len(captured)}"
    event = captured[0]

    assert event["event_kind"] == "rag_hit", (
        f"event_kind must be 'rag_hit', got {event['event_kind']!r}"
    )
    assert event["success"] is True
    assert event["user_id"] == actor.actor_id

    extra = event.get("extra", {})
    assert "hit_count" in extra, "extra must contain hit_count"
    assert extra["hit_count"] == 2, f"hit_count should be 2, got {extra['hit_count']}"
    assert "matter_type" in extra, "extra must contain matter_type"
    assert extra["matter_type"] == "variance"


# ---------------------------------------------------------------------------
# Test 4: success=False emitted BEFORE raising on retriever failure (Lock #7)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_rls_precedents_emits_failure_on_raise():
    """Lock #7: success=False must be emitted BEFORE the exception re-raises."""
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
            await server.list_rls_precedents(query="test", k=5)

    assert len(captured) >= 1, "Must emit at least one ROI event before raising"
    # The emit that preceded the raise must have success=False
    failure_events = [e for e in captured if e.get("success") is False]
    assert failure_events, "Must emit success=False before re-raising the exception"
    assert failure_events[0]["event_kind"] == "rag_hit"
    assert failure_events[0]["extra"]["hit_count"] == 0

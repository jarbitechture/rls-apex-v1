"""get_policy_snippets MCP tool — unit tests.

Plan C Task 7. Four tests covering:
1. Source filter pinned to POLICY_SOURCES (ldc, ordinance, procedure).
2. procedure_corpus_pending=True when no procedure hit is returned.
3. procedure_corpus_pending=False when at least one procedure hit is returned.
4. ROI rag_hit event includes procedure_corpus_available in extra (Lock #7 path).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        score=0.9,
        metadata={},
    )


# ---------------------------------------------------------------------------
# Fixtures: mock retriever with and without procedure hits
# ---------------------------------------------------------------------------

LDC_ONLY_HITS = [
    _make_hit("ldc.art2.s3", "ldc"),
    _make_hit("ord.2022.014", "ordinance"),
]

WITH_PROCEDURE_HITS = [
    _make_hit("ldc.art2.s3", "ldc"),
    _make_hit("proc.2023.001", "procedure"),
    _make_hit("ord.2022.014", "ordinance"),
]


# ---------------------------------------------------------------------------
# Test 1: source_filter is pinned to POLICY_SOURCES
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_policy_snippets_returns_policy_sources_only():
    """Retriever must be called with source_filter == POLICY_SOURCES."""
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
        await server.get_policy_snippets(topic_or_field="setback requirements", k=3)

    mock_retriever.search.assert_called_once()
    call_kwargs = mock_retriever.search.call_args
    used_filter = call_kwargs.kwargs.get(
        "source_filter", call_kwargs.args[2] if len(call_kwargs.args) > 2 else None
    )
    assert set(used_filter) == {"ldc", "ordinance", "procedure"}, (
        f"source_filter must be pinned to POLICY_SOURCES, got: {used_filter}"
    )


# ---------------------------------------------------------------------------
# Test 2: procedure_corpus_pending=True when no procedure hit returned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_policy_snippets_flags_procedure_pending_when_no_procedure_hit():
    """procedure_corpus_pending must be True when no procedure-type hit is in results."""
    actor = _make_actor()

    mock_retriever = MagicMock(spec=HybridRetriever)
    mock_retriever.search = AsyncMock(return_value=LDC_ONLY_HITS)

    async def _fake_get_retriever():
        return mock_retriever

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server, "_get_retriever", _fake_get_retriever),
        patch.object(ToolRoiEmitter, "emit", AsyncMock()),
    ):
        result = await server.get_policy_snippets(
            topic_or_field="flood zone setback", k=3
        )

    assert result["procedure_corpus_pending"] is True, (
        "procedure_corpus_pending must be True when no procedure hit is present"
    )


# ---------------------------------------------------------------------------
# Test 3: procedure_corpus_pending=False when procedure hit present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_policy_snippets_does_not_flag_pending_when_procedure_hit_present():
    """procedure_corpus_pending must be False when at least one procedure hit exists."""
    actor = _make_actor()

    mock_retriever = MagicMock(spec=HybridRetriever)
    mock_retriever.search = AsyncMock(return_value=WITH_PROCEDURE_HITS)

    async def _fake_get_retriever():
        return mock_retriever

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server, "_get_retriever", _fake_get_retriever),
        patch.object(ToolRoiEmitter, "emit", AsyncMock()),
    ):
        result = await server.get_policy_snippets(
            topic_or_field="floodplain procedure", k=3
        )

    assert result["procedure_corpus_pending"] is False, (
        "procedure_corpus_pending must be False when a procedure hit is present"
    )


# ---------------------------------------------------------------------------
# Test 4: ROI rag_hit includes procedure_corpus_available in extra
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_policy_snippets_emits_rag_hit_with_procedure_availability():
    """Must emit rag_hit with procedure_corpus_available=True in extra when procedure hit present."""
    actor = _make_actor()

    mock_retriever = MagicMock(spec=HybridRetriever)
    mock_retriever.search = AsyncMock(return_value=WITH_PROCEDURE_HITS)

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
            topic_or_field="floodplain procedure",
            rls_id="RLS-2024-001",
            k=3,
        )

    assert len(captured) == 1, f"Expected 1 ROI event, got {len(captured)}"
    event = captured[0]

    assert event["event_kind"] == "rag_hit", (
        f"event_kind must be 'rag_hit', got {event['event_kind']!r}"
    )
    assert event["success"] is True
    assert event["user_id"] == actor.actor_id

    extra = event.get("extra", {})
    assert extra.get("procedure_corpus_available") is True, (
        f"procedure_corpus_available must be True, got: {extra.get('procedure_corpus_available')!r}"
    )
    assert extra.get("topic") == "floodplain procedure", (
        f"extra.topic must match topic_or_field, got: {extra.get('topic')!r}"
    )
    assert extra.get("rls_id") == "RLS-2024-001", (
        f"extra.rls_id must match passed rls_id, got: {extra.get('rls_id')!r}"
    )
    assert extra.get("k") == 3, f"extra.k must be 3, got: {extra.get('k')!r}"
    assert "hit_count" in extra, "extra must contain hit_count"
    assert extra["hit_count"] == len(WITH_PROCEDURE_HITS), (
        f"hit_count should be {len(WITH_PROCEDURE_HITS)}, got {extra['hit_count']}"
    )

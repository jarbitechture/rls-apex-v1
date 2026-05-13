"""HybridRetriever tests — RRF correctness, BM25 + ANN order, point-in-time.

W3 acceptance criterion from spec §15.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from mcp_tools._lib.corpus.retriever import HybridRetriever
from mcp_tools._lib.corpus.types import Hit
from tests.fixtures.corpus_seed import _deterministic_embedding, seeded_corpus  # noqa: F401


@pytest.fixture()
def fake_embed_client():
    """Returns a deterministic vector that matches one seeded chunk."""
    c = AsyncMock()
    # Default: target the LDC §6.4 current row
    c.embed = AsyncMock(return_value=_deterministic_embedding("ldc.6.4.a.2"))
    return c


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bm25_search_returns_lexical_match_first(seeded_corpus, fake_embed_client):
    r = HybridRetriever(seeded_corpus, fake_embed_client)
    hits = await r._bm25_search("variance applications hearing", k=10)
    # Top hit should be LDC §6.5 ("Variance applications must be filed...")
    assert len(hits) >= 1
    assert hits[0].source_id == "ldc.6.5.a"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ann_search_returns_semantic_match_first(seeded_corpus, fake_embed_client):
    r = HybridRetriever(seeded_corpus, fake_embed_client)
    # query_vec is the embedding for "ldc.6.4.a.2" seed — should rank that chunk first
    query_vec = _deterministic_embedding("ldc.6.4.a.2")
    hits = await r._ann_search(query_vec, k=10)
    assert hits[0].source_id == "ldc.6.4.a.2"


@pytest.mark.asyncio
async def test_rrf_merge_is_correct():
    """RRF: score(d) = Σ 1 / (k + rank_in_list_i(d))."""
    from mcp_tools._lib.corpus.retriever import HybridRetriever

    # Two ranked lists. Doc A is rank 1 in list1, rank 2 in list2.
    # Doc B is rank 2 in list1, rank 1 in list2. Doc C is rank 3 in list1 only.
    list1 = [
        Hit(id=1, source_id="A", source_type="ldc", citation="A", body="A", score=1.0),
        Hit(id=2, source_id="B", source_type="ldc", citation="B", body="B", score=0.8),
        Hit(id=3, source_id="C", source_type="ldc", citation="C", body="C", score=0.5),
    ]
    list2 = [
        Hit(id=2, source_id="B", source_type="ldc", citation="B", body="B", score=0.95),
        Hit(id=1, source_id="A", source_type="ldc", citation="A", body="A", score=0.85),
    ]
    # k=60 Cormack default. Expected RRF scores:
    # A: 1/(60+1) + 1/(60+2) = 0.01639... + 0.01613... = 0.03252...
    # B: 1/(60+2) + 1/(60+1) = same = 0.03252...
    # C: 1/(60+3) = 0.01587...
    # A and B tie; tiebreak is by id ASC (stable). C is last.
    merged = HybridRetriever._rrf_merge(list1, list2, k=3, rrf_k=60)
    ids = [h.source_id for h in merged]
    # Ties broken deterministically (by id ascending)
    assert ids[:2] == ["A", "B"]
    assert ids[2] == "C"
    # Scores should be normalized to [0, 1]
    assert all(0.0 <= h.score <= 1.0 for h in merged)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_hybrid_search_returns_top_k(seeded_corpus, fake_embed_client):
    r = HybridRetriever(seeded_corpus, fake_embed_client)
    hits = await r.search("permit setback", k=5)
    assert len(hits) <= 5
    # All hits must be Hit instances with normalized scores
    for h in hits:
        assert isinstance(h, Hit)
        assert 0.0 <= h.score <= 1.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_source_filter_excludes_other_types(seeded_corpus, fake_embed_client):
    r = HybridRetriever(seeded_corpus, fake_embed_client)
    hits = await r.search("hearing", k=10, source_filter=["fl_ag_opinion"])
    for h in hits:
        assert h.source_type == "fl_ag_opinion"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_point_in_time_query_returns_historical_version(seeded_corpus, fake_embed_client):
    r = HybridRetriever(seeded_corpus, fake_embed_client)
    # 2023-06-01: historical LDC §6.4 was valid (2022-01-01 to 2024-01-01)
    valid_at = datetime(2023, 6, 1, tzinfo=timezone.utc)
    hits = await r._bm25_search("permit erected", k=10, valid_at=valid_at)
    # Should find the historical version, not the 2024 version
    matching = [h for h in hits if h.source_id == "ldc.6.4.a.2"]
    assert len(matching) >= 1
    assert "pre-2024" in matching[0].body


@pytest.mark.integration
@pytest.mark.asyncio
async def test_default_query_excludes_historical_versions(seeded_corpus, fake_embed_client):
    r = HybridRetriever(seeded_corpus, fake_embed_client)
    # No valid_at = current corpus only
    hits = await r._bm25_search("permit erected", k=10)
    for h in hits:
        if h.source_id == "ldc.6.4.a.2":
            assert "pre-2024" not in h.body


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_falls_back_to_bm25_when_embed_unavailable(seeded_corpus):
    from mcp_tools._lib.corpus.embed_client import EmbeddingUnavailable

    failing_client = AsyncMock()
    failing_client.embed = AsyncMock(side_effect=EmbeddingUnavailable("test"))
    r = HybridRetriever(seeded_corpus, failing_client)
    hits = await r.search("variance applications", k=5)
    # Should still get BM25 hits, with metadata flag
    assert len(hits) >= 1
    assert any(h.metadata.get("retrieval_mode") == "bm25_only" for h in hits)

"""E2 — Embedding-service down → HybridRetriever BM25-only fallback.

Verifies the circuit-breaker contract from spec §6.1 (ADR-001):
  - When embedding-service returns 503, EmbedClient raises EmbeddingUnavailable
    and HybridRetriever falls back to BM25-only, tagging every hit with
    metadata.retrieval_mode == "bm25_only".
  - When embedding-service returns 200 with a valid embedding, hybrid path
    executes and no hits carry the bm25_only tag.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mcp_tools._lib.corpus.embed_client import EmbedClient
from mcp_tools._lib.corpus.retriever import HybridRetriever
from tests.fixtures.corpus_seed import seeded_corpus, _deterministic_embedding  # noqa: F401


@pytest.mark.integration
async def test_breaker_open_falls_back_to_bm25(seeded_corpus):
    """Embedding-service 503 → EmbedClient raises → HybridRetriever uses BM25-only."""
    mock_resp = httpx.Response(503, json={"detail": "breaker open"})
    embed_client = EmbedClient(base_url="http://127.0.0.1:30201")
    r = HybridRetriever(seeded_corpus, embed_client)
    with patch.object(httpx.AsyncClient, "post", AsyncMock(return_value=mock_resp)):
        hits = await r.search("variance applications", k=5)
    assert len(hits) >= 1, "BM25-only path must still return at least one hit"
    assert all(h.metadata.get("retrieval_mode") == "bm25_only" for h in hits), (
        "Every hit must be tagged bm25_only so the frontend can surface degraded mode"
    )


@pytest.mark.integration
async def test_breaker_recovery_returns_to_hybrid(seeded_corpus):
    """Embedding-service 200 → hybrid path executes → no hit carries bm25_only tag."""
    embedding = _deterministic_embedding("ldc.6.4.a.2")
    mock_resp = httpx.Response(200, json={"embedding": embedding})
    embed_client = EmbedClient(base_url="http://127.0.0.1:30201")
    r = HybridRetriever(seeded_corpus, embed_client)
    with patch.object(httpx.AsyncClient, "post", AsyncMock(return_value=mock_resp)):
        hits = await r.search("variance applications", k=5)
    assert len(hits) >= 1, "Hybrid path must return at least one hit"
    assert not any(h.metadata.get("retrieval_mode") == "bm25_only" for h in hits), (
        "No hit should carry bm25_only when embedding-service is healthy"
    )

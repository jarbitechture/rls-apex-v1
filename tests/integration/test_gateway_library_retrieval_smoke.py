"""Plan D Task 10a — Gateway → library-retrieval smoke test (inherited Plan C Task 10).

Exercises the REAL (unpatched) _call_l4_get_policy_snippets helper in
apps.gateway.main against a seeded test corpus, mocking only the embedding
HTTP POST so the test stays offline.

Design constraints:
  - _lint_retriever is a module-level singleton; must be reset before/after each
    test to prevent cross-test pollution.
  - app.state.db_pool must be injected so _get_lint_retriever() can build the
    HybridRetriever without an HTTPException(503).
  - Embedding HTTP mock follows the same pattern as
    tests/integration/test_embedding_breaker_fallback.py.
  - NO tests/integration/__init__.py — rootdir-based pytest collection.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

import apps.gateway.main as gw_main
from tests.fixtures.corpus_seed import _deterministic_embedding, seeded_corpus  # noqa: F401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_call_l4_get_policy_snippets_returns_seeded_rows(seeded_corpus):
    """_call_l4_get_policy_snippets returns correct shape with >=1 seeded hit.

    seeded_corpus yields an asyncpg Pool seeded with 30 rows (5 each for ldc,
    ordinance, procedure, fl_ag_opinion, internal_opinion, calendar).
    POLICY_SOURCES = ["ldc", "ordinance", "procedure"] — all three types are
    present, so the helper must find at least one match for "permit".
    """
    # Reset the module-level singleton so this test always exercises init.
    gw_main._lint_retriever = None
    # Inject the seeded pool so _get_lint_retriever() succeeds.
    gw_main.app.state.db_pool = seeded_corpus

    # Use a deterministic embedding that targets the ldc.6.4.a.2 seed row
    # ("No structure shall be erected without a permit...").
    embedding = _deterministic_embedding("ldc.6.4.a.2")
    mock_resp = httpx.Response(200, json={"embedding": embedding})

    try:
        with patch.object(httpx.AsyncClient, "post", AsyncMock(return_value=mock_resp)):
            result = await gw_main._call_l4_get_policy_snippets(
                topic_or_field="permit", k=5
            )
    finally:
        # Always reset the singleton AND the injected pool so downstream tests
        # are not polluted by this test's injected (and soon-closed) pool.
        gw_main._lint_retriever = None
        gw_main.app.state.db_pool = None

    # --- Shape assertions ---
    assert isinstance(result, dict), "result must be a dict"
    assert "snippets" in result, "result must contain 'snippets' key"
    assert "procedure_corpus_pending" in result, (
        "result must contain 'procedure_corpus_pending' key"
    )
    assert isinstance(result["snippets"], list), "'snippets' must be a list"
    assert isinstance(result["procedure_corpus_pending"], bool), (
        "'procedure_corpus_pending' must be a bool"
    )

    # --- Content assertions ---
    assert len(result["snippets"]) >= 1, (
        "At least one seeded ldc/ordinance/procedure row must be retrieved "
        "for query 'permit'; check POLICY_SOURCES filter or seeded data"
    )

    for snippet in result["snippets"]:
        assert "citation" in snippet, f"snippet missing 'citation': {snippet}"
        assert "body" in snippet, f"snippet missing 'body': {snippet}"
        assert "source_type" in snippet, f"snippet missing 'source_type': {snippet}"
        assert snippet["source_type"] in ("ldc", "ordinance", "procedure"), (
            f"snippet source_type {snippet['source_type']!r} is not in POLICY_SOURCES"
        )

    # --- Sanity: confirm gateway→library path is exercised end-to-end ---
    # At least one snippet must reference a permit-related body from seeded data.
    permit_hits = [
        s for s in result["snippets"]
        if "permit" in s["body"].lower() or "permit" in s["citation"].lower()
    ]
    assert len(permit_hits) >= 1, (
        "Expected at least one snippet with 'permit' in body or citation; "
        f"got snippets: {result['snippets']}"
    )

"""get_policy_snippets — L4 MCP tool: retrieve relevant policy snippets.

Spec §6.1 and Plan C Task 7. Sources pinned to ldc + ordinance + procedure.
No matter_type post-filter; no over-fetch. Flags procedure_corpus_pending
when no procedure-source hit is present in the returned results.

Port 30104. No circuit breaker on the tool itself — the HybridRetriever's
DB pool and EmbedClient have their own breakers per spec §12.2.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import asyncpg

from mcp_tools._lib.corpus.embed_client import EmbedClient
from mcp_tools._lib.corpus.retriever import HybridRetriever
from mcp_tools._lib.server import build_tool_app

# D1 contract: build_tool_app returns (app, roi, require_actor).
app, roi, require_actor = build_tool_app("get_policy_snippets")

# Sources that constitute RLS policy references.
POLICY_SOURCES: list[str] = ["ldc", "ordinance", "procedure"]

_EMIT_DEFAULTS: dict[str, Any] = {
    "workflow": "rls_apex.mcp.get_policy_snippets",
    "tool": "rls_apex",
    "task_type": "retrieval",
    "dept": "DEV",
    "role_band": "professional",
}

# Module-level singletons — lazy-initialised on first tool call so the module
# can be imported without a live DB (unit tests patch these before calling).
_db_pool: asyncpg.Pool | None = None
_embed_client: EmbedClient | None = None


async def _get_retriever() -> HybridRetriever:
    """Return (or create) the module-level HybridRetriever."""
    global _db_pool, _embed_client

    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            host=os.environ.get("DB_HOST", "localhost"),
            port=int(os.environ.get("DB_PORT", "5432")),
            database=os.environ["DB_NAME"],
            min_size=1,
            max_size=5,
        )

    if _embed_client is None:
        embed_url = os.environ.get(
            "EMBEDDING_SERVICE_URL", "http://127.0.0.1:30201"
        )
        _embed_client = EmbedClient(embed_url)

    return HybridRetriever(_db_pool, _embed_client)


@app.tool()
async def get_policy_snippets(
    topic_or_field: str,
    rls_id: str | None = None,
    valid_at: str | None = None,
    k: int = 3,
) -> dict:
    """Return the top-k policy snippets most relevant to the topic or field.

    Args:
        topic_or_field: Natural-language topic or LDC field name to search.
        rls_id: Optional RLS case ID to scope the search context.
        valid_at: ISO-8601 UTC datetime string for point-in-time retrieval.
            Omit or pass null for current corpus.
        k: Maximum number of snippets to return (default 3).

    Returns:
        Serialised dict with `snippets` (list of Hit dicts) and
        `procedure_corpus_pending` (True when no procedure hit was found).
    """
    actor = require_actor()

    parsed_valid_at: datetime | None = None
    if valid_at:
        parsed_valid_at = datetime.fromisoformat(valid_at)
        if parsed_valid_at.tzinfo is None:
            parsed_valid_at = parsed_valid_at.replace(tzinfo=timezone.utc)

    try:
        retriever = await _get_retriever()

        # Pass k directly — no over-fetch, no matter_type post-filter.
        hits = await retriever.search(
            topic_or_field,
            k=k,
            source_filter=POLICY_SOURCES,
            valid_at=parsed_valid_at,
        )

        # Flag whether the procedure corpus has any coverage for this query.
        has_procedure = any(h.source_type == "procedure" for h in hits)

    except Exception:
        await roi.emit(
            "rag_hit",
            {
                **_EMIT_DEFAULTS,
                "user_id": actor.actor_id,
                "surface": "mcp",
                "duration_s": 0.0,
                "success": False,
                "extra": {
                    "topic": topic_or_field,
                    "hit_count": 0,
                    "procedure_corpus_available": False,
                    "k": k,
                    "rls_id": rls_id,
                },
            },
        )
        raise

    await roi.emit(
        "rag_hit",
        {
            **_EMIT_DEFAULTS,
            "user_id": actor.actor_id,
            "surface": "mcp",
            "duration_s": 0.0,
            "success": True,
            "extra": {
                "topic": topic_or_field,
                "hit_count": len(hits),
                "procedure_corpus_available": has_procedure,
                "k": k,
                "rls_id": rls_id,
            },
        },
    )

    return {
        "snippets": [h.model_dump(mode="json") for h in hits[:k]],
        "procedure_corpus_pending": not has_procedure,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=30104, log_level="info")

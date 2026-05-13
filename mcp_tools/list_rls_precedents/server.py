"""list_rls_precedents — L3 MCP tool: retrieve relevant legal precedents.

Spec §6.1 and Plan C Task 6. Sources pinned to internal_opinion +
fl_ag_opinion. FL AG opinions pass the matter_type post-filter unconditionally
(they are general-law precedents, not matter-specific).

Port 30103. No circuit breaker on the tool itself — the HybridRetriever's
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
app, roi, require_actor = build_tool_app("list_rls_precedents")

# Sources that constitute RLS legal precedents.
PRECEDENT_SOURCES: list[str] = ["internal_opinion", "fl_ag_opinion"]

_EMIT_DEFAULTS: dict[str, Any] = {
    "workflow": "rls_apex.mcp.list_rls_precedents",
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
            "EMBED_SERVICE_URL", "http://localhost:30200/embed"
        )
        _embed_client = EmbedClient(embed_url)

    return HybridRetriever(_db_pool, _embed_client)


@app.tool()
async def list_rls_precedents(
    query: str,
    k: int = 10,
    matter_type: str | None = None,
    valid_at: str | None = None,
) -> dict:
    """Return the top-k legal precedents most relevant to the query.

    Args:
        query: Natural-language search query.
        k: Maximum number of hits to return (default 10).
        matter_type: Optional matter type (e.g. "variance", "easement").
            internal_opinion hits are filtered to match; fl_ag_opinion hits
            always pass through.
        valid_at: ISO-8601 UTC datetime string for point-in-time retrieval.
            Omit or pass null for current corpus.

    Returns:
        Serialised dict with `hits` (list of Hit dicts) and `metadata`.
    """
    actor = require_actor()

    parsed_valid_at: datetime | None = None
    if valid_at:
        parsed_valid_at = datetime.fromisoformat(valid_at)
        if parsed_valid_at.tzinfo is None:
            parsed_valid_at = parsed_valid_at.replace(tzinfo=timezone.utc)

    try:
        retriever = await _get_retriever()

        # Over-fetch so that matter_type post-filter leaves enough results.
        raw_hits = await retriever.search(
            query,
            k=k * 4,
            source_filter=PRECEDENT_SOURCES,
            valid_at=parsed_valid_at,
        )

        # matter_type post-filter:
        #   • internal_opinion: must match matter_type (if provided)
        #   • fl_ag_opinion:    always passes through (general-law precedents)
        if matter_type:
            filtered = [
                h
                for h in raw_hits
                if h.source_type == "fl_ag_opinion"
                or h.metadata.get("matter_type") == matter_type
            ]
        else:
            filtered = raw_hits

        hits = filtered[:k]

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
                    "hit_count": 0,
                    "matter_type": matter_type,
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
                "hit_count": len(hits),
                "matter_type": matter_type,
            },
        },
    )

    return {
        "hits": [h.model_dump(mode="json") for h in hits],
        "metadata": {
            "query": query,
            "k": k,
            "matter_type": matter_type,
            "valid_at": valid_at,
            "returned": len(hits),
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=30103, log_level="info")

"""HybridRetriever — BM25 (Postgres ts_rank_cd) + pgvector ANN + RRF merge.

Per spec §6.1 and ADR-001. Library is imported into list_rls_precedents
and get_policy_snippets MCP tools.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Optional

import asyncpg

from mcp_tools._lib.corpus.embed_client import EmbedClient, EmbeddingUnavailable
from mcp_tools._lib.corpus.types import Hit


class HybridRetriever:
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        embed_client: EmbedClient,
        rrf_k: int = 60,
    ):
        self.db_pool = db_pool
        self.embed_client = embed_client
        self.rrf_k = rrf_k

    async def search(
        self,
        query: str,
        k: int = 10,
        source_filter: Optional[list[str]] = None,
        valid_at: Optional[datetime] = None,
    ) -> list[Hit]:
        bm25_task = asyncio.create_task(
            self._bm25_search(query, k=50, source_filter=source_filter, valid_at=valid_at)
        )

        bm25_only_mode = False
        ann_hits: list[Hit] = []
        try:
            query_vec = await self.embed_client.embed(query)
        except EmbeddingUnavailable:
            bm25_only_mode = True
        else:
            ann_hits = await self._ann_search(
                query_vec, k=50, source_filter=source_filter, valid_at=valid_at
            )

        bm25_hits = await bm25_task

        if bm25_only_mode:
            # Mark each hit so callers can surface the degraded mode to the UI.
            for h in bm25_hits:
                h.metadata = {**h.metadata, "retrieval_mode": "bm25_only"}
            return bm25_hits[:k]

        return self._rrf_merge(bm25_hits, ann_hits, k=k, rrf_k=self.rrf_k)

    async def _bm25_search(
        self,
        query: str,
        k: int,
        source_filter: Optional[list[str]] = None,
        valid_at: Optional[datetime] = None,
    ) -> list[Hit]:
        where = []
        args: list = [query]
        if valid_at is None:
            where.append("valid_to IS NULL")
        else:
            where.append("valid_from <= $2 AND (valid_to IS NULL OR valid_to > $2)")
            args.append(valid_at)
        if source_filter:
            ph = f"${len(args) + 1}"
            where.append(f"source_type = ANY({ph})")
            args.append(source_filter)
        args.append(k)
        k_ph = f"${len(args)}"

        sql = f"""
            SELECT id, source_id, source_type, section_path, citation, body,
                   ts_rank_cd(to_tsvector('english', body), plainto_tsquery('english', $1)) AS score,
                   valid_from, valid_to, metadata
            FROM corpus_chunks
            WHERE plainto_tsquery('english', $1) @@ to_tsvector('english', body)
              AND {' AND '.join(where)}
            ORDER BY score DESC
            LIMIT {k_ph}
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        if not rows:
            return []
        # Normalize ts_rank_cd scores into [0, 1] by dividing by max in result set.
        max_score = max(r["score"] for r in rows) or 1.0
        hits = []
        for r in rows:
            hits.append(
                Hit(
                    id=r["id"],
                    source_id=r["source_id"],
                    source_type=r["source_type"],
                    section_path=r["section_path"],
                    citation=r["citation"],
                    body=r["body"],
                    score=min(1.0, max(0.0, r["score"] / max_score)),
                    valid_from=r["valid_from"],
                    valid_to=r["valid_to"],
                    metadata=json.loads(r["metadata"]) if r["metadata"] else {},
                )
            )
        return hits

    async def _ann_search(
        self,
        query_vec: list[float],
        k: int,
        source_filter: Optional[list[str]] = None,
        valid_at: Optional[datetime] = None,
    ) -> list[Hit]:
        where = []
        args: list = [str(query_vec)]  # pgvector accepts text-formatted vector
        if valid_at is None:
            where.append("valid_to IS NULL")
        else:
            where.append("valid_from <= $2 AND (valid_to IS NULL OR valid_to > $2)")
            args.append(valid_at)
        if source_filter:
            ph = f"${len(args) + 1}"
            where.append(f"source_type = ANY({ph})")
            args.append(source_filter)
        args.append(k)
        k_ph = f"${len(args)}"

        sql = f"""
            SELECT id, source_id, source_type, section_path, citation, body,
                   1 - (embedding <=> $1::vector) AS score,
                   valid_from, valid_to, metadata
            FROM corpus_chunks
            WHERE embedding IS NOT NULL
              AND {' AND '.join(where)}
            ORDER BY embedding <=> $1::vector ASC
            LIMIT {k_ph}
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
        return [
            Hit(
                id=r["id"],
                source_id=r["source_id"],
                source_type=r["source_type"],
                section_path=r["section_path"],
                citation=r["citation"],
                body=r["body"],
                score=min(1.0, max(0.0, float(r["score"]))),
                valid_from=r["valid_from"],
                valid_to=r["valid_to"],
                metadata=json.loads(r["metadata"]) if r["metadata"] else {},
            )
            for r in rows
        ]

    @staticmethod
    def _rrf_merge(
        bm25_hits: list[Hit],
        ann_hits: list[Hit],
        k: int,
        rrf_k: int = 60,
    ) -> list[Hit]:
        """Reciprocal Rank Fusion (Cormack 2009).

        score(d) = Σ 1 / (rrf_k + rank_in_list_i(d))
        Tie-broken by source_id ascending for stability.
        """
        rrf: dict[str, float] = {}
        first_hit_seen: dict[str, Hit] = {}
        for rank, h in enumerate(bm25_hits, start=1):
            sid = h.source_id
            rrf[sid] = rrf.get(sid, 0.0) + 1.0 / (rrf_k + rank)
            first_hit_seen.setdefault(sid, h)
        for rank, h in enumerate(ann_hits, start=1):
            sid = h.source_id
            rrf[sid] = rrf.get(sid, 0.0) + 1.0 / (rrf_k + rank)
            first_hit_seen.setdefault(sid, h)

        # Sort by RRF score DESC, then source_id ASC for tiebreak
        ordered = sorted(rrf.items(), key=lambda kv: (-kv[1], kv[0]))[:k]

        # Normalize scores into [0, 1] by dividing by max
        if not ordered:
            return []
        max_rrf = ordered[0][1] or 1.0
        result = []
        for sid, score in ordered:
            h = first_hit_seen[sid]
            h.score = min(1.0, max(0.0, score / max_rrf))
            result.append(h)
        return result

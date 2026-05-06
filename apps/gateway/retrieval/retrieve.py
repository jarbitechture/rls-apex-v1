"""Query interface: load() + retrieve(q, k, classification_filter).

Returns a list of `Citation` records — same shape the gateway already streams
in SSE events. Production swaps the implementation for BM25+LightRAG+
Contextual Retrieval+pgvector; this file's *signature* is the contract.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .ingest import _tokenize  # shared tokenizer

ROOT = Path(__file__).resolve().parents[3]
INDEX_PATH = ROOT / "corpus" / "index" / "bm25.json"
MANIFEST_PATH = ROOT / "corpus" / "manifest.json"


@dataclass
class Citation:
    id: str
    source: str
    source_kind: str
    pinpoint: str
    excerpt: str
    score: float


# Lazy-loaded module-level state — guarded by a lock so the gateway's lifespan
# can warm it on startup without surprising any concurrent retrieve() calls.
_LOCK = threading.Lock()
_LOADED = False
_CHUNKS: list[dict] = []
_BM25 = None  # rank_bm25.BM25Okapi instance
_DOCS: dict[str, dict] = {}  # doc_id -> manifest entry


def load() -> bool:
    """Warm the in-process index. Idempotent. Returns True on success."""
    global _LOADED, _CHUNKS, _BM25, _DOCS
    with _LOCK:
        if _LOADED:
            return True
        if not INDEX_PATH.exists() or not MANIFEST_PATH.exists():
            return False
        from rank_bm25 import BM25Okapi
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        _CHUNKS = index["chunks"]
        _DOCS = {d["id"]: d for d in manifest["documents"]}
        if _CHUNKS:
            _BM25 = BM25Okapi([c["tokens"] for c in _CHUNKS])
        _LOADED = True
        return True


def manifest() -> dict:
    """Return the manifest as a plain dict (or an empty stub if not loaded)."""
    if not _LOADED:
        load()
    return {
        "loaded": _LOADED,
        "documents": list(_DOCS.values()),
        "total_chunks": len(_CHUNKS),
    }


def reload() -> bool:
    """Force-reload from disk. Use after `bin/ingest` rewrites the index."""
    global _LOADED, _CHUNKS, _BM25, _DOCS
    with _LOCK:
        _LOADED = False
        _CHUNKS = []
        _BM25 = None
        _DOCS = {}
    return load()


def _excerpt(text: str, q_tokens: list[str], max_chars: int = 280) -> str:
    """Best-effort excerpt: pick the first sentence-ish span containing any
    query token; fall back to the head of the chunk."""
    flat = re.sub(r"\s+", " ", text).strip()
    if not flat:
        return ""
    if not q_tokens:
        return flat[:max_chars] + ("…" if len(flat) > max_chars else "")
    low = flat.lower()
    best_pos = -1
    for tok in q_tokens:
        pos = low.find(tok)
        if pos >= 0 and (best_pos < 0 or pos < best_pos):
            best_pos = pos
    if best_pos < 0:
        return flat[:max_chars] + ("…" if len(flat) > max_chars else "")
    start = max(0, best_pos - 60)
    end = min(len(flat), start + max_chars)
    snippet = flat[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(flat):
        snippet = snippet + "…"
    return snippet


def retrieve(
    q: str,
    k: int = 12,
    classification_filter: Optional[list[str]] = None,
) -> list[Citation]:
    """BM25 over the in-process chunk index. Filters by classification if set."""
    if not _LOADED:
        load()
    if not _BM25 or not _CHUNKS or not q.strip():
        return []
    q_tokens = _tokenize(q)
    if not q_tokens:
        return []

    scores = _BM25.get_scores(q_tokens)
    # Take top 4*k by score, then filter + dedupe by doc_id (one chunk per doc)
    indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[: 4 * max(k, 1)]

    seen_docs: set[str] = set()
    out: list[Citation] = []
    for idx in indices:
        score = float(scores[idx])
        if score <= 0:
            continue
        chunk = _CHUNKS[idx]
        doc = _DOCS.get(chunk["doc_id"], {})
        if classification_filter and doc.get("classification") not in classification_filter:
            continue
        if chunk["doc_id"] in seen_docs:
            continue
        seen_docs.add(chunk["doc_id"])
        page_tag = f"p. {chunk['page']}" if chunk.get("page") else f"chunk {chunk['chunk_idx']}"
        out.append(Citation(
            id=chunk["chunk_id"],
            source=doc.get("source", chunk["doc_id"]),
            source_kind=doc.get("source_kind", "document"),
            pinpoint=page_tag,
            excerpt=_excerpt(chunk["text"], q_tokens),
            score=round(score, 3),
        ))
        if len(out) >= k:
            break
    return out

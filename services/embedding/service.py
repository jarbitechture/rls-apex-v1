"""embedding-service — port 30201.

Wraps Ollama mxbai-embed-large with a single-probe circuit breaker. Multiple
MCP tool processes share this service so the breaker state is centralized.

Endpoints:
- POST /embed {text: str} → {embedding: list[float]}
- GET  /health           → {status, ollama_reachable, breaker_state, last_inference_ms}
"""
from __future__ import annotations

import time
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.embedding.breaker import EmbeddingBreaker
from services.embedding.config import (
    BREAKER_FAILURE_THRESHOLD,
    BREAKER_OPEN_SECONDS,
    EMBED_DIM,
    EMBED_MODEL,
    HTTP_TIMEOUT_SECONDS,
    KEEP_ALIVE,
    OLLAMA_URL,
)

app = FastAPI(title="embedding-service")

_breaker = EmbeddingBreaker(
    failure_threshold=BREAKER_FAILURE_THRESHOLD,
    open_for_seconds=BREAKER_OPEN_SECONDS,
)

_last_inference_ms: Optional[float] = None


class EmbedRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)


class EmbedResponse(BaseModel):
    embedding: list[float]


async def _ollama_embed_call(text: str) -> dict:
    """Real Ollama call — split out for monkey-patching in tests."""
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as c:
        r = await c.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text, "keep_alive": KEEP_ALIVE},
        )
        r.raise_for_status()
        return r.json()


async def _probe_ollama() -> bool:
    """Lightweight probe used by /health. Times out fast."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


@app.post("/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    try:
        _breaker.guard()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    started = time.monotonic()
    try:
        resp = await _ollama_embed_call(req.text)
    except Exception as e:
        _breaker.record_failure()
        raise HTTPException(status_code=502, detail=f"ollama error: {e}")

    vec = resp.get("embedding")
    if not isinstance(vec, list) or len(vec) != EMBED_DIM:
        _breaker.record_failure()
        raise HTTPException(
            status_code=502, detail=f"unexpected embedding shape: len={len(vec) if isinstance(vec, list) else 'NA'}"
        )

    _breaker.record_success()
    global _last_inference_ms
    _last_inference_ms = (time.monotonic() - started) * 1000.0
    return EmbedResponse(embedding=vec)


@app.get("/health")
async def health():
    reachable = await _probe_ollama()
    state = _breaker.state
    ok = state == "closed" and reachable
    body = {
        "status": "healthy" if ok else "degraded",
        "ollama_reachable": reachable,
        "breaker_state": state,
        "last_inference_ms": _last_inference_ms,
    }
    if not ok:
        return JSONResponse(status_code=503, content=body)
    return body

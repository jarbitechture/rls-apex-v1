"""EmbedClient — HTTP wrapper to embedding-service for the retrieval library.

Distinct exception type EmbeddingUnavailable lets HybridRetriever drop to
BM25-only without conflating with other retrieval errors.
"""
from __future__ import annotations

import httpx


class EmbeddingUnavailable(RuntimeError):
    """Raised when embedding-service refuses (breaker open) or is unreachable."""


class EmbedClient:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout_seconds

    async def embed(self, text: str) -> list[float]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(f"{self._base}/embed", json={"text": text})
        except httpx.TimeoutException as e:
            raise EmbeddingUnavailable(f"embedding-service timeout: {e}") from e
        except httpx.ConnectError as e:
            raise EmbeddingUnavailable(f"embedding-service connect error: {e}") from e
        except httpx.HTTPError as e:
            raise EmbeddingUnavailable(f"embedding-service http error: {e}") from e

        if r.status_code == 503:
            raise EmbeddingUnavailable(f"embedding-service breaker open: {r.text}")
        if r.status_code != 200:
            raise EmbeddingUnavailable(f"embedding-service {r.status_code}: {r.text}")

        return r.json()["embedding"]

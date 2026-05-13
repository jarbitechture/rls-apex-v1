"""EmbedClient tests."""
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mcp_tools._lib.corpus.embed_client import EmbedClient, EmbeddingUnavailable


@pytest.mark.asyncio
async def test_embed_returns_vector_on_200():
    fake_vec = [0.1] * 1024
    mock_resp = httpx.Response(200, json={"embedding": fake_vec})
    async with httpx.AsyncClient() as _client_unused:
        pass
    with patch.object(httpx.AsyncClient, "post", AsyncMock(return_value=mock_resp)):
        c = EmbedClient(base_url="http://localhost:30201")
        vec = await c.embed("RLS form requirements")
    assert len(vec) == 1024


@pytest.mark.asyncio
async def test_embed_raises_unavailable_on_503():
    mock_resp = httpx.Response(503, json={"detail": "breaker open"})
    with patch.object(httpx.AsyncClient, "post", AsyncMock(return_value=mock_resp)):
        c = EmbedClient(base_url="http://localhost:30201")
        with pytest.raises(EmbeddingUnavailable, match="breaker"):
            await c.embed("x")


@pytest.mark.asyncio
async def test_embed_raises_unavailable_on_connect_error():
    with patch.object(
        httpx.AsyncClient,
        "post",
        AsyncMock(side_effect=httpx.ConnectError("connection refused")),
    ):
        c = EmbedClient(base_url="http://localhost:30201")
        with pytest.raises(EmbeddingUnavailable, match="connect"):
            await c.embed("x")


@pytest.mark.asyncio
async def test_embed_raises_unavailable_on_timeout():
    with patch.object(
        httpx.AsyncClient,
        "post",
        AsyncMock(side_effect=httpx.TimeoutException("timed out")),
    ):
        c = EmbedClient(base_url="http://localhost:30201")
        with pytest.raises(EmbeddingUnavailable, match="timeout"):
            await c.embed("x")

"""FastAPI service tests — POST /embed + GET /health."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from services.embedding.service import app


@pytest.fixture()
def client():
    return TestClient(app)


def test_health_when_breaker_closed_and_ollama_reachable(client):
    with patch("services.embedding.service._probe_ollama", AsyncMock(return_value=True)):
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert body["ollama_reachable"] is True
    assert body["breaker_state"] == "closed"


def test_health_returns_503_when_breaker_open(client):
    from services.embedding.service import _breaker
    _breaker.record_failure(); _breaker.record_failure(); _breaker.record_failure()
    try:
        r = client.get("/health")
        assert r.status_code == 503
        assert r.json()["breaker_state"] == "open"
    finally:
        _breaker.record_success()  # reset for next test


def test_embed_returns_vector_when_ollama_succeeds(client):
    fake_vec = [0.1] * 1024
    fake_resp = {"embedding": fake_vec}
    async_fake = AsyncMock(return_value=fake_resp)
    with patch("services.embedding.service._ollama_embed_call", async_fake):
        r = client.post("/embed", json={"text": "RLS form requirements"})
    assert r.status_code == 200
    body = r.json()
    assert body["embedding"] == fake_vec
    assert len(body["embedding"]) == 1024


def test_embed_returns_503_when_breaker_open(client):
    from services.embedding.service import _breaker
    _breaker.record_failure(); _breaker.record_failure(); _breaker.record_failure()
    try:
        r = client.post("/embed", json={"text": "x"})
        assert r.status_code == 503
    finally:
        _breaker.record_success()


def test_embed_increments_failure_on_ollama_error(client):
    from services.embedding.service import _breaker
    _breaker.record_success()  # reset
    async_fail = AsyncMock(side_effect=RuntimeError("ollama down"))
    with patch("services.embedding.service._ollama_embed_call", async_fail):
        r = client.post("/embed", json={"text": "x"})
    assert r.status_code == 502
    assert _breaker._consecutive_failures == 1

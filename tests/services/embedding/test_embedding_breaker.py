"""Embedding-service breaker tests. Mirrors the manatee-civic-ai breaker pattern."""
import asyncio

import pytest

from services.embedding.breaker import EmbeddingBreaker


@pytest.mark.asyncio
async def test_breaker_starts_closed():
    b = EmbeddingBreaker(failure_threshold=3, open_for_seconds=30)
    assert b.state == "closed"


@pytest.mark.asyncio
async def test_breaker_opens_after_threshold_failures():
    b = EmbeddingBreaker(failure_threshold=3, open_for_seconds=30)
    for _ in range(3):
        b.record_failure()
    assert b.state == "open"


@pytest.mark.asyncio
async def test_breaker_blocks_calls_when_open():
    b = EmbeddingBreaker(failure_threshold=1, open_for_seconds=30)
    b.record_failure()
    assert b.state == "open"
    with pytest.raises(RuntimeError, match="breaker is open"):
        b.guard()


@pytest.mark.asyncio
async def test_breaker_single_probe_half_open():
    """After open_for_seconds elapses, exactly ONE probe is allowed."""
    b = EmbeddingBreaker(failure_threshold=1, open_for_seconds=0)
    b.record_failure()
    assert b.state == "open"
    # First guard() after expiry transitions to half_open
    await asyncio.sleep(0.01)
    b.guard()  # OK — half-open probe allowed
    assert b.state == "half_open"
    # Second guard() while still half-open MUST block
    with pytest.raises(RuntimeError, match="probe in flight"):
        b.guard()


@pytest.mark.asyncio
async def test_breaker_recovers_on_probe_success():
    b = EmbeddingBreaker(failure_threshold=1, open_for_seconds=0)
    b.record_failure()
    await asyncio.sleep(0.01)
    b.guard()  # half-open
    b.record_success()
    assert b.state == "closed"


@pytest.mark.asyncio
async def test_breaker_reopens_on_probe_failure():
    b = EmbeddingBreaker(failure_threshold=1, open_for_seconds=0)
    b.record_failure()
    await asyncio.sleep(0.01)
    b.guard()  # half-open
    b.record_failure()
    assert b.state == "open"

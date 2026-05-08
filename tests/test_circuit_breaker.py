"""Circuit breaker state machine — closed/open/half-open per spec §12.3."""
import asyncio
import pytest

from apps.gateway.circuit.breaker import CircuitBreaker, BreakerOpenError, BreakerState


@pytest.mark.asyncio
async def test_closed_to_open_after_threshold_failures():
    cb = CircuitBreaker(name="test", failure_threshold=5, window_seconds=30, open_duration_seconds=30)
    fail = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

    for _ in range(5):
        with pytest.raises(RuntimeError):
            await cb.call(fail)

    assert cb.state == BreakerState.OPEN

    with pytest.raises(BreakerOpenError):
        await cb.call(fail)


@pytest.mark.asyncio
async def test_open_to_half_open_after_timeout():
    cb = CircuitBreaker(name="test", failure_threshold=2, window_seconds=30, open_duration_seconds=0.1)
    fail = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(fail)
    assert cb.state == BreakerState.OPEN

    await asyncio.sleep(0.15)
    assert cb.state == BreakerState.HALF_OPEN


@pytest.mark.asyncio
async def test_half_open_probe_success_returns_to_closed():
    cb = CircuitBreaker(name="test", failure_threshold=2, window_seconds=30, open_duration_seconds=0.1)
    fail = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(fail)
    await asyncio.sleep(0.15)

    result = await cb.call(lambda: 42)
    assert result == 42
    assert cb.state == BreakerState.CLOSED


@pytest.mark.asyncio
async def test_half_open_probe_fail_returns_to_open():
    cb = CircuitBreaker(name="test", failure_threshold=2, window_seconds=30, open_duration_seconds=0.1)
    fail = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(fail)
    await asyncio.sleep(0.15)
    assert cb.state == BreakerState.HALF_OPEN

    with pytest.raises(RuntimeError):
        await cb.call(fail)
    assert cb.state == BreakerState.OPEN


@pytest.mark.asyncio
async def test_window_expiry_clears_old_failures():
    """Failures outside the window don't count toward threshold."""
    cb = CircuitBreaker(name="test", failure_threshold=3, window_seconds=0.1, open_duration_seconds=30)
    fail = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        await cb.call(fail)
    with pytest.raises(RuntimeError):
        await cb.call(fail)
    await asyncio.sleep(0.15)
    with pytest.raises(RuntimeError):
        await cb.call(fail)

    assert cb.state == BreakerState.CLOSED


def test_status_dict_shape_matches_spec_section_12_4():
    """spec §12.4 — health surface returns {name, state, consecutive_failures, last_failure_ts, last_success_ts}."""
    cb = CircuitBreaker(name="ollama", failure_threshold=5, window_seconds=30, open_duration_seconds=30)
    status = cb.status()
    assert set(status.keys()) >= {"name", "state", "consecutive_failures", "last_failure_ts", "last_success_ts"}
    assert status["name"] == "ollama"
    assert status["state"] == "closed"

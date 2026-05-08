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


@pytest.mark.asyncio
async def test_half_open_single_probe_enforcement():
    """Spec §12.1 — only one probe at a time during HALF_OPEN; others see BreakerOpenError."""
    cb = CircuitBreaker(name="test", failure_threshold=2, window_seconds=30, open_duration_seconds=0.1)
    fail = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

    # Trip the breaker.
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(fail)
    assert cb.state == BreakerState.OPEN

    # Wait for HALF_OPEN.
    await asyncio.sleep(0.15)
    assert cb.state == BreakerState.HALF_OPEN

    # Slow probe + concurrent fast caller.
    probe_started = asyncio.Event()
    probe_release = asyncio.Event()

    async def slow_probe():
        probe_started.set()
        await probe_release.wait()
        return "ok"

    async def fast_caller():
        return await cb.call(lambda: 42)

    probe_task = asyncio.create_task(cb.call(slow_probe))
    await probe_started.wait()  # ensure probe is in flight before competing call

    # Concurrent caller should be rejected (probe already in flight).
    with pytest.raises(BreakerOpenError):
        await fast_caller()

    # Release the probe.
    probe_release.set()
    result = await probe_task
    assert result == "ok"
    assert cb.state == BreakerState.CLOSED


@pytest.mark.asyncio
async def test_half_open_probe_failure_releases_slot_and_reopens():
    """If the probe fails, the in-flight flag clears so the next OPEN→HALF_OPEN cycle works."""
    cb = CircuitBreaker(name="test", failure_threshold=2, window_seconds=30, open_duration_seconds=0.1)
    fail = lambda: (_ for _ in ()).throw(RuntimeError("boom"))

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(fail)
    await asyncio.sleep(0.15)

    # Probe fails → re-open.
    with pytest.raises(RuntimeError):
        await cb.call(fail)
    assert cb.state == BreakerState.OPEN

    # Wait again, then a successful probe should work.
    await asyncio.sleep(0.15)
    result = await cb.call(lambda: 99)
    assert result == 99
    assert cb.state == BreakerState.CLOSED

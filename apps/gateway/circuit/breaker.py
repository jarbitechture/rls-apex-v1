"""Circuit breaker state machine.

Implements the closed → open → half-open pattern from spec §12.3:

  closed ──[N fails / window_seconds]──▶ open
  open ──[open_duration_seconds elapsed]──▶ half-open
  half-open ──[probe success]──▶ closed
  half-open ──[probe fail]──▶ open

Concurrency: state mutations are guarded by an asyncio.Lock. Single-process
only — distributed coordination is out of scope (each tool runs its own
breakers; no shared state across processes).
"""
from __future__ import annotations
import asyncio
import time
from collections import deque
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BreakerOpenError(RuntimeError):
    """Raised when a call is rejected because the breaker is open."""

    def __init__(self, name: str, retry_after_seconds: float) -> None:
        super().__init__(f"breaker '{name}' open; retry after {retry_after_seconds:.1f}s")
        self.name = name
        self.retry_after_seconds = retry_after_seconds


class CircuitBreaker:
    """Single-process circuit breaker.

    Args:
        name: identifier for telemetry and the /api/health/breakers surface
        failure_threshold: failures inside `window_seconds` that trip the breaker
        window_seconds: rolling window for counting failures
        open_duration_seconds: how long to stay open before allowing a half-open probe
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        window_seconds: float = 30.0,
        open_duration_seconds: float = 30.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.open_duration_seconds = open_duration_seconds

        self._failures: deque[float] = deque()  # timestamps
        self._opened_at: float | None = None
        self._last_failure_ts: float | None = None
        self._last_success_ts: float | None = None
        self._consecutive_failures: int = 0
        self._probe_in_flight: bool = False
        self._lock = asyncio.Lock()

    @property
    def state(self) -> BreakerState:
        if self._opened_at is None:
            return BreakerState.CLOSED
        if time.monotonic() - self._opened_at >= self.open_duration_seconds:
            return BreakerState.HALF_OPEN
        return BreakerState.OPEN

    def _prune_failures(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()

    async def call(self, fn: Callable[[], T] | Callable[[], Awaitable[T]]) -> T:
        """Execute `fn` through the breaker. `fn` may be sync or async.

        Single-probe semantics in HALF_OPEN: only one call at a time may pass
        while recovering. Concurrent callers see BreakerOpenError until the
        probe resolves. Spec §12.1 — "single probe".
        """
        is_probe = False
        async with self._lock:
            current = self.state
            if current == BreakerState.OPEN:
                if self._opened_at is None:
                    raise RuntimeError(
                        f"breaker '{self.name}' is OPEN but _opened_at is None — invariant broken"
                    )
                retry_after = self.open_duration_seconds - (time.monotonic() - self._opened_at)
                raise BreakerOpenError(self.name, max(0.0, retry_after))
            if current == BreakerState.HALF_OPEN:
                if self._probe_in_flight:
                    # Another probe is already in flight; don't stampede.
                    raise BreakerOpenError(self.name, 0.0)
                self._probe_in_flight = True
                is_probe = True

        try:
            result = fn()
            if asyncio.iscoroutine(result):
                result = await result
        except Exception:
            await self._record_failure(was_probe=is_probe)
            raise
        else:
            await self._record_success(was_probe=is_probe)
            return result  # type: ignore[return-value]

    async def _record_failure(self, was_probe: bool = False) -> None:
        async with self._lock:
            now = time.monotonic()
            self._last_failure_ts = now
            self._consecutive_failures += 1
            self._failures.append(now)
            self._prune_failures(now)

            current = self.state
            if current == BreakerState.HALF_OPEN or was_probe:
                # half-open probe failed: re-open and release the probe slot
                self._opened_at = now
                self._failures.clear()
                if was_probe:
                    self._probe_in_flight = False
                return

            if len(self._failures) >= self.failure_threshold:
                self._opened_at = now
                self._failures.clear()

    async def _record_success(self, was_probe: bool = False) -> None:
        async with self._lock:
            now = time.monotonic()
            self._last_success_ts = now
            self._consecutive_failures = 0

            if self.state == BreakerState.HALF_OPEN or was_probe:
                # probe succeeded: close and release the probe slot
                self._opened_at = None
                self._failures.clear()
                if was_probe:
                    self._probe_in_flight = False

    def force_open(self) -> None:
        """Test hook: trip the breaker open immediately."""
        self._opened_at = time.monotonic()

    def status(self) -> dict[str, Any]:
        """Health surface shape per spec §12.4."""
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_failures": self._consecutive_failures,
            "last_failure_ts": self._last_failure_ts,
            "last_success_ts": self._last_success_ts,
        }

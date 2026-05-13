"""Single-probe circuit breaker for Ollama embed calls.

Mirrors the manatee-civic-ai breaker semantics:
- closed → open after `failure_threshold` consecutive failures
- open → half_open after `open_for_seconds` elapses (lazy: triggered by guard())
- half_open → closed on probe success, → open on probe failure
- only one probe allowed in half_open (single-probe enforcement)

Design note: the `state` property reflects the *committed* state (_state field).
The open→half_open transition is NOT lazy in the property; it happens inside
guard() so that tests can assert on state between calls without timing races.
"""
from __future__ import annotations

import time
from typing import Literal

State = Literal["closed", "open", "half_open"]


class EmbeddingBreaker:
    def __init__(self, failure_threshold: int = 3, open_for_seconds: int = 30):
        self._threshold = failure_threshold
        self._open_for = open_for_seconds
        self._state: State = "closed"
        self._consecutive_failures = 0
        self._opened_at: float = 0.0
        self._probe_in_flight = False

    @property
    def state(self) -> State:
        """Return the current committed state. open→half_open transition is driven by guard()."""
        return self._state

    def _timer_expired(self) -> bool:
        return (time.monotonic() - self._opened_at) > self._open_for

    def guard(self) -> None:
        """Raise if the breaker won't allow a call. Transitions open → half_open if expired."""
        if self._state == "open":
            if self._timer_expired():
                self._state = "half_open"
                self._probe_in_flight = True
                return
            raise RuntimeError("Embedding breaker is open — refusing call")
        if self._state == "half_open":
            if self._probe_in_flight:
                raise RuntimeError("Embedding breaker probe in flight — refusing call")
            self._probe_in_flight = True
            return
        # closed — allowed
        return

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._state = "closed"
        self._probe_in_flight = False

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        self._probe_in_flight = False
        if self._consecutive_failures >= self._threshold:
            self._state = "open"
            self._opened_at = time.monotonic()

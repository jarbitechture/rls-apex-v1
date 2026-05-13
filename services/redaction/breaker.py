"""Per-detector circuit breaker registry for the redaction pipeline.

Mirrors services/scraper/breaker.py but uses LLM-appropriate settings:
shorter open_duration_seconds (30s vs 1h) because LLM calls are transient
and retrying sooner is safe for redaction (failures just skip LLM detection).
"""
from __future__ import annotations

from apps.gateway.circuit import CircuitBreaker

_REGISTRY: dict[str, CircuitBreaker] = {}

# LLM calls fail fast and recover fast — 30s open is appropriate.
_BREAKER_DEFAULTS: dict = {
    "failure_threshold": 5,
    "window_seconds": 30.0,
    "open_duration_seconds": 30.0,
}


def get_or_create_breaker(name: str) -> CircuitBreaker:
    """Return (or create) a named circuit breaker for a redaction detector."""
    if name not in _REGISTRY:
        _REGISTRY[name] = CircuitBreaker(
            name=f"redaction_{name}",
            **_BREAKER_DEFAULTS,
        )
    return _REGISTRY[name]

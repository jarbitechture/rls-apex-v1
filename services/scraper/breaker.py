"""Per-host breaker registry. Reuses apps.gateway.circuit.CircuitBreaker so operators have one mental model."""
from __future__ import annotations

from apps.gateway.circuit import CircuitBreaker
from .config import BREAKER_DEFAULTS

_REGISTRY: dict[str, CircuitBreaker] = {}


def get_or_create_breaker(host: str) -> CircuitBreaker:
    if host not in _REGISTRY:
        _REGISTRY[host] = CircuitBreaker(name=f"scrape_{host}", **BREAKER_DEFAULTS)
    return _REGISTRY[host]


def breaker_status_all() -> dict[str, dict]:
    return {host: b.status() for host, b in _REGISTRY.items()}

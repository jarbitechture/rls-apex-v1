"""Per-host breaker registry. Reuses apps.gateway.circuit.CircuitBreaker so operators have one mental model."""
from __future__ import annotations

from apps.gateway.circuit import CircuitBreaker
from .config import BREAKER_DEFAULTS

_REGISTRY: dict[str, CircuitBreaker] = {}


def get_or_create_breaker(host: str) -> CircuitBreaker:
    """Return the breaker for `host`, creating one if missing.

    The returned breaker is async; call sites use `await breaker.call(fn)`
    (see apps.gateway.circuit.breaker). Registry mutation here is sync-only —
    not safe for concurrent coroutines; wrap in a Lock if the scraper ever
    runs sources via asyncio.gather. Names follow the pattern `scrape_{host}`
    for telemetry filtering.
    """
    if host not in _REGISTRY:
        _REGISTRY[host] = CircuitBreaker(name=f"scrape_{host}", **BREAKER_DEFAULTS)
    return _REGISTRY[host]


def breaker_status_all() -> dict[str, dict]:
    """Return per-host breaker status, keyed by host.

    Note: shape is `dict[host_str, status_dict]`, not the `list[dict]` shape
    used by `/api/health/breakers` (apps/gateway/main.py). Task 11 must
    flatten via `list(breaker_status_all().values())` or use a sibling helper.
    """
    return {host: b.status() for host, b in _REGISTRY.items()}

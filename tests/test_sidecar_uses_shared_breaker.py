"""Sidecar client uses the shared circuit breaker library after refactor."""
import pytest

from apps.gateway.sidecar import _client
from apps.gateway.circuit import CircuitBreaker


def test_sidecar_exposes_shared_breaker_instance(tmp_path):
    """The sidecar client must own a CircuitBreaker (not a private rolled state machine)."""
    # The exact constructor name in _client.py may be RoiClient or similar;
    # discover it dynamically.
    candidates = [c for c in dir(_client) if c.lower().endswith("client") and not c.startswith("_")]
    assert candidates, f"no client class found in _client; have: {dir(_client)}"
    ClientCls = getattr(_client, candidates[0])

    # Default fallback_path is /var/log/rls-apex-v1 (production) — override
    # to a writable path so the test focuses on breaker shape, not filesystem perms.
    client = ClientCls(
        endpoint="http://localhost:8000",
        fallback_path=tmp_path / "roi-fallback.jsonl",
    )
    # The breaker may be exposed as `_breaker`, `breaker`, or `circuit_breaker`.
    breaker_attr = next(
        (a for a in ("_breaker", "breaker", "circuit_breaker") if hasattr(client, a)),
        None,
    )
    assert breaker_attr is not None, f"client has no breaker attr; got: {[a for a in dir(client) if 'break' in a.lower()]}"

    breaker = getattr(client, breaker_attr)
    assert isinstance(breaker, CircuitBreaker), f"breaker is {type(breaker)}, expected CircuitBreaker"
    assert breaker.name == "roi_sidecar"
    # Spec §12.1 row "Gateway → manatee-ai-roi POST"
    assert breaker.failure_threshold == 5
    assert breaker.open_duration_seconds == 30.0

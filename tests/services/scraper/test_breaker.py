"""Per-host breaker for scrape sources — wraps apps.gateway.circuit.CircuitBreaker."""
from __future__ import annotations

import pytest

from services.scraper.breaker import get_or_create_breaker, breaker_status_all


def test_get_or_create_returns_same_instance():
    b1 = get_or_create_breaker("municode")
    b2 = get_or_create_breaker("municode")
    assert b1 is b2


def test_status_includes_all_registered():
    get_or_create_breaker("municode")
    get_or_create_breaker("mymanatee")
    get_or_create_breaker("myfloridalegal")
    status = breaker_status_all()
    assert set(status.keys()) >= {"municode", "mymanatee", "myfloridalegal"}
    assert all("state" in v for v in status.values())


def test_breaker_name_follows_scrape_prefix():
    b = get_or_create_breaker("municode")
    assert b.name == "scrape_municode"


def test_breaker_defaults_applied():
    b = get_or_create_breaker("test_defaults_host")
    assert b.failure_threshold == 3
    assert b.window_seconds == 300.0
    assert b.open_duration_seconds == 3600.0


def test_empty_registry_status():
    """Empty status when nothing is registered — verified by isolating in a fresh registry snapshot."""
    from services.scraper import breaker as bk
    saved = bk._REGISTRY.copy()
    bk._REGISTRY.clear()
    try:
        assert bk.breaker_status_all() == {}
    finally:
        bk._REGISTRY.clear()
        bk._REGISTRY.update(saved)

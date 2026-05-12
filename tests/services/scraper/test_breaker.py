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

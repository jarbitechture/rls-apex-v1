"""Per-source config for the scraper service."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceConfig:
    name: str            # logical name used in source_id prefix
    host: str            # host key for breaker registry
    timeout_s: float     # per-request timeout

SOURCES: dict[str, SourceConfig] = {
    "municode_ldc":         SourceConfig("municode_ldc",         "municode",     timeout_s=15.0),
    "municode_ch2_26":      SourceConfig("municode_ch2_26",      "municode",     timeout_s=15.0),
    "mymanatee_ldr":        SourceConfig("mymanatee_ldr",        "mymanatee",    timeout_s=10.0),
    "mymanatee_calendar":   SourceConfig("mymanatee_calendar",   "mymanatee",    timeout_s=10.0),
    "fl_ag_opinions":       SourceConfig("fl_ag_opinions",       "myfloridalegal", timeout_s=15.0),
}

BREAKER_DEFAULTS = {
    "failure_threshold": 3,
    "window_seconds":    300.0,
    "open_duration_seconds": 3600.0,  # 1 hour per spec §4.4
}

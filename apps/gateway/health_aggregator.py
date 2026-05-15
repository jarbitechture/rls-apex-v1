"""W8 — 30s background poller for all v0.2.1a /health endpoints.

Per spec §9. Polls 9 components (3 v0.2.0b tools + 4 new MCP tools + 2
new services) every 30s, caches the result, exposes a snapshot
accessor. The /api/health/aggregated endpoint just returns the cache.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TOOL_HEALTH_ENDPOINTS: dict[str, str] = {
    "validate_rls_structure":         "http://127.0.0.1:30100/health",
    "classify_matter":                "http://127.0.0.1:30101/health",
    "extract_fields":                 "http://127.0.0.1:30102/health",
    "list_rls_precedents":            "http://127.0.0.1:30103/health",
    "get_policy_snippets":            "http://127.0.0.1:30104/health",
    "check_code_enforcement_litigation": "http://127.0.0.1:30105/health",
    "check_urgency_rules":            "http://127.0.0.1:30106/health",
    "scraper_service":                "http://127.0.0.1:30200/health",
    "embedding_service":              "http://127.0.0.1:30201/health",
}


@dataclass
class HealthSnapshot:
    tools: dict[str, dict] = field(default_factory=dict)
    checked_at: Optional[str] = None
    overall_status: str = "unknown"


class HealthAggregator:
    def __init__(
        self,
        endpoints: dict[str, str] = TOOL_HEALTH_ENDPOINTS,
        poll_interval_seconds: float = 30.0,
        per_request_timeout_seconds: float = 5.0,
    ):
        self._endpoints = endpoints
        self._interval = poll_interval_seconds
        self._timeout = per_request_timeout_seconds
        self._snapshot = HealthSnapshot()

    def snapshot(self) -> HealthSnapshot:
        return self._snapshot

    async def poll_once(self) -> None:
        async def fetch_one(name: str, url: str) -> tuple[str, dict]:
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as c:
                    r = await c.get(url)
                if r.status_code == 200:
                    payload = r.json()
                    return name, {**payload, "status": payload.get("status", "healthy")}
                if r.status_code == 503:
                    try:
                        payload = r.json()
                    except Exception:
                        payload = {}
                    return name, {**payload, "status": payload.get("status", "degraded")}
                return name, {"status": "degraded", "http_status": r.status_code}
            except Exception as e:
                return name, {"status": "unreachable", "error": str(e)}

        results = await asyncio.gather(
            *(fetch_one(n, u) for n, u in self._endpoints.items()),
            return_exceptions=False,
        )
        tools = dict(results)
        overall = "healthy" if all(t.get("status") == "healthy" for t in tools.values()) else "degraded"
        self._snapshot = HealthSnapshot(
            tools=tools,
            checked_at=datetime.now(timezone.utc).isoformat(),
            overall_status=overall,
        )

    async def run_forever(self) -> None:
        while True:
            try:
                await self.poll_once()
            except Exception:
                logger.exception("health aggregator poll failed")
            await asyncio.sleep(self._interval)

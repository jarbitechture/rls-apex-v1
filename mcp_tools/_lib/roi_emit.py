"""Per-tool ROI emit client.

Each MCP tool runs as its own process, so it can't share the gateway's
RoiClient. Instead, it emits via the same Architecture A+ pattern (POST
manatee-ai-roi FastAPI; JSONL fallback on breaker open).

Reuses apps.gateway.circuit.CircuitBreaker — same pattern as the
gateway's sidecar so operators have one mental model.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx

from apps.gateway.circuit import BreakerOpenError, CircuitBreaker
from apps.gateway.sidecar._client import validate_event_for_persistence

ROI_ENDPOINT = os.environ.get("ROI_EVENTS_URL", "http://localhost:8000")
ROI_FALLBACK_PATH = Path(
    os.environ.get("ROI_FALLBACK_PATH", "/var/log/rls-apex-v1/roi-fallback.jsonl")
)


class ToolRoiEmitter:
    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        self._breaker = CircuitBreaker(
            name=f"roi_emit_{tool_name}",
            failure_threshold=5,
            window_seconds=30.0,
            open_duration_seconds=30.0,
        )

    def breaker_status(self) -> dict[str, Any]:
        """Surface for /health endpoint per spec §12.4."""
        return self._breaker.status()

    async def emit(self, event_kind: str, payload: dict[str, Any]) -> None:
        """Fire-and-forget — never raises."""
        full_event = {
            "event_kind": event_kind,
            "tool": self.tool_name,
            **payload,
        }
        validate_event_for_persistence(full_event)
        try:
            await self._breaker.call(lambda: self._post(full_event))
        except BreakerOpenError:
            self._fallback(full_event)
        except Exception:
            # _post raised — breaker recorded the failure. Fall through to local JSONL.
            self._fallback(full_event)

    async def _post(self, event: dict) -> None:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.post(f"{ROI_ENDPOINT}/events", json=event)
            r.raise_for_status()

    def _fallback(self, event: dict) -> None:
        try:
            ROI_FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
            with ROI_FALLBACK_PATH.open("a") as f:
                f.write(json.dumps(event) + "\n")
        except OSError:
            # Last-resort: emit silently dropped. Don't raise from emit().
            pass

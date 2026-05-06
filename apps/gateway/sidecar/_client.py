"""Vendored A+ ROI sidecar client.

Mirrors `manatee_ai_roi.sidecar.A_Plus_Client` (canonical at
~/Projects/manatee-ai-roi/src/manatee_ai_roi/sidecar.py) but stays
self-contained so rls-apex-v1's deploy doesn't depend on the
manatee_ai_roi Python package being installed on the same host
(per Lock #1 spirit and DECISION_LOG D-001).

Pattern: Architecture A+ — POST primary, local-fallback JSONL on this
host when the breaker opens, background drain when the breaker recovers.

Telemetry NEVER blocks the user-facing action (Operating Rule #18).

Schema contract: apps/gateway/sidecar/manatee_ai_roi.schema.json
(regenerated from the canonical Pydantic model in manatee_ai_roi).
Drift between this client and the schema is caught by CI in the
manatee_ai_roi repo (tests/test_json_schema_drift.py).
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

import httpx


logger = logging.getLogger("rls_apex.sidecar")


# ─── EventKind (mirrors manatee_ai_roi.schema.EventKind) ──────────────────────

EVENT_KIND_LLM_CALL = "llm_call"
EVENT_KIND_TOOL_INVOCATION = "tool_invocation"
EVENT_KIND_GPT_PICK = "gpt_pick"
EVENT_KIND_PROJECT_ACCESS = "project_access"
EVENT_KIND_FILE_INTERACTION = "file_interaction"
EVENT_KIND_RAG_HIT = "rag_hit"
EVENT_KIND_LICENSE_LIFECYCLE = "license_lifecycle"
EVENT_KIND_HEADCOUNT_ATTESTATION = "headcount_attestation"
EVENT_KIND_FEEDBACK = "feedback"
EVENT_KIND_ESCALATION = "escalation"
EVENT_KIND_TRAINING_INTERACTION = "training_interaction"

VALID_EVENT_KINDS = frozenset({
    EVENT_KIND_LLM_CALL,
    EVENT_KIND_TOOL_INVOCATION,
    EVENT_KIND_GPT_PICK,
    EVENT_KIND_PROJECT_ACCESS,
    EVENT_KIND_FILE_INTERACTION,
    EVENT_KIND_RAG_HIT,
    EVENT_KIND_LICENSE_LIFECYCLE,
    EVENT_KIND_HEADCOUNT_ATTESTATION,
    EVENT_KIND_FEEDBACK,
    EVENT_KIND_ESCALATION,
    EVENT_KIND_TRAINING_INTERACTION,
})


# ─── Defaults (per spec §9 sign-off) ──────────────────────────────────────────

DEFAULT_FALLBACK_PATH = Path("/var/log/rls-apex-v1/roi-fallback.jsonl")
DEFAULT_POST_TIMEOUT_S = 3.0
DEFAULT_DRAIN_INTERVAL_S = 60.0
FAILURE_THRESHOLD = 5
COOLDOWN_S = 30.0


# ─── Breaker ──────────────────────────────────────────────────────────────────


class BreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class _Breaker:
    state: BreakerState = BreakerState.CLOSED
    failures: int = 0
    opened_at: float = 0.0
    dropped_count: int = 0


@dataclass
class _DrainStats:
    last_drain_ts: float | None = None
    last_drain_count: int = 0
    drained_total: int = 0


# ─── Validation ───────────────────────────────────────────────────────────────


_REQUIRED_KEYS = {
    "event_kind", "workflow", "user_id", "dept", "role_band",
    "task_type", "tool", "success",
}


def validate_event_for_persistence(event: dict) -> None:
    """Raise ValueError if `event` isn't in a persistable state.

    Mirrors RoiEvent.validate_for_persistence() in manatee_ai_roi/schema.py.
    """
    missing = _REQUIRED_KEYS - event.keys()
    if missing:
        raise ValueError(f"missing required fields: {sorted(missing)}")
    kind = event.get("event_kind")
    if kind not in VALID_EVENT_KINDS:
        raise ValueError(f"invalid event_kind: {kind!r}")
    if kind == EVENT_KIND_LLM_CALL:
        if event.get("prompt_tokens") is None or event.get("output_tokens") is None:
            raise ValueError(
                "event_kind=llm_call requires both prompt_tokens and output_tokens"
            )


# ─── Fallback queue (append-only JSONL, thread-safe) ──────────────────────────


class _FallbackQueue:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def append(self, event: dict) -> None:
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def count(self) -> int:
        if not self.path.exists():
            return 0
        with self._lock, self.path.open("r", encoding="utf-8") as f:
            return sum(1 for _ in f)

    def drain(self, post_fn) -> tuple[int, int]:
        """Replay queued events. `post_fn(json_str)` returns bool.

        Returns (drained, remaining). Halts on first False.
        """
        with self._lock:
            if not self.path.exists():
                return 0, 0
            with self.path.open("r", encoding="utf-8") as f:
                lines = [line.rstrip("\n") for line in f if line.strip()]
            drained = 0
            for i, line in enumerate(lines):
                try:
                    ok = post_fn(line)
                except Exception:
                    ok = False
                if not ok:
                    remaining = lines[i:]
                    with self.path.open("w", encoding="utf-8") as f:
                        for rem in remaining:
                            f.write(rem + "\n")
                    return drained, len(remaining)
                drained += 1
            self.path.write_text("", encoding="utf-8")
            return drained, 0


# ─── RoiClient (async) ────────────────────────────────────────────────────────


class RoiClient:
    """Async A+ client for emitting ROI events from the gateway.

    One instance per process. Initialize in FastAPI's lifespan and store in
    `app.state.roi_client`. emit_now() is fire-and-forget — never blocks.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        fallback_path: str | Path = DEFAULT_FALLBACK_PATH,
        timeout_s: float = DEFAULT_POST_TIMEOUT_S,
        drain_interval_s: float = DEFAULT_DRAIN_INTERVAL_S,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout_s = timeout_s
        self.drain_interval_s = drain_interval_s
        self.fallback = _FallbackQueue(fallback_path)
        self.breaker = _Breaker()
        self.stats = _DrainStats()
        self._client = httpx.AsyncClient(timeout=timeout_s)
        self._drain_task: asyncio.Task | None = None

    # — lifecycle —

    async def start_drain_loop(self) -> None:
        if self._drain_task is None or self._drain_task.done():
            self._drain_task = asyncio.create_task(self._drain_loop())

    async def close(self) -> None:
        if self._drain_task is not None:
            self._drain_task.cancel()
            try:
                await self._drain_task
            except (asyncio.CancelledError, Exception):
                pass
        await self._client.aclose()

    # — public API —

    def emit_now(self, event: dict) -> None:
        """Fire-and-forget. Schedules an async POST + fallback path.

        Sync API so existing call sites (`emit_roi(event)`) don't change.
        """
        if "started_at" not in event:
            event["started_at"] = datetime.now(timezone.utc).isoformat()
        if "event_id" not in event:
            event["event_id"] = _new_event_id()
        try:
            asyncio.create_task(self._dispatch(event))
        except RuntimeError:
            # No running event loop (e.g., shutdown). Drop fail-open.
            self.breaker.dropped_count += 1

    async def emit_now_async(self, event: dict) -> None:
        """Awaitable variant. Use when you want to ensure dispatch completes."""
        if "started_at" not in event:
            event["started_at"] = datetime.now(timezone.utc).isoformat()
        if "event_id" not in event:
            event["event_id"] = _new_event_id()
        await self._dispatch(event)

    def breaker_status(self) -> dict:
        return {
            "state": self.breaker.state.value,
            "consecutive_failures": self.breaker.failures,
            "dropped_events_total": self.breaker.dropped_count,
            "fallback_count": self.fallback.count(),
            "last_drain_ts": self.stats.last_drain_ts,
            "last_drain_count": self.stats.last_drain_count,
            "drained_total": self.stats.drained_total,
        }

    async def drain_now(self) -> tuple[int, int]:
        if self.breaker.state != BreakerState.CLOSED and not self._can_probe():
            return 0, self.fallback.count()
        # Wrap async POST as sync callback for FallbackQueue.drain
        loop = asyncio.get_event_loop()

        def _sync_post(json_line: str) -> bool:
            return loop.run_until_complete(self._post_raw_line(json_line))

        # Drain inline using async fold (avoid run_until_complete inside loop)
        drained, remaining = await self._async_drain()
        self.stats.last_drain_ts = time.time()
        self.stats.last_drain_count = drained
        self.stats.drained_total += drained
        return drained, remaining

    # — internals —

    async def _dispatch(self, event: dict) -> None:
        try:
            validate_event_for_persistence(event)
        except ValueError as exc:
            logger.debug("RoiClient: invalid event dropped pre-flight: %s", exc)
            self.breaker.dropped_count += 1
            return

        if not self._can_attempt():
            self.fallback.append(event)
            return

        ok = await self._post(event)
        if ok:
            self._record_success()
        else:
            self.fallback.append(event)
            self._record_failure()

    def _can_attempt(self) -> bool:
        if self.breaker.state == BreakerState.CLOSED:
            return True
        if self.breaker.state == BreakerState.OPEN:
            if time.monotonic() - self.breaker.opened_at >= COOLDOWN_S:
                self.breaker.state = BreakerState.HALF_OPEN
                return True
            return False
        return True  # HALF_OPEN

    def _can_probe(self) -> bool:
        if self.breaker.state == BreakerState.OPEN:
            if time.monotonic() - self.breaker.opened_at >= COOLDOWN_S:
                self.breaker.state = BreakerState.HALF_OPEN
                return True
        return False

    async def _post(self, event: dict) -> bool:
        try:
            r = await self._client.post(f"{self.endpoint}/v1/events", json=event)
            return 200 <= r.status_code < 300
        except (httpx.HTTPError, httpx.TimeoutException, OSError) as exc:
            logger.debug("RoiClient: POST failed: %s", exc)
            return False

    async def _post_raw_line(self, json_line: str) -> bool:
        try:
            r = await self._client.post(
                f"{self.endpoint}/v1/events",
                content=json_line,
                headers={"content-type": "application/json"},
            )
            return 200 <= r.status_code < 300
        except (httpx.HTTPError, httpx.TimeoutException, OSError):
            return False

    async def _async_drain(self) -> tuple[int, int]:
        # Read all lines under lock, then post one-at-a-time async
        if not self.fallback.path.exists():
            return 0, 0
        with self.fallback._lock:
            with self.fallback.path.open("r", encoding="utf-8") as f:
                lines = [line.rstrip("\n") for line in f if line.strip()]
        drained = 0
        for i, line in enumerate(lines):
            ok = await self._post_raw_line(line)
            if not ok:
                remaining = lines[i:]
                with self.fallback._lock:
                    with self.fallback.path.open("w", encoding="utf-8") as f:
                        for rem in remaining:
                            f.write(rem + "\n")
                return drained, len(remaining)
            drained += 1
        with self.fallback._lock:
            self.fallback.path.write_text("", encoding="utf-8")
        return drained, 0

    async def _drain_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.drain_interval_s)
                if self.breaker.state == BreakerState.CLOSED:
                    if self.fallback.count() > 0:
                        await self.drain_now()
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.debug("RoiClient: drain loop error: %s", exc)

    def _record_success(self) -> None:
        self.breaker.state = BreakerState.CLOSED
        self.breaker.failures = 0

    def _record_failure(self) -> None:
        self.breaker.failures += 1
        self.breaker.dropped_count += 1
        if self.breaker.state == BreakerState.HALF_OPEN:
            self.breaker.state = BreakerState.OPEN
            self.breaker.opened_at = time.monotonic()
        elif self.breaker.failures >= FAILURE_THRESHOLD:
            self.breaker.state = BreakerState.OPEN
            self.breaker.opened_at = time.monotonic()


def _new_event_id() -> str:
    import uuid
    return str(uuid.uuid4())

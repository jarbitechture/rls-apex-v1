"""Each gateway action lands a ROI event in the JSONL fallback (Architecture A+).

Non-vacuous: the test owns its RoiClient instance (patched into the module
global) so it can control endpoint + fallback_path without relying on lifespan.
The httpx ASGITransport client fixture does NOT run FastAPI lifespan, so the
module-level `_roi_client` stays None without the patch.
"""
import asyncio
import json
import time
from pathlib import Path

import pytest

from apps.gateway.sidecar._client import RoiClient, validate_event_for_persistence


@pytest.fixture()
async def _roi_client_with_fallback(tmp_path, monkeypatch):
    """Create a real RoiClient pointing at an unreachable endpoint.

    Patches apps.gateway.main._roi_client so emit_roi() routes through it.
    Yields the fallback Path so assertions can read it.
    """
    import apps.gateway.main as gw_main

    fallback_path = tmp_path / "roi.jsonl"
    roi_client = RoiClient(
        endpoint="http://127.0.0.1:1",  # unreachable → forces fallback on every POST
        fallback_path=fallback_path,
    )
    await roi_client.start_drain_loop()

    # Patch the module global. monkeypatch.setattr restores on teardown.
    monkeypatch.setattr(gw_main, "_roi_client", roi_client)

    yield fallback_path

    await roi_client.close()


async def _wait_for_fallback(fallback: Path, min_lines: int = 1, timeout_s: float = 5.0) -> None:
    """Poll until fallback exists and has at least `min_lines` non-empty lines.

    emit_now() is fire-and-forget (asyncio.create_task), so the fallback write
    happens asynchronously after each client.post() returns. Polling-with-
    deadline avoids magic sleeps and is stable on a healthy system.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if fallback.exists():
            lines = [l for l in fallback.read_text().splitlines() if l.strip()]
            if len(lines) >= min_lines:
                return
        await asyncio.sleep(0.05)
    # Timeout: let assertions handle the failure message.


@pytest.mark.asyncio
async def test_intake_writes_roi_event_to_fallback_when_sidecar_unreachable(
    client, _roi_client_with_fallback
):
    """Strict (non-vacuous) assertion: /api/intake writes a valid persistable ROI event.

    Architecture A+: when the sidecar HTTP target is unreachable, emit_roi()
    must write the event to the JSONL fallback file. This test was previously
    vacuous (the fallback file never existed because _roi_client was None during
    tests — lifespan doesn't run under httpx ASGITransport). The fixture now
    owns and patches the client, so the full path from gateway → sidecar →
    fallback is exercised.

    RED state (pre-Task-1): emit_roi() calls had missing required schema fields
    → validate_event_for_persistence raised → events dropped pre-flight → fallback
    file empty → assertion fails. This test therefore fails without Task 1's fix.
    """
    fallback = _roi_client_with_fallback

    # Single call is sufficient: each POST failure writes to fallback immediately.
    response = await client.post("/api/intake", json={"text": "permit denial"})
    assert response.status_code == 200

    # Wait for the fire-and-forget dispatch task to complete.
    await _wait_for_fallback(fallback, min_lines=1)

    # ── Assertion 1: file exists ───────────────────────────────────────────────
    assert fallback.exists(), (
        "ROI fallback file does not exist — either emit_roi() was never called "
        "(check _roi_client patch) or events were dropped pre-flight by validate_event_for_persistence"
    )

    # ── Assertion 2: at least one non-empty line ───────────────────────────────
    raw_lines = [l for l in fallback.read_text().splitlines() if l.strip()]
    assert len(raw_lines) >= 1, (
        f"fallback file exists but contains 0 non-empty lines; content: {fallback.read_text()!r}"
    )

    # ── Assertion 3: every line is valid JSON ─────────────────────────────────
    events = []
    for i, line in enumerate(raw_lines):
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            pytest.fail(f"line {i} is not valid JSON: {exc!r}\nline: {line!r}")

    # ── Assertion 4: every event passes validate_event_for_persistence ─────────
    for i, event in enumerate(events):
        try:
            validate_event_for_persistence(event)
        except ValueError as exc:
            pytest.fail(
                f"event at line {i} fails validate_event_for_persistence: {exc}\n"
                f"event: {json.dumps(event, indent=2)}"
            )

    # ── Assertion 5: at least one event is from rls_apex.intake ───────────────
    intake_events = [e for e in events if e.get("workflow") == "rls_apex.intake"]
    assert intake_events, (
        f"no event with workflow=='rls_apex.intake' found in fallback.\n"
        f"workflows present: {[e.get('workflow') for e in events]}"
    )

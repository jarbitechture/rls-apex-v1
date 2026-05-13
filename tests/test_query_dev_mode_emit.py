"""/api/query DEV_MODE — ROI emit + TAC-03 refusal contract.

Task 6 (happy path): emits a ROI event after SSE stream close, all 8 required
fields, tool='rls_apex', workflow='rls_apex.query', success=True.

TAC-03 (refusal path, Lock #19): when retrieval returns zero relevant chunks
the gateway returns HTTP 200 with a structured refusal body
(`{"refused": true, "reason": "no_grounding", "message": "..."}`) and emits
exactly one ROI event with event_kind='escalation', success=False, and
extra.refusal_reason='no_grounding'. No tokens are streamed. Same shape when
retrieval raises — telemetry never blocks the user-facing action (Rule #18).

surface='other' (NOT 'api'): the dispatch contract specified surface='api'
but that value is not in the schema enum (word, excel, outlook, teams,
copilot_chat, chatgpt_web, cookbook_ui, other). Existing emit sites in
main.py also use 'other'. Schema is primary source.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

import apps.gateway.main as gateway_main
from apps.gateway.retrieval.retrieve import Citation
from apps.gateway.sidecar._client import validate_event_for_persistence


def _fake_citation() -> Citation:
    """Minimum-viable Citation that proves retrieval returned ≥1 hit."""
    return Citation(
        id="RLS-TEST-0001",
        source="test-corpus",
        source_kind="opinion",
        pinpoint="p. 1",
        excerpt="Test precedent excerpt for happy-path retrieval.",
        score=0.9,
    )


@pytest.mark.asyncio
async def test_query_dev_mode_emits_valid_roi_event(client) -> None:
    """DEV_MODE /api/query emits a compliant ROI event after stream exhaustion.

    Patches `_corpus_retrieve` to return one fake hit — otherwise the empty
    test-env corpus triggers the TAC-03 refusal path (covered by separate
    tests below) instead of the streaming path under test here.
    """
    captured: list[dict] = []

    def _fake_emit_roi(event: dict) -> None:
        captured.append(event)

    with (
        patch.object(gateway_main, "DEV_MODE", True),
        patch.object(gateway_main, "emit_roi", _fake_emit_roi),
        patch.object(gateway_main, "_corpus_retrieve",
                     lambda *a, **kw: [_fake_citation()]),
    ):
        response = await client.post(
            "/api/query",
            json={"q": "What are the procurement rules for contracts over $50k?"},
        )

    # Stream consumed fully — response should be 200 with SSE content-type
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    # ROI event must have been emitted exactly once
    assert len(captured) == 1, (
        f"Expected 1 ROI event, got {len(captured)}: {captured!r}"
    )
    event = captured[0]

    # Must pass the pre-flight schema validator
    validate_event_for_persistence(event)

    # Field value assertions per ADR-001 + ADR-003
    assert event["tool"] == "rls_apex", f"tool must be 'rls_apex', got {event['tool']!r}"
    assert event["workflow"] == "rls_apex.query", (
        f"workflow must be 'rls_apex.query', got {event['workflow']!r}"
    )
    assert event["event_kind"] == "tool_invocation", (
        f"event_kind must be 'tool_invocation', got {event['event_kind']!r}"
    )
    assert event["success"] is True, "success must be True on happy path"
    assert event["user_id"] == "test@local", (
        f"user_id must match fixture UPN, got {event['user_id']!r}"
    )


@pytest.mark.asyncio
async def test_query_refuses_when_retrieval_returns_zero_chunks(client) -> None:
    """TAC-03 / Lock #19: empty retrieval → structured refusal + escalation event.

    Asserts the validator framing: no grounding means no critique. The
    gateway returns HTTP 200 with `{refused, reason, message}` (NOT a 4xx —
    a 4xx would signal client error; refusal is a deliberate, semantic
    response). One ROI escalation event is emitted, success=False.
    """
    captured: list[dict] = []

    def _fake_emit_roi(event: dict) -> None:
        captured.append(event)

    with (
        patch.object(gateway_main, "DEV_MODE", True),
        patch.object(gateway_main, "emit_roi", _fake_emit_roi),
        patch.object(gateway_main, "_corpus_retrieve", lambda *a, **kw: []),
    ):
        response = await client.post(
            "/api/query",
            json={"q": "Some question with no precedent in the corpus."},
        )

    # Refusal is a deliberate semantic response, not an HTTP error.
    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("application/json"), (
        f"refusal must be JSON (not SSE), got "
        f"{response.headers.get('content-type')!r}"
    )

    body = response.json()
    assert body == {
        "refused": True,
        "reason": "no_grounding",
        "message": body["message"],  # human text — assert presence + non-empty
    }, f"refusal body shape mismatch: {body!r}"
    assert isinstance(body["message"], str) and body["message"].strip(), (
        "message must be a non-empty human-readable string"
    )

    # Exactly one ROI event, schema-valid, with refusal markers.
    assert len(captured) == 1, (
        f"Expected exactly 1 ROI event on refusal, got {len(captured)}: "
        f"{captured!r}"
    )
    event = captured[0]
    validate_event_for_persistence(event)

    assert event["event_kind"] == "escalation", (
        f"event_kind must be 'escalation' (closest valid enum for refusal), "
        f"got {event['event_kind']!r}"
    )
    assert event["success"] is False, (
        "success must be False on refusal — Rule #18 success field reflects "
        "whether the user got a useful result, not whether telemetry worked"
    )
    assert event["tool"] == "rls_apex", f"tool must be 'rls_apex', got {event['tool']!r}"
    assert event["surface"] == "other", (
        f"surface must be 'other' (schema enum has no 'api' value), "
        f"got {event['surface']!r}"
    )
    assert event["workflow"] == "rls_apex.query", (
        f"workflow must be 'rls_apex.query', got {event['workflow']!r}"
    )
    assert event.get("extra", {}).get("refusal_reason") == "no_grounding", (
        f"extra.refusal_reason must be 'no_grounding', "
        f"got {event.get('extra', {}).get('refusal_reason')!r}"
    )

    # User's query text MUST NOT appear in the ROI payload (PII surface —
    # forbidden by the dispatch contract). Defensive check.
    serialised = repr(event)
    assert "Some question with no precedent" not in serialised, (
        "Refusal ROI event leaked user query text into extra/metadata"
    )


@pytest.mark.asyncio
async def test_query_refuses_when_retrieval_raises(client) -> None:
    """Edge: retrieval raises (e.g., breaker open) → still refuse + emit ROI.

    Rule #18: telemetry never blocks the user-facing action. The user gets
    a refusal response regardless of whether retrieval blew up; the ROI
    emit is fire-and-forget and records success=False.
    """
    captured: list[dict] = []

    def _fake_emit_roi(event: dict) -> None:
        captured.append(event)

    def _boom(*a, **kw):
        raise RuntimeError("retrieval breaker open (simulated)")

    with (
        patch.object(gateway_main, "DEV_MODE", True),
        patch.object(gateway_main, "emit_roi", _fake_emit_roi),
        patch.object(gateway_main, "_corpus_retrieve", _boom),
    ):
        response = await client.post(
            "/api/query",
            json={"q": "Anything — retrieval will raise."},
        )

    # User STILL gets the refusal — no 5xx leak.
    assert response.status_code == 200, (
        f"User-facing response must not surface retrieval errors as 5xx; "
        f"got {response.status_code}"
    )
    body = response.json()
    assert body["refused"] is True
    assert body["reason"] == "no_grounding"

    # ROI still emits with success=False (telemetry never blocks).
    assert len(captured) == 1, (
        f"Expected exactly 1 ROI event when retrieval raises, "
        f"got {len(captured)}: {captured!r}"
    )
    event = captured[0]
    validate_event_for_persistence(event)
    assert event["event_kind"] == "escalation"
    assert event["success"] is False
    assert event.get("extra", {}).get("refusal_reason") == "no_grounding"

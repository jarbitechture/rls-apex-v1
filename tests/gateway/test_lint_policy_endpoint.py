"""Tests for POST /api/lint/policy (Plan D Task 5 — L14 policy lint endpoint).

Three coverage cases:
  1. Violation detected — LLM returns JSON with violation=true; suggestions populated.
  2. No violation — LLM returns violation=false; suggestions empty.
  3. LLM unavailable — complete_sync raises RuntimeError; endpoint returns 503.

Patching strategy (OVERRIDE #2):
  - patch apps.gateway.main._call_l4_get_policy_snippets (async)
  - patch apps.gateway.main.complete_sync (async)
  - patch apps.gateway.main.emit_roi (sync, single dict arg)

No tests/gateway/__init__.py — pytest uses rootdir-based collection (OVERRIDE #5).
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


_FAKE_SNIPPETS_RESP = {
    "snippets": [
        {
            "citation": "LDC §4.3.2",
            "body": "Applicants must disclose all pending litigation within 30 days.",
            "source_type": "ldc",
        },
        {
            "citation": "Ord. 2022-11 §2",
            "body": "Legal questions must identify the specific ordinance at issue.",
            "source_type": "ordinance",
        },
    ],
    "procedure_corpus_pending": True,
}

_PAYLOAD = {
    "rlsPayload": {
        "factualBackground": "The applicant failed to disclose pending litigation.",
        "legalQuestion": "Does the zoning ordinance apply retroactively?",
    }
}


@pytest.mark.asyncio
async def test_lint_policy_violation_detected():
    """LLM identifies a violation — suggestions list is populated."""
    from apps.gateway.main import app, current_user

    llm_response = json.dumps({
        "violation": True,
        "rule_citation": "LDC §4.3.2",
        "field": "factualBackground",
        "explanation": "Applicant did not disclose pending litigation as required.",
    })

    async def fake_call_l4(topic_or_field: str, k: int = 3) -> dict:
        return _FAKE_SNIPPETS_RESP

    async def fake_llm_complete(system: str, user: str, **kwargs) -> str:
        return llm_response

    captured_emits: list[dict] = []

    def capture_emit(event: dict) -> None:
        captured_emits.append(event)

    def _fake_user() -> dict:
        return {
            "upn": "test@local",
            "display_name": "Test User",
            "role": "general-counsel",
            "dept": "DEV",
            "role_band": "professional",
        }

    app.dependency_overrides[current_user] = _fake_user
    try:
        with patch("apps.gateway.main._call_l4_get_policy_snippets", fake_call_l4), \
             patch("apps.gateway.main._complete_sync", fake_llm_complete), \
             patch("apps.gateway.main.emit_roi", capture_emit):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                r = await ac.post("/api/lint/policy", json=_PAYLOAD)
    finally:
        app.dependency_overrides.pop(current_user, None)

    assert r.status_code == 200
    body = r.json()
    assert len(body["suggestions"]) == 1
    suggestion = body["suggestions"][0]
    assert suggestion["ruleId"] == "policy-lint-llm"
    assert suggestion["field"] == "factualBackground"
    assert suggestion["citation"] == "LDC §4.3.2"
    assert suggestion["severity"] == "info"

    # ROI event must have been emitted with correct shape
    assert len(captured_emits) == 1
    evt = captured_emits[0]
    assert evt["event_kind"] == "llm_call"
    assert evt["workflow"] == "rls_apex"
    assert "prompt_tokens" in evt
    assert "output_tokens" in evt
    assert evt["task_type"] == "policy_lint"


@pytest.mark.asyncio
async def test_lint_policy_no_violation():
    """LLM finds no violation — suggestions list is empty."""
    from apps.gateway.main import app, current_user

    async def fake_call_l4(topic_or_field: str, k: int = 3) -> dict:
        return _FAKE_SNIPPETS_RESP

    async def fake_llm_complete(system: str, user: str, **kwargs) -> str:
        return '{"violation": false}'

    captured_emits: list[dict] = []

    def capture_emit(event: dict) -> None:
        captured_emits.append(event)

    def _fake_user() -> dict:
        return {
            "upn": "test@local",
            "display_name": "Test User",
            "role": "general-counsel",
            "dept": "DEV",
            "role_band": "professional",
        }

    app.dependency_overrides[current_user] = _fake_user
    try:
        with patch("apps.gateway.main._call_l4_get_policy_snippets", fake_call_l4), \
             patch("apps.gateway.main._complete_sync", fake_llm_complete), \
             patch("apps.gateway.main.emit_roi", capture_emit):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                r = await ac.post("/api/lint/policy", json=_PAYLOAD)
    finally:
        app.dependency_overrides.pop(current_user, None)

    assert r.status_code == 200
    body = r.json()
    assert body["suggestions"] == []
    # ROI still emitted even when no violation
    assert len(captured_emits) == 1
    assert captured_emits[0]["event_kind"] == "llm_call"


@pytest.mark.asyncio
async def test_lint_policy_llm_unavailable():
    """complete_sync raises RuntimeError — endpoint returns 503."""
    from apps.gateway.main import app, current_user

    async def fake_call_l4(topic_or_field: str, k: int = 3) -> dict:
        return _FAKE_SNIPPETS_RESP

    async def fake_llm_complete(system: str, user: str, **kwargs) -> str:
        raise RuntimeError("llm breaker open")

    def _fake_user() -> dict:
        return {
            "upn": "test@local",
            "display_name": "Test User",
            "role": "general-counsel",
            "dept": "DEV",
            "role_band": "professional",
        }

    app.dependency_overrides[current_user] = _fake_user
    try:
        with patch("apps.gateway.main._call_l4_get_policy_snippets", fake_call_l4), \
             patch("apps.gateway.main._complete_sync", fake_llm_complete):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as ac:
                r = await ac.post("/api/lint/policy", json=_PAYLOAD)
    finally:
        app.dependency_overrides.pop(current_user, None)

    assert r.status_code == 503
    assert "policy lint llm unavailable" in r.json()["detail"]

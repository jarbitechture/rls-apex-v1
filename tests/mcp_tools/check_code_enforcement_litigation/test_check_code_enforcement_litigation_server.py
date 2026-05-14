"""check_code_enforcement_litigation MCP tool — unit tests.

Plan D Task 1. Seven tests covering:
1. Non-CE matter_type → applicable=False, no blocking rules.
2. NOV referenced without date → CE_NOV_DATE_MISSING blocking.
3. NOV with year in reference → CE_NOV_DATE_MISSING NOT triggered.
4. NOV with ISO date form → CE_NOV_DATE_MISSING NOT triggered.
5. Special magistrate hearing without deadline → CE_HEARING_DEADLINE_MISSING blocking.
6. Special magistrate hearing with deadline → CE_HEARING_DEADLINE_MISSING NOT triggered.
7. ROI tool_invocation event emitted with correct fields on success.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import mcp_tools.check_code_enforcement_litigation.server as server


def _make_actor(actor_id: str = "tester@manatee.local") -> MagicMock:
    actor = MagicMock()
    actor.actor_id = actor_id
    return actor


# ---------------------------------------------------------------------------
# Test 1: non-CE matter_type → applicable=False immediately
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_applicable_false_when_matter_type_not_ce():
    """matter_type != 'code_enforcement_litigation' → applicable=False, empty blocking."""
    actor = _make_actor()

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock()),
    ):
        result = await server.check_code_enforcement_litigation(
            rls_payload={"factualBackground": "some text"},
            matter_type="permit_or_zoning",
        )

    assert result["applicable"] is False
    assert result["blocking"] == []
    assert result["warnings"] == []


# ---------------------------------------------------------------------------
# Test 2: NOV referenced without date → CE_NOV_DATE_MISSING blocked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocks_when_nov_referenced_without_date():
    """NOV mention without any date → CE_NOV_DATE_MISSING must appear in blocking."""
    actor = _make_actor()

    payload = {
        "factualBackground": "The NOV was issued and remains outstanding.",
        "deadline": None,
    }

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock()),
    ):
        result = await server.check_code_enforcement_litigation(
            rls_payload=payload,
            matter_type="code_enforcement_litigation",
        )

    codes = [b["code"] for b in result["blocking"]]
    assert "CE_NOV_DATE_MISSING" in codes, (
        f"Expected CE_NOV_DATE_MISSING in blocking codes, got: {codes}"
    )
    # Confirm field tag
    nov_block = next(b for b in result["blocking"] if b["code"] == "CE_NOV_DATE_MISSING")
    assert nov_block["field"] == "factualBackground"


# ---------------------------------------------------------------------------
# Test 3: NOV with year reference → CE_NOV_DATE_MISSING NOT triggered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_passes_when_nov_has_date_2026():
    """NOV-2026-117 (year in reference) satisfies the date requirement."""
    actor = _make_actor()

    payload = {
        "factualBackground": (
            "NOV-2026-117 dated January 15 2026 was served on the property owner."
        ),
    }

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock()),
    ):
        result = await server.check_code_enforcement_litigation(
            rls_payload=payload,
            matter_type="code_enforcement_litigation",
        )

    codes = [b["code"] for b in result["blocking"]]
    assert "CE_NOV_DATE_MISSING" not in codes, (
        f"CE_NOV_DATE_MISSING must not be triggered when date is present, got: {codes}"
    )


# ---------------------------------------------------------------------------
# Test 4: NOV with ISO date form → CE_NOV_DATE_MISSING NOT triggered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_passes_when_nov_dated_with_iso_form():
    """NOV with 'dated 2026-01-15' ISO form satisfies the date requirement."""
    actor = _make_actor()

    payload = {
        "factualBackground": "A notice of violation dated 2026-01-15 was recorded.",
    }

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock()),
    ):
        result = await server.check_code_enforcement_litigation(
            rls_payload=payload,
            matter_type="code_enforcement_litigation",
        )

    codes = [b["code"] for b in result["blocking"]]
    assert "CE_NOV_DATE_MISSING" not in codes, (
        f"CE_NOV_DATE_MISSING must not fire for ISO-dated NOV, got: {codes}"
    )


# ---------------------------------------------------------------------------
# Test 5: Special magistrate hearing without deadline → CE_HEARING_DEADLINE_MISSING
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blocks_when_special_magistrate_hearing_pending_no_deadline():
    """Special magistrate hearing pending without deadline → CE_HEARING_DEADLINE_MISSING."""
    actor = _make_actor()

    payload = {
        "factualBackground": (
            "Special magistrate hearing is pending review of the violation."
        ),
    }

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock()),
    ):
        result = await server.check_code_enforcement_litigation(
            rls_payload=payload,
            matter_type="code_enforcement_litigation",
        )

    codes = [b["code"] for b in result["blocking"]]
    assert "CE_HEARING_DEADLINE_MISSING" in codes, (
        f"Expected CE_HEARING_DEADLINE_MISSING, got: {codes}"
    )
    deadline_block = next(
        b for b in result["blocking"] if b["code"] == "CE_HEARING_DEADLINE_MISSING"
    )
    assert deadline_block["field"] == "deadline"


# ---------------------------------------------------------------------------
# Test 6: Special magistrate hearing with deadline → NOT blocked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_passes_when_special_magistrate_hearing_has_deadline():
    """Special magistrate hearing with deadline provided → CE_HEARING_DEADLINE_MISSING must not fire."""
    actor = _make_actor()

    payload = {
        "factualBackground": (
            "Special magistrate hearing is scheduled for the property at 123 Main St."
        ),
        "deadline": "2026-06-01",
    }

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock()),
    ):
        result = await server.check_code_enforcement_litigation(
            rls_payload=payload,
            matter_type="code_enforcement_litigation",
        )

    codes = [b["code"] for b in result["blocking"]]
    assert "CE_HEARING_DEADLINE_MISSING" not in codes, (
        f"CE_HEARING_DEADLINE_MISSING must not fire when deadline is set, got: {codes}"
    )


# ---------------------------------------------------------------------------
# Test 7: ROI tool_invocation event emitted with correct fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emits_tool_invocation_on_success():
    """Must emit event_kind='tool_invocation' with correct fields including extra."""
    actor = _make_actor(actor_id="u9")

    captured: list[dict] = []

    async def capture(event_kind: str, payload: dict) -> None:
        captured.append({"event_kind": event_kind, **payload})

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock(side_effect=capture)),
    ):
        result = await server.check_code_enforcement_litigation(
            rls_payload={"factualBackground": "some text"},
            matter_type="permit_or_zoning",
        )

    assert result["applicable"] is False
    assert len(captured) == 1, f"Expected 1 ROI event, got {len(captured)}"

    event = captured[0]
    assert event["event_kind"] == "tool_invocation", (
        f"event_kind must be 'tool_invocation', got {event['event_kind']!r}"
    )
    assert event["user_id"] == "u9"
    assert event["tool"] == "rls_apex"
    assert event["task_type"] == "validation"
    assert event["success"] is True

    extra = event.get("extra", {})
    assert extra.get("matter_type") == "permit_or_zoning"
    assert extra.get("applicable") is False
    assert extra.get("blocking_count") == 0

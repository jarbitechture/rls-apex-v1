"""check_urgency_rules MCP tool — unit tests.

Plan D Task 3. Five tests covering:
1. Non-critical urgency → applicable=False, no blocking rules.
2. Critical urgency, no deadline → URG_DEADLINE_MISSING blocking.
3. Critical urgency, deadline > 15 working days → URG_DEADLINE_TOO_FAR blocking.
4. Critical urgency, deadline within 15 working days → URG_DEADLINE_TOO_FAR NOT triggered.
5. Critical urgency, no adverse action → URG_ADVERSE_MISSING blocking.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

import mcp_tools.check_urgency_rules.server as server


# ---------------------------------------------------------------------------
# Inline seeded_calendar fixture (cannot import from test_calendar.py without
# __init__.py — which is forbidden by repo conventions).
# ---------------------------------------------------------------------------

HOLIDAYS_2026 = [
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # MLK Day
    "2026-02-16",  # Presidents Day
    "2026-05-25",  # Memorial Day
    "2026-07-03",  # Independence Day (observed)
    "2026-09-07",  # Labor Day
    "2026-11-11",  # Veterans Day
    "2026-11-26",  # Thanksgiving
    "2026-11-27",  # Day after Thanksgiving
    "2026-12-24",  # Christmas Eve
    "2026-12-25",  # Christmas Day
]
HOLIDAYS_2025 = [
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-05-26", "2025-07-04",
    "2025-09-01", "2025-11-11", "2025-11-27", "2025-11-28", "2025-12-24",
    "2025-12-25",
]


@pytest_asyncio.fixture()
async def seeded_calendar(db_pool):
    """Insert calendar holiday rows into corpus_chunks."""
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM corpus_chunks WHERE source_type = 'calendar';")
        for iso in HOLIDAYS_2026 + HOLIDAYS_2025:
            body = f"Manatee County holiday: {iso}"
            sha = hashlib.sha256(body.encode()).hexdigest()
            await conn.execute(
                """
                INSERT INTO corpus_chunks
                  (source_id, source_type, section_path, citation, body, sha256,
                   valid_from, valid_to, embedding, metadata)
                VALUES ($1, 'calendar', $2, $3, $4, $5, $6, NULL, NULL, $7::jsonb)
                """,
                f"calendar.holiday.{iso}",
                "Holidays / 2026" if iso.startswith("2026") else "Holidays / 2025",
                f"Manatee County Working Days Calendar ({iso[:4]})",
                body, sha,
                datetime(int(iso[:4]), 1, 1, tzinfo=timezone.utc),
                f'{{"date": "{iso}"}}',
            )
    yield db_pool
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM corpus_chunks WHERE source_type = 'calendar';")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(actor_id: str = "tester@manatee.local") -> MagicMock:
    actor = MagicMock()
    actor.actor_id = actor_id
    return actor


# ---------------------------------------------------------------------------
# Test 1: non-critical urgency → applicable=False immediately
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_returns_applicable_false_when_urgency_not_critical(seeded_calendar):
    """urgency != 'critical' → applicable=False, empty blocking."""
    actor = _make_actor()
    server._db_pool = seeded_calendar

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock()),
    ):
        result = await server.check_urgency_rules(
            rls_payload={"factualBackground": "routine matter"},
            urgency="standard",
        )

    assert result["applicable"] is False
    assert result["blocking"] == []
    assert result["warnings"] == []


# ---------------------------------------------------------------------------
# Test 2: critical urgency, missing deadline → URG_DEADLINE_MISSING
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_blocks_when_critical_and_no_deadline(seeded_calendar):
    """Critical urgency without deadline → URG_DEADLINE_MISSING in blocking."""
    actor = _make_actor()
    server._db_pool = seeded_calendar

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock()),
    ):
        result = await server.check_urgency_rules(
            rls_payload={"factualBackground": "urgent matter, adverse action imminent"},
            urgency="critical",
            deadline=None,
            today=date(2026, 1, 6),
        )

    codes = [b["code"] for b in result["blocking"]]
    assert "URG_DEADLINE_MISSING" in codes, (
        f"Expected URG_DEADLINE_MISSING in blocking codes, got: {codes}"
    )
    block = next(b for b in result["blocking"] if b["code"] == "URG_DEADLINE_MISSING")
    assert block["field"] == "deadline"


# ---------------------------------------------------------------------------
# Test 3: critical urgency, deadline > 15 working days → URG_DEADLINE_TOO_FAR
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_blocks_when_deadline_exceeds_15_working_days(seeded_calendar):
    """Critical urgency with deadline > 15 working days → URG_DEADLINE_TOO_FAR."""
    actor = _make_actor()
    server._db_pool = seeded_calendar

    # today=2026-01-06 (Tue), deadline=2026-02-02 (Mon)
    # Working days Jan 6..Feb 2:
    #   Jan 6 (Tue), 7 (Wed), 8 (Thu), 9 (Fri)         = 4
    #   Jan 12..16                                       = 5
    #   Jan 20 = MLK Day (holiday), Jan 21..23           = 3
    #   Jan 26..30                                       = 5
    #   Feb 2 (Mon)                                      = 1
    #   Total = 18 > 15 → should block
    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock()),
    ):
        result = await server.check_urgency_rules(
            rls_payload={"factualBackground": "adverse action expected"},
            urgency="critical",
            deadline=date(2026, 2, 2),
            today=date(2026, 1, 6),
        )

    codes = [b["code"] for b in result["blocking"]]
    assert "URG_DEADLINE_TOO_FAR" in codes, (
        f"Expected URG_DEADLINE_TOO_FAR in blocking codes, got: {codes}"
    )
    block = next(b for b in result["blocking"] if b["code"] == "URG_DEADLINE_TOO_FAR")
    assert block["field"] == "deadline"


# ---------------------------------------------------------------------------
# Test 4: critical urgency, deadline ≤ 15 working days → URG_DEADLINE_TOO_FAR NOT triggered
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_passes_when_deadline_within_15_working_days(seeded_calendar):
    """Critical urgency, deadline within 15 working days → URG_DEADLINE_TOO_FAR must not fire."""
    actor = _make_actor()
    server._db_pool = seeded_calendar

    # today=2026-01-06 (Tue), deadline=2026-01-20 (holiday: MLK Day)
    # Working days Jan 6..Jan 20:
    #   Jan 6..9 (4), Jan 12..16 (5), Jan 19 = MLK Day, Jan 20 = MLK Day
    #   = 9 working days ≤ 15 → must NOT block
    # Also include adverse action text to suppress URG_ADVERSE_MISSING
    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock()),
    ):
        result = await server.check_urgency_rules(
            rls_payload={
                "factualBackground": (
                    "Adverse action notice was served. License revocation is pending."
                )
            },
            urgency="critical",
            deadline=date(2026, 1, 20),
            today=date(2026, 1, 6),
        )

    codes = [b["code"] for b in result["blocking"]]
    assert "URG_DEADLINE_TOO_FAR" not in codes, (
        f"URG_DEADLINE_TOO_FAR must not fire for deadline within 15 working days, got: {codes}"
    )


# ---------------------------------------------------------------------------
# Test 5: critical urgency, no adverse action mention → URG_ADVERSE_MISSING
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_blocks_when_no_adverse_action_mentioned(seeded_calendar):
    """Critical urgency without adverse action mention → URG_ADVERSE_MISSING in blocking."""
    actor = _make_actor()
    server._db_pool = seeded_calendar

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock()),
    ):
        result = await server.check_urgency_rules(
            rls_payload={"factualBackground": "routine critical matter, no adverse mention"},
            urgency="critical",
            deadline=date(2026, 1, 12),
            today=date(2026, 1, 6),
        )

    codes = [b["code"] for b in result["blocking"]]
    assert "URG_ADVERSE_MISSING" in codes, (
        f"Expected URG_ADVERSE_MISSING in blocking codes, got: {codes}"
    )
    block = next(b for b in result["blocking"] if b["code"] == "URG_ADVERSE_MISSING")
    assert block["field"] == "factualBackground"

"""E1 — check_urgency_rules emit shapes validated against ROI schema.

These tests patch server.roi.emit at the instance level (bypassing the emitter's
internal validate_event_for_persistence call) to independently verify that the
server's payload construction produces a schema-compliant event.

L2 touches the DB (calendar pool injection) — @pytest.mark.integration required.
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from apps.gateway.sidecar._client import validate_event_for_persistence
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
# Test 1: non-critical urgency → applicable=False emit passes ROI schema
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_l2_emit_non_urgent_passes_schema(seeded_calendar):
    """Non-critical urgency (applicable=False path): emit payload must pass ROI schema."""
    actor = _make_actor()
    server._db_pool = seeded_calendar
    captured: list[dict] = []

    async def capture(event_kind: str, payload: dict) -> None:
        captured.append({"event_kind": event_kind, **payload})

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock(side_effect=capture)),
    ):
        result = await server.check_urgency_rules(
            rls_payload={"factualBackground": "routine standard matter"},
            urgency="normal",
        )

    assert result["applicable"] is False
    assert len(captured) == 1, f"Expected 1 ROI event, got {len(captured)}"
    event = captured[0]

    # Core E1 assertion — must not raise.
    validate_event_for_persistence(event)

    assert event["success"] is True
    assert event["event_kind"] == "tool_invocation"
    assert event.get("extra", {}).get("applicable") is False


# ---------------------------------------------------------------------------
# Test 2: critical urgency, no deadline → applicable=True blocked emit passes ROI schema
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_l2_emit_critical_blocked_passes_schema(seeded_calendar):
    """Critical urgency with no deadline (blocked path): emit payload must pass ROI schema."""
    actor = _make_actor()
    server._db_pool = seeded_calendar
    captured: list[dict] = []

    async def capture(event_kind: str, payload: dict) -> None:
        captured.append({"event_kind": event_kind, **payload})

    with (
        patch.object(server, "require_actor", return_value=actor),
        patch.object(server.roi, "emit", AsyncMock(side_effect=capture)),
    ):
        result = await server.check_urgency_rules(
            rls_payload={"factualBackground": "adverse action imminent"},
            urgency="critical",
            deadline=None,
            today=date(2026, 1, 6),
        )

    assert result["applicable"] is True
    assert len(captured) == 1, f"Expected 1 ROI event, got {len(captured)}"
    event = captured[0]

    # Core E1 assertion — must not raise.
    validate_event_for_persistence(event)

    assert event["success"] is True
    assert event["event_kind"] == "tool_invocation"
    assert event.get("extra", {}).get("applicable") is True
    assert event.get("extra", {}).get("blocking_count", 0) >= 1

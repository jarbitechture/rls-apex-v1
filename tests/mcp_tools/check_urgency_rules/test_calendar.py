"""calendar_check_working_days tests against fixture-seeded holiday corpus."""
import hashlib
from datetime import date, datetime, timezone

import pytest_asyncio
import pytest


# 2026 Manatee County holidays (matches Plan A's W6 fixture)
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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_skip_weekends_and_holidays(seeded_calendar):
    from mcp_tools.check_urgency_rules.calendar import calendar_check_working_days
    # Jan 1 2026 (Thu, holiday) → Jan 6 2026 (Tue)
    # Days in range: Thu Jan 1 (holiday), Fri Jan 2, Sat Jan 3, Sun Jan 4, Mon Jan 5, Tue Jan 6
    # Working days: Jan 2 (Fri), Jan 5 (Mon), Jan 6 (Tue) = 3
    n = await calendar_check_working_days(
        seeded_calendar, start=date(2026, 1, 1), end=date(2026, 1, 6)
    )
    assert n == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_zero_when_only_holidays_and_weekends(seeded_calendar):
    from mcp_tools.check_urgency_rules.calendar import calendar_check_working_days
    # Dec 25 Fri (Christmas), Dec 26 Sat, Dec 27 Sun
    n = await calendar_check_working_days(
        seeded_calendar, start=date(2026, 12, 25), end=date(2026, 12, 27)
    )
    assert n == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cross_year_boundary(seeded_calendar):
    from mcp_tools.check_urgency_rules.calendar import calendar_check_working_days
    # 2025-12-29 Mon → 2026-01-05 Mon
    # Dec 29 Mon (work), Dec 30 Tue (work), Dec 31 Wed (work),
    # Jan 1 2026 Thu (holiday), Jan 2 Fri (work), Jan 3 Sat, Jan 4 Sun, Jan 5 Mon (work) = 5
    n = await calendar_check_working_days(
        seeded_calendar, start=date(2025, 12, 29), end=date(2026, 1, 5)
    )
    assert n == 5


@pytest.mark.integration
@pytest.mark.asyncio
async def test_single_workday_returns_one(seeded_calendar):
    from mcp_tools.check_urgency_rules.calendar import calendar_check_working_days
    # Tuesday Jan 6 to itself
    n = await calendar_check_working_days(
        seeded_calendar, start=date(2026, 1, 6), end=date(2026, 1, 6)
    )
    assert n == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_before_start_returns_zero(seeded_calendar):
    from mcp_tools.check_urgency_rules.calendar import calendar_check_working_days
    n = await calendar_check_working_days(
        seeded_calendar, start=date(2026, 1, 10), end=date(2026, 1, 5)
    )
    assert n == 0

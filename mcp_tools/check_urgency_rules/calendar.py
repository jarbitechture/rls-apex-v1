"""Working-days calendar helper.

Holidays sourced from corpus_chunks WHERE source_type='calendar'.
Each holiday row has metadata.date in ISO 8601 (YYYY-MM-DD).
"""
from __future__ import annotations

from datetime import date, timedelta

import asyncpg


async def _load_holiday_dates(db_pool: asyncpg.Pool) -> set[date]:
    """Read holiday ISO date strings out of corpus_chunks metadata."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT metadata->>'date' AS iso FROM corpus_chunks "
            "WHERE source_type = 'calendar' AND metadata ? 'date' "
            "AND valid_to IS NULL"
        )
    out: set[date] = set()
    for r in rows:
        iso = r["iso"]
        if iso:
            try:
                out.add(date.fromisoformat(iso))
            except ValueError:
                continue
    return out


async def calendar_check_working_days(
    db_pool: asyncpg.Pool,
    start: date,
    end: date,
) -> int:
    """Inclusive count of working days in [start, end].

    Working day = Mon-Fri AND not a county-recognized holiday.
    Returns 0 if end < start.
    """
    if end < start:
        return 0
    holidays = await _load_holiday_dates(db_pool)
    count = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5 and cur not in holidays:
            count += 1
        cur += timedelta(days=1)
    return count

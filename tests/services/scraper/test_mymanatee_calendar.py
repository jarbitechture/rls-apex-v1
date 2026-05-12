"""mymanatee_calendar source — 11 Manatee County 2026 holidays parsed from hand-authored fixture.

Spec W6: working-days calculation depends on these rows. The L2 working-days
tool (Plan D) queries ``WHERE source_type='calendar'`` and parses the strict
``"YYYY-MM-DD: Name"`` body format — both are asserted here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from services.scraper.sources.mymanatee_calendar import parse_calendar_html


FIXTURE_HTML = Path(__file__).parent / "fixtures" / "mymanatee_calendar_2026.html"
FIXTURE_JSON = Path(__file__).parent / "fixtures" / "manatee_holidays_2026.json"


def test_parser_extracts_11_holidays():
    """Spec W6: exactly 11 county-observed holidays for 2026."""
    chunks = parse_calendar_html(FIXTURE_HTML.read_text(), year=2026)
    assert len(chunks) == 11


def test_chunks_have_source_type_calendar():
    """L2 working-days tool queries WHERE source_type='calendar'."""
    chunks = parse_calendar_html(FIXTURE_HTML.read_text(), year=2026)
    assert all(c.source_type == "calendar" for c in chunks)


def test_chunks_have_consistent_source_id_and_section_path():
    chunks = parse_calendar_html(FIXTURE_HTML.read_text(), year=2026)
    assert all(c.source_id == "mymanatee.calendar.2026" for c in chunks)
    assert all(c.section_path == "Holidays 2026" for c in chunks)


def test_chunks_have_consistent_citation():
    chunks = parse_calendar_html(FIXTURE_HTML.read_text(), year=2026)
    assert all(
        c.citation == "Manatee County HR Observed Holidays (2026)" for c in chunks
    )


def test_holidays_match_known_json_dates():
    """HTML-parsed dates must match the hand-authored JSON (single source of truth)."""
    known = json.loads(FIXTURE_JSON.read_text())["holidays"]
    chunks = parse_calendar_html(FIXTURE_HTML.read_text(), year=2026)
    dates_from_chunks = sorted([c.body.split(":")[0].strip() for c in chunks])
    dates_known = sorted([h["date"] for h in known])
    assert dates_from_chunks == dates_known


def test_chunk_body_format():
    """Body format is 'YYYY-MM-DD: HolidayName' — L2 tool depends on this."""
    chunks = parse_calendar_html(FIXTURE_HTML.read_text(), year=2026)
    for c in chunks:
        assert re.match(r"^\d{4}-\d{2}-\d{2}:\s+.+$", c.body), f"bad body: {c.body!r}"


def test_chunk_sha256_is_64_hex():
    chunks = parse_calendar_html(FIXTURE_HTML.read_text(), year=2026)
    for c in chunks:
        assert re.fullmatch(r"[0-9a-f]{64}", c.sha256)

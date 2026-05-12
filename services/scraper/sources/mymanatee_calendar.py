"""mymanatee.org county holidays scraper.

mymanatee.org does NOT have a stable public holidays page — the fixture is
hand-authored from the canonical HR holiday list (verified against JSON twin
in tests/services/scraper/fixtures/manatee_holidays_2026.json). Each holiday
becomes one corpus_chunks row with source_type='calendar'; L2 working-days
queries `WHERE source_type='calendar'`.

This source differs from Tasks 6-8: it does NOT use ``normalize.chunk_html_section``
(paragraph-level). Each holiday is one structured row with body in the strict
``"YYYY-MM-DD: Name"`` format the L2 working-days tool (Plan D) parses.
"""
from __future__ import annotations

import hashlib
import re
from typing import AsyncIterator

import requests
from bs4 import BeautifulSoup

from services.scraper.breaker import get_or_create_breaker
from services.scraper.config import SOURCES
from services.scraper.normalize import Chunk


# Placeholder URL — mymanatee.org has no stable public holidays page today.
# When/if HR publishes one, swap this in; scrape runs currently rely on the
# hand-authored fixture (single source of truth: manatee_holidays_2026.json).
SEED_URL = (
    "https://www.mymanatee.org/departments/financial_management/"
    "human_resources/county_holidays"
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_calendar_html(html: str, year: int) -> list[Chunk]:
    """Parse the holiday list HTML; return one Chunk per holiday.

    Each Chunk has::

        body         = "YYYY-MM-DD: Holiday Name"
        source_id    = f"mymanatee.calendar.{year}"
        source_type  = "calendar"          # L2 query key
        section_path = f"Holidays {year}"
        citation     = f"Manatee County HR Observed Holidays ({year})"

    Lines that don't carry both a ``holiday-date`` span (with an ISO date) and
    a ``holiday-name`` span are skipped silently.
    """
    soup = BeautifulSoup(html, "html.parser")
    chunks: list[Chunk] = []

    for li in soup.find_all("li"):
        date_span = li.find("span", class_="holiday-date")
        name_span = li.find("span", class_="holiday-name")
        if not (date_span and name_span):
            continue

        date = date_span.get_text(strip=True)
        name = name_span.get_text(strip=True)
        if not _DATE_RE.match(date) or not name:
            continue

        body = f"{date}: {name}"
        chunks.append(
            Chunk(
                body=body,
                source_id=f"mymanatee.calendar.{year}",
                source_type="calendar",
                section_path=f"Holidays {year}",
                citation=f"Manatee County HR Observed Holidays ({year})",
                sha256=_sha256(body),
            )
        )

    return chunks


async def fetch_and_chunk(year: int = 2026) -> AsyncIterator[Chunk]:
    """Fetch the county holidays page through the async breaker; yield chunks.

    NOTE: mymanatee.org has no stable public holidays URL today. ``SEED_URL`` is
    wired for the future-when-discovered page; current scrape runs would
    populate from the hand-authored fixture (or a curated HTML drop) instead.
    The breaker contract matches Tasks 6-8 (``await breaker.call(sync_fn)``).
    """
    cfg = SOURCES["mymanatee_calendar"]
    breaker = get_or_create_breaker(cfg.host)

    def _fetch():
        return requests.get(
            SEED_URL,
            timeout=cfg.timeout_s,
            headers={"User-Agent": "RLS-Apex Scraper (Manatee County internal)"},
        )

    response = await breaker.call(_fetch)
    response.raise_for_status()

    for chunk in parse_calendar_html(response.text, year):
        yield chunk

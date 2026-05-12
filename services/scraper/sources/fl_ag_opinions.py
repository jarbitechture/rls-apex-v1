"""FL AG Opinions scraper — myfloridalegal.com/opinions index + per-opinion pages.

Server-side rendered (Drupal-style markup, not Angular). Uses the async breaker
per Tasks 6-8 contract. The fixture is a single sample opinion (AGO 2020-09 on
local regulation of vaping device sales to ages 18-20); full multi-opinion
crawling is deferred to v0.2.1b. Each opinion becomes paragraph-level chunks
via ``chunk_html_section``.

Citation format: ``"Fla. Op. Att'y Gen. <year>-<num>"`` (e.g.,
``"Fla. Op. Att'y Gen. 2020-09"``). The AGO number is mined from the page
content via regex — myfloridalegal.com surfaces ``"AGO 2020-09"`` in the
breadcrumb / metadata blocks rather than a structured field.
"""
from __future__ import annotations

import re
from typing import AsyncIterator

import requests
from bs4 import BeautifulSoup

from services.scraper.breaker import get_or_create_breaker
from services.scraper.config import SOURCES
from services.scraper.normalize import Chunk, chunk_html_section


SEED_URL = "https://www.myfloridalegal.com/opinions"

# AGO numbers look like "AGO 2020-09" (year-padded sequence).
_AGO_NUMBER_RE = re.compile(r"AGO\s+(\d{4})-(\d+)", re.I)


def _extract_ago_info(soup: BeautifulSoup) -> tuple[str, str, str]:
    """Return ``(ago_num, year, opinion_title)`` extracted from the page.

    ``ago_num`` is the ``"YYYY-NN"`` portion (e.g., ``"2020-09"``); year is the
    4-digit prefix for version_year wiring. Opinion title is the first ``<h1>``
    (falling back to ``<h2>``, then ``<title>``) with the trailing site-suffix
    stripped.
    """
    title_tag = soup.find("title")
    title_text = title_tag.get_text(" ", strip=True) if title_tag else ""

    # Search the title first, then the full page text. AGO numbers appear in
    # breadcrumbs and inline metadata blocks rather than dedicated fields.
    page_text = soup.get_text(" ", strip=True) if soup else ""
    haystack = f"{title_text} {page_text[:2000]}"
    match = _AGO_NUMBER_RE.search(haystack)
    if match:
        year = match.group(1)
        num = match.group(2)
        ago_num = f"{year}-{num}"
    else:
        ago_num = "unknown"
        year = "unknown"

    # Opinion title — prefer <h1>, fall back to <h2>, then strip "| My Florida
    # Legal" or similar site-name tail off the <title>.
    heading = soup.find("h1") or soup.find("h2")
    opinion_title = heading.get_text(" ", strip=True) if heading else ""
    if not opinion_title:
        opinion_title = re.sub(r"\s*\|\s*My Florida Legal.*$", "", title_text, flags=re.I).strip()

    return ago_num, year, opinion_title or title_text


def parse_section_html(html: str, section_url: str) -> list[Chunk]:
    """Parse one FL AG opinion page into paragraph-level chunks.

    Returns ``[]`` only if the page genuinely has no parseable paragraphs —
    callers should treat that as a scrape miss, not a parser bug.
    """
    soup = BeautifulSoup(html, "html.parser")

    ago_num, year, opinion_title = _extract_ago_info(soup)
    source_id = f"fl_ag.{ago_num}"
    section_path = f"FL AG Opinions / AGO {ago_num} / {opinion_title}"

    # Locate the opinion body — myfloridalegal.com uses Drupal markup. The
    # ``field--name-body`` div carries the rendered opinion. Fall back to
    # <article>, <main>, then the whole document.
    main = (
        soup.find("div", class_=re.compile(r"field--name-body", re.I))
        or soup.find("article")
        or soup.find("main")
        or soup
    )

    citation_prefix = "Fla. Op. Att'y Gen."
    version_year_int = int(year) if year.isdigit() else 2024

    chunks = chunk_html_section(
        html=str(main),
        source_id=source_id,
        source_type="fl_ag_opinion",
        section_path=section_path,
        citation_prefix=citation_prefix,
        version_year=version_year_int,
    )

    # ``chunk_html_section`` builds citations like "Fla. Op. Att'y Gen. (2020)";
    # FL AG citations conventionally include the AGO number itself
    # ("Fla. Op. Att'y Gen. 2020-09"). Post-process each chunk to inject it.
    rewritten: list[Chunk] = []
    for chunk in chunks:
        new_citation = f"Fla. Op. Att'y Gen. {ago_num}"
        rewritten.append(
            Chunk(
                body=chunk.body,
                source_id=chunk.source_id,
                source_type=chunk.source_type,
                section_path=chunk.section_path,
                citation=new_citation,
                sha256=chunk.sha256,
            )
        )
    return rewritten


async def fetch_and_chunk() -> AsyncIterator[Chunk]:
    """Fetch the FL AG opinions seed page through the myfloridalegal host
    breaker; yield chunks.

    ``CircuitBreaker.call`` is async (apps/gateway/circuit/breaker.py); we wrap
    the synchronous ``requests.get`` in a callable so the breaker can run it
    and apply the open/half-open guard.
    """
    cfg = SOURCES["fl_ag_opinions"]
    breaker = get_or_create_breaker(cfg.host)

    def _fetch():
        return requests.get(
            SEED_URL,
            timeout=cfg.timeout_s,
            headers={"User-Agent": "RLS-Apex Scraper (Manatee County internal)"},
        )

    response = await breaker.call(_fetch)
    response.raise_for_status()

    for chunk in parse_section_html(response.text, SEED_URL):
        yield chunk

"""Municode Code of Ordinances Ch. 2-26 scraper.

Source: ``library.municode.com/fl/manatee_county/codes/code_of_ordinances``

Same Angular SPA shape as the LDC source — content lives in
``<main class="primary content-zone zone style-default-bright">``; section
identifiers come from ``<title>`` (``"Chapter 2-25 - PLANNING AND DEVELOPMENT
| Code of Ordinances | ..."`` or ``"Sec. 2-25-80 ... | Code of Ordinances |
..."``) with a fallback to the first non-modal ``<h2>``.

The plan targeted Chapter 2-26 (Procurement) but the live Municode TOC nodeId
for Ch. 2-26 returned "Content Not Found" at fixture-capture time. The fixture
landed on Ch. 2-25 (Planning and Development); the parser stays
chapter-agnostic — it derives the chapter from the page title rather than
hardcoding "2-26".
"""
from __future__ import annotations

import re
from typing import AsyncIterator

import requests
from bs4 import BeautifulSoup

from services.scraper.breaker import get_or_create_breaker
from services.scraper.config import SOURCES
from services.scraper.normalize import Chunk, chunk_html_section


VERSION_YEAR = 2024

SEED_URL = "https://library.municode.com/fl/manatee_county/codes/code_of_ordinances"

_TITLE_SUFFIX_RE = re.compile(
    r"\s*\|\s*(Land Development Code|Code of Ordinances).*$", re.I
)

# Try Section-level (Sec. 2-25-80) first, then Chapter-level (Chapter 2-25),
# then §, then Ordinance No. — Code of Ordinances pages usually surface one of
# Sec./Chapter in the <title>.
_SECTION_NUM_RE = re.compile(
    r"Sec\.\s*([\d\-\.]+)"
    r"|Chapter\s+([\d\-\.]+)"
    r"|§\s*([\d.]+)"
    r"|Ordinance\s+No\.\s*([\d\-]+)",
    re.I,
)

_CHAPTER_RE = re.compile(r"Chapter\s+([\d\-\.]+)", re.I)


def _first_non_modal_h2(soup: BeautifulSoup) -> str:
    """Return text of the first useful <h2> — skip modal-title and SPA shells."""
    for h2 in soup.find_all("h2"):
        classes = " ".join(h2.get("class") or [])
        if "modal" in classes:
            continue
        text = h2.get_text(" ", strip=True)
        if not text:
            continue
        low = text.lower()
        if "loading title" in low or "get notified" in low or "search results" in low:
            continue
        return text
    return ""


def _derive_chapter_label(label: str) -> str:
    """Return ``"Ch. 2-25"`` (or similar) when the page title mentions a chapter."""
    m = _CHAPTER_RE.search(label)
    if m:
        return f"Ch. {m.group(1)}"
    return ""


def _extract_section_info(soup: BeautifulSoup) -> tuple[str, str]:
    """Derive ``(section_path, source_id_suffix)`` for the page.

    Prefers ``<title>`` (cleaner string after stripping Municode's "| Code of
    Ordinances | ..." tail), falls back to the first non-modal ``<h2>``.
    """
    title_tag = soup.find("title")
    title_text = title_tag.get_text(" ", strip=True) if title_tag else ""
    title_text = _TITLE_SUFFIX_RE.sub("", title_text).strip()

    label = title_text or _first_non_modal_h2(soup)

    match = _SECTION_NUM_RE.search(label)
    if match:
        section_num = (
            match.group(1) or match.group(2) or match.group(3) or match.group(4)
        )
        suffix = section_num.replace("-", "_").replace(".", "_")
        chapter = _derive_chapter_label(label)
        prefix = f"Manatee Code / {chapter} / " if chapter else "Manatee Code / "
        return f"{prefix}{label}", suffix

    return (
        f"Manatee Code / {label}" if label else "Manatee Code",
        "unknown",
    )


def parse_section_html(html: str, section_url: str) -> list[Chunk]:
    """Parse one Municode Code of Ordinances page into paragraph-level chunks.

    Returns ``[]`` only if the page genuinely has no parseable paragraphs —
    callers should treat that as a scrape miss, not a parser bug.
    """
    soup = BeautifulSoup(html, "html.parser")

    main = soup.find("main", class_=re.compile(r"content-zone", re.I)) or soup

    section_path, source_id_suffix = _extract_section_info(soup)
    source_id = f"municode.ch2_26.{source_id_suffix}"

    return chunk_html_section(
        html=str(main),
        source_id=source_id,
        source_type="ordinance",
        section_path=section_path,
        citation_prefix="Manatee County Code",
        version_year=VERSION_YEAR,
    )


async def fetch_and_chunk() -> AsyncIterator[Chunk]:
    """Fetch the Code of Ordinances seed page through the Municode host
    breaker; yield chunks.

    ``CircuitBreaker.call`` is async (apps/gateway/circuit/breaker.py); we wrap
    the synchronous ``requests.get`` in a callable so the breaker can run it
    and apply the open/half-open guard.
    """
    cfg = SOURCES["municode_ch2_26"]
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

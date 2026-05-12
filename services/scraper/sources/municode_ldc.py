"""Municode LDC scraper.

Source: ``library.municode.com/fl/manatee_county/codes/land_development_code``

Municode is an Angular SPA. Content lives in
``<main class="primary content-zone zone style-default-bright">``; section
identifiers come from ``<title>`` (``"Ordinance No. 26-05 | Land Development
Code | ..."``) with a fallback to the first non-modal ``<h2>``. Paragraphs may
start with ``(a)``/``(b)``/``(1)`` subsection markers — those are handled by
``normalize.chunk_html_section``.

The seed-URL nodeId scheme is brittle: Municode's TOC node-ids change on each
re-publish. We point at the codified land_development_code root and let the
SPA fall through; downstream tasks may iterate the TOC.
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

SEED_URL = "https://library.municode.com/fl/manatee_county/codes/land_development_code"

_TITLE_SUFFIX_RE = re.compile(
    r"\s*\|\s*(Land Development Code|Code of Ordinances).*$", re.I
)

_SECTION_NUM_RE = re.compile(
    r"§\s*([\d.]+)|Sec\.\s*([\d\-\.]+)|Ordinance\s+No\.\s*([\d\-]+)",
    re.I,
)


def _first_non_modal_h2(soup: BeautifulSoup) -> str:
    """Return text of the first useful <h2> — skip modal-title and SPA shells."""
    for h2 in soup.find_all("h2"):
        classes = " ".join(h2.get("class") or [])
        if "modal" in classes:
            continue
        text = h2.get_text(" ", strip=True)
        if not text:
            continue
        # SPA shell placeholders such as "loading title...Get Notified".
        low = text.lower()
        if "loading title" in low or "get notified" in low or "search results" in low:
            continue
        return text
    return ""


def _extract_section_info(soup: BeautifulSoup) -> tuple[str, str]:
    """Derive ``(section_path, source_id_suffix)`` for the page.

    Prefers ``<title>`` (cleaner string after stripping Municode's "| Land
    Development Code | ..." tail), falls back to the first non-modal ``<h2>``.
    """
    title_tag = soup.find("title")
    title_text = title_tag.get_text(" ", strip=True) if title_tag else ""
    title_text = _TITLE_SUFFIX_RE.sub("", title_text).strip()

    label = title_text or _first_non_modal_h2(soup)

    match = _SECTION_NUM_RE.search(label)
    if match:
        section_num = match.group(1) or match.group(2) or match.group(3)
        suffix = section_num.replace("-", "_").replace(".", "_")
        return f"Manatee LDC / {label}", suffix

    return f"Manatee LDC / {label}" if label else "Manatee LDC", "unknown"


def parse_section_html(html: str, section_url: str) -> list[Chunk]:
    """Parse one Municode LDC page into paragraph-level chunks.

    Returns ``[]`` only if the page genuinely has no parseable paragraphs —
    callers should treat that as a scrape miss, not a parser bug.
    """
    soup = BeautifulSoup(html, "html.parser")

    main = soup.find("main", class_=re.compile(r"content-zone", re.I)) or soup

    section_path, source_id_suffix = _extract_section_info(soup)
    source_id = f"municode.ldc.{source_id_suffix}"

    return chunk_html_section(
        html=str(main),
        source_id=source_id,
        source_type="ldc",
        section_path=section_path,
        citation_prefix="Manatee County LDC",
        version_year=VERSION_YEAR,
    )


async def fetch_and_chunk() -> AsyncIterator[Chunk]:
    """Fetch the LDC seed page through the Municode host breaker; yield chunks.

    ``CircuitBreaker.call`` is async (apps/gateway/circuit/breaker.py); we wrap
    the synchronous ``requests.get`` in a callable so the breaker can run it
    and apply the open/half-open guard.
    """
    cfg = SOURCES["municode_ldc"]
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

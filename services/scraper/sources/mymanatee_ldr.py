"""mymanatee.org LDR ecosystem scraper.

Source: ``mymanatee.org/services-and-amenities/service-listing/service-details/view-land-development-regulations``

Unlike Municode this page is server-side rendered (not an Angular SPA). Content
lives in ``<main>`` (~7.8 KB of plain text, 21+ non-empty ``<p>`` tags in the
real fixture). Title is the clean human label ``"View Land Development
Regulations"`` — no Municode-style "| ..." suffix to strip.

The page is an LDR ecosystem hub: it links out to the Development Review Manual
(PDF), the Comprehensive Plan (PDF), and ordinance history. Crawling those
linked PDFs is deferred to v0.2.1b; this module only parses the hub page itself.

Section identifiers are derived from the page's ``<h2>``/``<h3>`` history
headings (e.g. "2015 -- LDC REWRITE Ordinance 15-17"); paragraphs inherit the
page-level section_path. Subsection markers (``(a)``/``(b)``/``(1)``) are
handled by ``normalize.chunk_html_section`` for the synthetic test path, even
though the real hub page is descriptive prose without enumerated subsections.
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

SEED_URL = (
    "https://www.mymanatee.org/services-and-amenities/service-listing/"
    "service-details/view-land-development-regulations"
)

# Strip site-name suffix if mymanatee.org ever adds a "| Manatee County" tail.
_TITLE_SUFFIX_RE = re.compile(r"\s*\|\s*.*Manatee.*$", re.I)


def _extract_page_label(soup: BeautifulSoup) -> str:
    """Pick the cleanest human label for the page.

    Prefers ``<title>`` (real fixture: "View Land Development Regulations"),
    falls back to the first ``<h1>``/``<h2>`` if title is missing.
    """
    title_tag = soup.find("title")
    title_text = title_tag.get_text(" ", strip=True) if title_tag else ""
    title_text = _TITLE_SUFFIX_RE.sub("", title_text).strip()
    if title_text:
        return title_text

    for tag in ("h1", "h2"):
        h = soup.find(tag)
        if h:
            text = h.get_text(" ", strip=True)
            if text and text.lower() != "search results":
                return text
    return "Land Development Regulations"


def parse_section_html(html: str, section_url: str) -> list[Chunk]:
    """Parse the LDR hub page into paragraph-level chunks.

    Returns ``[]`` only if the page has no usable paragraphs — callers should
    treat that as a scrape miss, not a parser bug.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Server-side rendered; <main> is the canonical content container.
    # Fallbacks cover hypothetical future template changes.
    main = soup.find("main") or soup.find("article") or soup

    label = _extract_page_label(soup)

    # The LDR hub is a single page; use a fixed source_id rather than per-section
    # suffixing. Per-PDF source_ids will land in v0.2.1b when linked-doc crawling
    # is added.
    source_id = "mymanatee.ldr.main"
    section_path = f"Manatee County LDR / {label}"

    return chunk_html_section(
        html=str(main),
        source_id=source_id,
        source_type="ldc",  # LDR ecosystem = LDC-equivalent land-use regulations
        section_path=section_path,
        citation_prefix="Manatee County LDR",
        version_year=VERSION_YEAR,
    )


async def fetch_and_chunk() -> AsyncIterator[Chunk]:
    """Fetch the LDR hub page through the mymanatee host breaker; yield chunks.

    ``CircuitBreaker.call`` is async (apps/gateway/circuit/breaker.py); we wrap
    the synchronous ``requests.get`` in a callable so the breaker can run it
    and apply the open/half-open guard.
    """
    cfg = SOURCES["mymanatee_ldr"]
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

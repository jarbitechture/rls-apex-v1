"""HTML -> paragraph chunks with section-header context, citations, and sha256.

Per spec §4.3: paragraph-level chunks with section-header context. Each chunk
records section_path (full hierarchy), citation (formatted), body (plain text),
and sha256 (for change detection).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class Chunk:
    body: str
    source_id: str
    source_type: str
    section_path: str
    citation: str
    sha256: str


SUBSECTION_PREFIX_RE = re.compile(r"^\(([a-z0-9]+)\)\s*")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_subsection_marker(text: str) -> tuple[str | None, str]:
    """If paragraph starts with '(a)' or '(1)', strip and return (marker, remaining_text)."""
    m = SUBSECTION_PREFIX_RE.match(text)
    if m:
        return m.group(1), text[m.end():].strip()
    return None, text


def chunk_html_section(
    html: str,
    source_id: str,
    source_type: str,
    section_path: str,
    citation_prefix: str,
    version_year: int,
) -> list[Chunk]:
    """Parse an HTML fragment representing one code section; return one Chunk per paragraph.

    Paragraphs starting with `(a)`, `(b)`, etc. are recognized as subsections;
    the marker is appended to section_path and citation.
    """
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.find_all("p")
    chunks: list[Chunk] = []

    # Parse section number out of section_path (last "§X.Y" pattern)
    section_num_match = re.search(r"§([\d.]+)", section_path)
    section_num = section_num_match.group(1) if section_num_match else None

    for p in paragraphs:
        raw_text = p.get_text(strip=True)
        if not raw_text:
            continue

        marker, body_text = _extract_subsection_marker(raw_text)
        if marker:
            full_section_path = f"{section_path} / ({marker})"
            citation = (
                f"{citation_prefix} §{section_num}({marker}) ({version_year})"
                if section_num
                else f"{citation_prefix} ({version_year})"
            )
        else:
            full_section_path = section_path
            citation = (
                f"{citation_prefix} §{section_num} ({version_year})"
                if section_num
                else f"{citation_prefix} ({version_year})"
            )

        chunks.append(
            Chunk(
                body=body_text,
                source_id=source_id,
                source_type=source_type,
                section_path=full_section_path,
                citation=citation,
                sha256=_sha256(body_text),
            )
        )

    return chunks

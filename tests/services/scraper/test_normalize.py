"""Chunker preserves citation precision and paragraph boundaries."""
from __future__ import annotations

from services.scraper.normalize import chunk_html_section, Chunk


SAMPLE_HTML = """
<div class="section" id="sec_6_4">
  <h2>§6.4 — Building Code Compliance</h2>
  <p>(a) All structures shall comply with the Florida Building Code (FBC) as adopted by the State of Florida.</p>
  <p>(b) Applicants seeking variance approval shall submit a Variance Application Form FB-101.</p>
  <p>(c) The Building Official shall review applications within 30 working days of filing.</p>
</div>
"""


def test_chunker_returns_one_chunk_per_paragraph():
    chunks = chunk_html_section(
        html=SAMPLE_HTML,
        source_id="municode.ldc.6.4",
        source_type="ldc",
        section_path="Chapter 6 / §6.4",
        citation_prefix="Manatee County LDC",
        version_year=2024,
    )
    assert len(chunks) == 3
    assert all(isinstance(c, Chunk) for c in chunks)


def test_chunker_preserves_subsection_in_section_path():
    chunks = chunk_html_section(SAMPLE_HTML, "x", "ldc", "Chapter 6 / §6.4", "Manatee LDC", 2024)
    paths = [c.section_path for c in chunks]
    assert "Chapter 6 / §6.4 / (a)" in paths
    assert "Chapter 6 / §6.4 / (b)" in paths
    assert "Chapter 6 / §6.4 / (c)" in paths


def test_chunker_formats_citation_with_subsection():
    chunks = chunk_html_section(SAMPLE_HTML, "x", "ldc", "Chapter 6 / §6.4", "Manatee County LDC", 2024)
    citations = [c.citation for c in chunks]
    assert "Manatee County LDC §6.4(a) (2024)" in citations
    assert "Manatee County LDC §6.4(b) (2024)" in citations


def test_chunker_body_is_plain_text_no_html():
    chunks = chunk_html_section(SAMPLE_HTML, "x", "ldc", "Chapter 6 / §6.4", "Manatee LDC", 2024)
    assert all("<" not in c.body for c in chunks)


def test_chunker_sha256_is_64_hex():
    chunks = chunk_html_section(SAMPLE_HTML, "x", "ldc", "Chapter 6 / §6.4", "Manatee LDC", 2024)
    import re
    assert all(re.fullmatch(r"[0-9a-f]{64}", c.sha256) for c in chunks)


def test_chunker_handles_empty_section():
    chunks = chunk_html_section("<div></div>", "x", "ldc", "Chapter 6 / §6.4", "Manatee LDC", 2024)
    assert chunks == []

"""Ch. 2-26 source module — parses real Municode HTML, returns ordinance chunks."""
from __future__ import annotations

from pathlib import Path

from services.scraper.sources.municode_ch2_26 import parse_section_html


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "municode_ch2_26_section.html"


def test_parse_real_fixture_returns_chunks():
    """Parse the real Municode-captured Chapter page; verify the parser returns
    a non-trivial set of ordinance Chunks with Manatee County Code citations.
    The captured fixture is Chapter 2-25 (Planning and Development), ~619 KB
    with hundreds of paragraphs.
    """
    html = FIXTURE_PATH.read_text()
    chunks = parse_section_html(
        html,
        section_url=(
            "https://library.municode.com/fl/manatee_county/codes/code_of_ordinances"
        ),
    )
    assert len(chunks) >= 10, f"expected many chunks from real chapter fixture, got {len(chunks)}"
    assert all(c.source_type == "ordinance" for c in chunks)
    assert all("Manatee County Code" in c.citation for c in chunks)


def test_real_fixture_body_is_plain_text():
    """No HTML markup leaks into chunk bodies."""
    html = FIXTURE_PATH.read_text()
    chunks = parse_section_html(html, "https://x")
    for c in chunks:
        assert "<" not in c.body, f"body contained HTML: {c.body[:80]}"
        assert ">" not in c.body, f"body contained HTML: {c.body[:80]}"


def test_subsection_marker_extraction_via_synthetic_fragment():
    """Subsection-marker branch via synthetic HTML, since the real chapter
    fixture mixes hundreds of paragraphs and we want a tight assertion on the
    (a)/(b) routing. Validates the Ch 2-26 source module routes through the
    chunker's marker branch with ``source_type="ordinance"``."""
    fake_html = """
    <html><head><title>Sec. 2-25-80 - Temporary moratorium | Code of Ordinances | Manatee County, FL | Municode Library</title></head><body>
    <main class="primary content-zone zone style-default-bright">
      <h2>Sec. 2-25-80 — Temporary moratorium</h2>
      <div class="chunk">
        <p>(a) The board may impose a temporary moratorium upon a finding of urgent need.</p>
        <p>(b) A moratorium shall not exceed twelve months without renewal.</p>
      </div>
    </main>
    </body></html>
    """
    chunks = parse_section_html(fake_html, "https://x")
    assert len(chunks) == 2
    assert all(c.source_type == "ordinance" for c in chunks)
    assert all("Manatee County Code" in c.citation for c in chunks)
    paths = [c.section_path for c in chunks]
    assert any("(a)" in p for p in paths)
    assert any("(b)" in p for p in paths)
    # source_id suffix should derive from "Sec. 2-25-80" → "2_25_80"
    assert all(c.source_id == "municode.ch2_26.2_25_80" for c in chunks)

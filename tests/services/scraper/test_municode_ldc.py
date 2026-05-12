"""LDC source module — parses real Municode HTML, returns chunks with expected fields."""
from __future__ import annotations

from pathlib import Path

from services.scraper.sources.municode_ldc import parse_section_html


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "municode_ldc_section_6_4.html"


def test_parse_real_fixture_returns_chunks():
    """Parse the real Municode-captured Ordinance 26-05 page; verify parser doesn't crash + returns Chunks."""
    html = FIXTURE_PATH.read_text()
    chunks = parse_section_html(
        html,
        section_url="https://library.municode.com/fl/manatee_county/codes/land_development_code?nodeId=1409404",
    )
    # Real fixture has at least one paragraph — exact count depends on Municode page state
    assert len(chunks) >= 1, "expected at least one chunk from real fixture"
    assert all(c.source_type == "ldc" for c in chunks)
    # Citation prefix should always include Manatee
    assert all("Manatee" in c.citation for c in chunks)


def test_real_fixture_body_is_plain_text():
    """No HTML markup leaks into chunk bodies."""
    html = FIXTURE_PATH.read_text()
    chunks = parse_section_html(html, "https://x")
    for c in chunks:
        assert "<" not in c.body, f"body contained HTML: {c.body[:80]}"
        assert ">" not in c.body, f"body contained HTML: {c.body[:80]}"


def test_subsection_marker_extraction_via_synthetic_fragment():
    """Subsection-marker branch via synthetic HTML, since the real Ordinance fixture
    is uncodified text without (a)/(b)/(1) markers. Validates that the LDC source
    module routes through the chunker's marker branch correctly."""
    # Inline-construct a Municode-shape fragment that has subsection markers
    fake_html = """
    <html><body>
    <main class="primary content-zone zone style-default-bright">
      <h2>Sec. 6.4 — Building Code Compliance</h2>
      <div class="chunk">
        <p>(a) All structures shall comply with the Florida Building Code.</p>
        <p>(b) Applicants seeking variance shall submit Form FB-101.</p>
      </div>
    </main>
    </body></html>
    """
    chunks = parse_section_html(fake_html, "https://x")
    # Expect 2 chunks, each with subsection in section_path
    assert len(chunks) == 2
    paths = [c.section_path for c in chunks]
    assert any("(a)" in p for p in paths)
    assert any("(b)" in p for p in paths)

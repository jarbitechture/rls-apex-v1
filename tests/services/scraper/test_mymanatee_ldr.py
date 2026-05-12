"""LDR source module — parses mymanatee.org LDR hub page."""
from __future__ import annotations

from pathlib import Path

from services.scraper.sources.mymanatee_ldr import parse_section_html


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "mymanatee_ldr_page.html"


def test_parse_real_fixture_returns_substantive_chunks():
    """Real LDR fixture is 121 KB of server-rendered content — must produce real chunks."""
    chunks = parse_section_html(
        FIXTURE_PATH.read_text(),
        section_url=(
            "https://www.mymanatee.org/services-and-amenities/service-listing/"
            "service-details/view-land-development-regulations"
        ),
    )
    # Real fixture has 21+ non-empty <p> in <main>; expect a meaningful number of chunks
    assert len(chunks) >= 5, f"expected >= 5 chunks, got {len(chunks)}"
    assert all(c.source_type == "ldc" for c in chunks)
    assert all(
        "LDR" in c.citation or "LDR" in c.section_path for c in chunks
    )


def test_real_fixture_body_is_plain_text():
    """No HTML markup leaks into chunk bodies."""
    chunks = parse_section_html(FIXTURE_PATH.read_text(), "https://x")
    for c in chunks:
        assert "<" not in c.body, f"body contained HTML: {c.body[:80]}"
        assert ">" not in c.body, f"body contained HTML: {c.body[:80]}"


def test_subsection_marker_via_synthetic_fragment():
    """Mirror Tasks 6-7 pattern — exercise the chunker's subsection-marker branch
    via a synthetic fragment, since the real LDR hub page is descriptive prose
    without enumerated (a)/(b) subsections."""
    fake_html = """
    <html><body>
    <main>
      <h2>§3.2 Submittal Requirements</h2>
      <p>(a) The applicant shall file Form A.</p>
      <p>(b) The applicant shall file Form B.</p>
    </main>
    </body></html>
    """
    chunks = parse_section_html(fake_html, "https://x")
    assert len(chunks) == 2
    paths = [c.section_path for c in chunks]
    assert any("(a)" in p for p in paths)
    assert any("(b)" in p for p in paths)

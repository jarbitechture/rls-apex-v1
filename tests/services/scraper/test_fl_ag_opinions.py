"""FL AG Opinions source — parses myfloridalegal.com opinion pages."""
from __future__ import annotations

from pathlib import Path

from services.scraper.sources.fl_ag_opinions import parse_section_html


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "fl_ag_opinion_sample.html"


def test_parse_real_fixture_returns_chunks():
    """Real AGO 2020-09 fixture must produce paragraph chunks."""
    chunks = parse_section_html(
        FIXTURE_PATH.read_text(),
        "https://www.myfloridalegal.com/opinions/2020-09",
    )
    assert len(chunks) >= 5, f"expected >= 5 chunks, got {len(chunks)}"
    assert all(c.source_type == "fl_ag_opinion" for c in chunks)


def test_real_fixture_citation_includes_ago_number():
    """Citation must be ``Fla. Op. Att'y Gen. 2020-09`` (AGO-number format)."""
    chunks = parse_section_html(FIXTURE_PATH.read_text(), "https://x")
    assert all("Fla. Op. Att'y Gen." in c.citation for c in chunks)
    assert any("2020-09" in c.citation for c in chunks), (
        f"no chunk has AGO 2020-09 in citation; sample: "
        f"{chunks[0].citation if chunks else 'n/a'}"
    )


def test_real_fixture_body_is_plain_text():
    """No HTML markup leaks into chunk bodies."""
    chunks = parse_section_html(FIXTURE_PATH.read_text(), "https://x")
    for c in chunks:
        assert "<" not in c.body, f"body contained HTML: {c.body[:80]}"
        assert ">" not in c.body, f"body contained HTML: {c.body[:80]}"


def test_real_fixture_substantive_content():
    """Per Tasks 7-8 reviewer recs: assert chunks contain real opinion vocab.

    AGO 2020-09 is about local regulation of vaping device sales — content
    should mention domain vocabulary, not just navigation chrome.
    """
    chunks = parse_section_html(FIXTURE_PATH.read_text(), "https://x")
    bodies_lower = " ".join(c.body.lower() for c in chunks)
    assert any(
        kw in bodies_lower
        for kw in ["opinion", "regulation", "vaping", "florida", "section"]
    ), "no substantive vocab in any chunk body"


def test_source_id_format():
    """source_id must be ``fl_ag.<year>-<num>`` for real AGO 2020-09 fixture."""
    chunks = parse_section_html(FIXTURE_PATH.read_text(), "https://x")
    assert all(c.source_id.startswith("fl_ag.") for c in chunks)
    assert any(c.source_id == "fl_ag.2020-09" for c in chunks)


def test_subsection_marker_via_synthetic_fragment():
    """Subsection-marker branch via synthetic HTML — real fixture is prose
    without ``(a)``/``(b)`` markers, so this validates the marker route."""
    fake_html = """
    <html><body>
    <main>
      <h1>AGO 2024-05 — Sample Opinion</h1>
      <div class="field--name-body">
        <p>(a) The first issue is whether the statute applies.</p>
        <p>(b) The second issue is whether local regulation is preempted.</p>
      </div>
    </main>
    </body></html>
    """
    chunks = parse_section_html(fake_html, "https://x")
    paths = [c.section_path for c in chunks]
    assert any("(a)" in p for p in paths)
    assert any("(b)" in p for p in paths)

"""classify_matter v0.2.0a is a regex mock that maps keywords to RlsType (spec §4.1)."""
import pytest

from mcp_tools.classify_matter.server import classify_text


@pytest.mark.parametrize("text,expected_type", [
    ("Need legal review on a permit denial", "permit_or_zoning"),
    ("Code enforcement violation, NOV issued, lien proceedings", "code_enforcement_litigation"),
    ("Request for procurement contract review", "procurement"),
    ("Public records request from journalist", "public_records"),
    ("General advisory on commission ethics", "general_advisory"),
])
def test_classify_text_returns_expected_type(text, expected_type):
    result = classify_text(text)
    assert result["type"] == expected_type


def test_unknown_text_falls_back_to_general_advisory():
    result = classify_text("nondescript filler that matches nothing")
    assert result["type"] == "general_advisory"
    assert 0.0 < result["confidence"] < 0.6  # low confidence on fallback


def test_confidence_higher_with_more_keyword_hits():
    high = classify_text("permit zoning variance setback approval LDC")
    low = classify_text("permit")
    assert high["confidence"] > low["confidence"]

"""extract_fields v0.2.0a is a mock that derives a canned skeleton from text (spec §4.1)."""
from mcp_tools.extract_fields.server import extract_text


def test_extract_returns_subject_capped_to_50_chars():
    text = "x" * 200
    out = extract_text(text)
    assert len(out["subject"]) <= 50


def test_extract_includes_required_fields():
    out = extract_text("Need legal review on permit denial for parcel 12345")
    expected_keys = {
        "subject", "legalQuestion", "factualBackground",
        "servicesRequested", "parties", "dates",
    }
    assert set(out.keys()) >= expected_keys


def test_short_input_still_returns_complete_shape():
    out = extract_text("a")
    assert isinstance(out["servicesRequested"], list)
    assert isinstance(out["parties"], list)
    assert isinstance(out["dates"], list)

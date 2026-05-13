"""Regex detectors for high-confidence PII patterns."""
from __future__ import annotations

import pytest

from services.redaction.detectors.regex_detectors import detect_all, DetectedSpan


def test_ssn_detected():
    spans = detect_all("Patient SSN is 123-45-6789 on file.")
    ssns = [s for s in spans if s.reason == "pii_ssn_or_id"]
    assert len(ssns) == 1
    assert ssns[0].text == "123-45-6789"


def test_phone_detected_both_formats():
    text = "Call (941) 555-0142 or 941-555-0143 anytime."
    spans = detect_all(text)
    phones = [s for s in spans if s.reason == "pii_contact"]
    assert len(phones) == 2


def test_bates_detected():
    spans = detect_all("See Bates MC-104301 for the exhibit.")
    bates = [s for s in spans if s.reason == "other"]
    assert any(s.text == "MC-104301" for s in bates)


def test_no_false_positive_on_dates():
    # 2024-01-15 looks like a date, not an SSN
    spans = detect_all("Filing date 2024-01-15.")
    ssns = [s for s in spans if s.reason == "pii_ssn_or_id"]
    assert ssns == []


def test_no_false_positive_on_empty_text():
    assert detect_all("") == []


def test_detector_label_present():
    spans = detect_all("SSN 123-45-6789")
    assert all(s.detector.startswith("regex:") for s in spans)

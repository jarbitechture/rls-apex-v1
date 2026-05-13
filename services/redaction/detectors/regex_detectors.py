"""High-confidence regex detectors for PII redaction.

Per spec ADR-007: regex catches deterministic patterns; LLM detector handles
ambiguous spans (names, addresses, privileged content). Both write to
redaction_audit with detector="regex:<name>" or "llm:<model>".
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DetectedSpan:
    start: int
    end: int
    text: str
    reason: str  # matches RedactionReason enum value
    detector: str  # "regex:ssn" | "regex:phone" | "regex:bates"


# SSN — three groups of digits separated by dashes; word-boundary anchored
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Phone — accept both (NNN) NNN-NNNN and NNN-NNN-NNNN
PHONE_RE = re.compile(r"\(\d{3}\)\s\d{3}-\d{4}|\b\d{3}-\d{3}-\d{4}\b")

# Bates label — MC-NNNNNN format
BATES_RE = re.compile(r"\bMC-\d{6}\b")


def detect_all(text: str) -> list[DetectedSpan]:
    """Run all regex detectors over `text`; return non-overlapping spans."""
    spans: list[DetectedSpan] = []
    for m in SSN_RE.finditer(text):
        spans.append(DetectedSpan(
            start=m.start(), end=m.end(), text=m.group(),
            reason="pii_ssn_or_id", detector="regex:ssn",
        ))
    for m in PHONE_RE.finditer(text):
        spans.append(DetectedSpan(
            start=m.start(), end=m.end(), text=m.group(),
            reason="pii_contact", detector="regex:phone",
        ))
    for m in BATES_RE.finditer(text):
        spans.append(DetectedSpan(
            start=m.start(), end=m.end(), text=m.group(),
            reason="other", detector="regex:bates",
        ))
    # De-overlap: sort by start; drop spans that fall inside earlier-finishing ones
    spans.sort(key=lambda s: (s.start, -s.end))
    deduped: list[DetectedSpan] = []
    for s in spans:
        if deduped and s.start < deduped[-1].end:
            continue
        deduped.append(s)
    return deduped

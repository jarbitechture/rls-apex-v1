"""W4 — validate 18 stub opinions meet spec criteria.

Per spec ADR-003 + §15 W4:
- 18 files committed under corpus-data/stubs/
- Named stub-{matter_type}-{1,2,3}.md
- Each >=800 words
- Each MUST contain:
  >=1 SSN regex match (\\d{3}-\\d{2}-\\d{4})
  >=1 phone match (\\(\\d{3}\\) \\d{3}-\\d{4} or \\d{3}-\\d{3}-\\d{4})
  >=1 Bates label (MC-\\d{6} format)
  >=1 attorney-client work-product marker ([ATTORNEY-CLIENT PRIVILEGED] or similar)
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


STUBS_DIR = Path(__file__).resolve().parents[3] / "corpus-data" / "stubs"

MATTER_TYPES = [
    "code_enforcement_litigation",
    "permit_or_zoning",
    "procurement",
    "public_records",
    "general_advisory",
    "other",
]

SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE_RE = re.compile(r"\(\d{3}\) \d{3}-\d{4}|\d{3}-\d{3}-\d{4}")
BATES_RE = re.compile(r"\bMC-\d{6}\b")
PRIVILEGE_RE = re.compile(
    r"\[ATTORNEY[- ]CLIENT PRIVILEGED\]|\[WORK PRODUCT\]|\[PRIVILEGED\]",
    re.IGNORECASE,
)


def test_eighteen_stub_files_exist():
    assert STUBS_DIR.exists(), f"stubs dir missing: {STUBS_DIR}"
    stub_files = sorted(STUBS_DIR.glob("stub-*.md"))
    assert len(stub_files) == 18, (
        f"expected 18 stub files, got {len(stub_files)}: "
        f"{[f.name for f in stub_files]}"
    )


def test_three_stubs_per_matter_type():
    for matter_type in MATTER_TYPES:
        files = sorted(STUBS_DIR.glob(f"stub-{matter_type}-*.md"))
        assert len(files) == 3, (
            f"expected 3 stubs for {matter_type}, got {len(files)}"
        )


@pytest.mark.parametrize("matter_type", MATTER_TYPES)
@pytest.mark.parametrize("idx", [1, 2, 3])
def test_stub_word_count_at_least_800(matter_type, idx):
    path = STUBS_DIR / f"stub-{matter_type}-{idx}.md"
    text = path.read_text()
    words = len(text.split())
    assert words >= 800, f"{path.name} has only {words} words; >=800 required"


@pytest.mark.parametrize("matter_type", MATTER_TYPES)
@pytest.mark.parametrize("idx", [1, 2, 3])
def test_stub_contains_required_pii_patterns(matter_type, idx):
    path = STUBS_DIR / f"stub-{matter_type}-{idx}.md"
    text = path.read_text()
    assert SSN_RE.search(text), f"{path.name} missing SSN pattern"
    assert PHONE_RE.search(text), f"{path.name} missing phone pattern"
    assert BATES_RE.search(text), f"{path.name} missing Bates label"
    assert PRIVILEGE_RE.search(text), f"{path.name} missing privilege marker"

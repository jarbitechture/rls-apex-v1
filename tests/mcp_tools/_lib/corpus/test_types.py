"""Hit model unit tests."""
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from mcp_tools._lib.corpus.types import Hit


def test_hit_minimal_required_fields():
    h = Hit(
        id=42,
        source_id="municode.ldc.6.4",
        source_type="ldc",
        citation="Manatee County LDC §6.4(a)(2) (2024)",
        body="No structure shall be erected without...",
        score=0.87,
    )
    assert h.id == 42
    assert h.source_type == "ldc"
    assert h.score == pytest.approx(0.87)
    # metadata defaults to empty dict
    assert h.metadata == {}


def test_hit_full_metadata_roundtrip():
    meta = {"matter_type": "permit_or_zoning", "retrieved_at": "2026-05-11T10:00:00Z"}
    h = Hit(
        id=1,
        source_id="internal_opinion.stub.1",
        source_type="internal_opinion",
        citation="Internal Opinion 2026-001",
        body="...",
        score=0.5,
        section_path="opinion / recommendation",
        metadata=meta,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_to=None,
    )
    dumped = h.model_dump()
    rebuilt = Hit(**dumped)
    assert rebuilt.metadata == meta
    assert rebuilt.section_path == "opinion / recommendation"


def test_hit_rejects_score_out_of_range_lower():
    with pytest.raises(ValidationError):
        Hit(
            id=1, source_id="x", source_type="ldc", citation="x", body="x",
            score=-0.1,
        )


def test_hit_rejects_score_out_of_range_upper():
    with pytest.raises(ValidationError):
        Hit(
            id=1, source_id="x", source_type="ldc", citation="x", body="x",
            score=1.5,
        )


def test_hit_rejects_unknown_source_type():
    with pytest.raises(ValidationError):
        Hit(
            id=1, source_id="x", source_type="bogus_source", citation="x", body="x",
            score=0.5,
        )

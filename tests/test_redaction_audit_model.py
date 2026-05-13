"""RedactionAuditRow Pydantic model — matches alembic schema, validates enum + spans.

Mirrors columns from migration b1d742f07a46 (redaction_audit). reviewer_upn and
reviewed_at are nullable to support the human-review gate (ADR-007); chunk_id is
nullable until the redacted body is INSERTed into corpus_chunks.
"""
from __future__ import annotations

import pytest

from apps.gateway.db.models import RedactionAuditRow, RedactionReason


def test_minimal_required_fields():
    row = RedactionAuditRow(
        source_doc_id="stub-code_enforcement_litigation-1",
        original_span_start=10,
        original_span_end=20,
        original_text="123-45-6789",
        redaction_reason=RedactionReason.pii_ssn_or_id,
        detector="regex:ssn",
    )
    assert row.reviewer_upn is None
    assert row.reviewed_at is None
    assert row.chunk_id is None
    assert row.id is None
    assert row.created_at is None


def test_redaction_reason_enum_accepts_all_documented_values():
    for value in [
        "pii_name",
        "pii_address",
        "pii_dob",
        "pii_ssn_or_id",
        "pii_contact",
        "privileged",
        "settlement_terms",
        "ongoing_litigation",
        "other",
    ]:
        row = RedactionAuditRow(
            source_doc_id="x",
            original_span_start=0,
            original_span_end=1,
            original_text="x",
            redaction_reason=value,
            detector="regex:test",
        )
        assert row.redaction_reason == value


def test_redaction_reason_rejects_unknown():
    with pytest.raises(ValueError, match="redaction_reason"):
        RedactionAuditRow(
            source_doc_id="x",
            original_span_start=0,
            original_span_end=1,
            original_text="x",
            redaction_reason="not_a_valid_reason",
            detector="regex:test",
        )


def test_span_must_be_non_negative():
    with pytest.raises(ValueError):
        RedactionAuditRow(
            source_doc_id="x",
            original_span_start=-1,
            original_span_end=5,
            original_text="x",
            redaction_reason="other",
            detector="x",
        )


def test_span_end_must_exceed_start():
    with pytest.raises(ValueError, match="span_end"):
        RedactionAuditRow(
            source_doc_id="x",
            original_span_start=10,
            original_span_end=5,
            original_text="x",
            redaction_reason="other",
            detector="x",
        )

"""Pydantic models reflect domain.yaml. Round-trip JSON without loss."""
from datetime import datetime, timezone

from apps.gateway.db.models import (
    LineageEvent,
    MatterClassification,
    RlsRecord,
    RlsStatus,
    RlsType,
    ValidationIssue,
    ValidationResult,
)


def test_rls_record_roundtrip():
    record = RlsRecord(
        rls_id="RLS-26-0141",
        matter_id=None,
        classification=MatterClassification.PUBLIC_RECORD,
        status=RlsStatus.DRAFT,
        type=RlsType.PERMIT_OR_ZONING,
        subject="Vested rights for East Bradenton Park",
        department="Development Services",
        contact_name="Jane Planner",
        contact_extension="1234",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        lineage_head="0" * 64,
    )
    serialized = record.model_dump_json()
    restored = RlsRecord.model_validate_json(serialized)
    assert restored == record


def test_validation_result_blocking_and_warnings():
    result = ValidationResult(
        blocking=[
            ValidationIssue(
                code="MISSING_ACCOUNT_KEY",
                severity="blocking",
                message="x",
                field="accountKey",
            )
        ],
        warnings=[
            ValidationIssue(
                code="NO_SERVICES",
                severity="warning",
                message="y",
                field="servicesRequested",
            )
        ],
    )
    assert len(result.blocking) == 1
    assert result.blocking[0].severity == "blocking"


def test_lineage_event_chains_via_prev_hash():
    e1 = LineageEvent(
        rls_id="RLS-26-0141",
        sequence=1,
        prev_hash=None,
        this_hash="a" * 64,
        payload={},
    )
    e2 = LineageEvent(
        rls_id="RLS-26-0141",
        sequence=2,
        prev_hash="a" * 64,
        this_hash="b" * 64,
        payload={},
    )
    assert e2.prev_hash == e1.this_hash

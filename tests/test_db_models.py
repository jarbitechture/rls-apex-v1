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


def test_optional_fields_default_to_none():
    """matter_id and prev_hash should be omittable (None default), not required."""
    from datetime import datetime, timezone
    from apps.gateway.db.models import RlsRecord, MatterClassification, RlsStatus, RlsType, LineageEvent

    record = RlsRecord(
        rls_id="RLS-26-0001",
        # matter_id intentionally omitted
        classification=MatterClassification.PUBLIC_RECORD,
        status=RlsStatus.DRAFT,
        type=RlsType.PERMIT_OR_ZONING,
        subject="Test",
        department="Test",
        contact_name="Test",
        contact_extension="1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        lineage_head="0" * 64,
    )
    assert record.matter_id is None

    genesis = LineageEvent(
        rls_id="RLS-26-0001",
        sequence=1,
        # prev_hash intentionally omitted (genesis event)
        this_hash="a" * 64,
        payload={},
    )
    assert genesis.prev_hash is None


def test_rls_payload_accepts_camel_and_snake_input():
    """RlsPayload accepts both wire (camelCase) and Python (snake_case) keys."""
    from apps.gateway.db.models import RlsPayload

    camel_input = {
        "accountKey": "010-1234-560",
        "legalQuestion": "Q",
        "factualBackground": "F",
        "servicesRequested": ["written_response"],
    }
    snake_input = {
        "account_key": "010-1234-560",
        "legal_question": "Q",
        "factual_background": "F",
        "services_requested": ["written_response"],
    }

    p_camel = RlsPayload.model_validate(camel_input)
    p_snake = RlsPayload.model_validate(snake_input)

    assert p_camel.account_key == "010-1234-560"
    assert p_snake.account_key == "010-1234-560"
    assert p_camel == p_snake


def test_rls_payload_emits_camelcase_with_by_alias():
    """model_dump(by_alias=True) emits camelCase for the wire."""
    from apps.gateway.db.models import RlsPayload

    p = RlsPayload(account_key="ABC", legal_question="Q")
    wire = p.model_dump(by_alias=True)
    assert "accountKey" in wire
    assert "legalQuestion" in wire
    assert "account_key" not in wire

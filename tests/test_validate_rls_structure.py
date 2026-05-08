"""validate_rls_structure produces blocking + warnings against domain.yaml constraints (spec §4.3)."""
from mcp_tools.validate_rls_structure.server import validate_dict, validate_payload
from apps.gateway.db.models import RlsPayload, RlsType


def test_missing_account_key_is_blocking():
    payload = RlsPayload(
        subject="Vested rights",
        department="Development Services",
        contact_name="Jane",
        contact_extension="1234",
        type=RlsType.PERMIT_OR_ZONING,
        legal_question="Q",
        factual_background="F",
    )
    result = validate_payload(payload)
    codes = {issue.code for issue in result.blocking}
    assert "MISSING_ACCOUNT_KEY" in codes


def test_subject_over_50_chars_is_blocking():
    raw = {
        "subject": "x" * 51,
        "department": "X",
        "contact_name": "X",
        "contact_extension": "1",
        "account_key": "ABC",
    }
    result = validate_dict(raw)
    codes = {issue.code for issue in result.blocking}
    assert "SUBJECT_TOO_LONG" in codes


def test_no_services_requested_is_warning_not_blocking():
    payload = RlsPayload(
        subject="Q",
        department="DS",
        contact_name="J",
        contact_extension="1",
        account_key="ABC123",
        type=RlsType.GENERAL_ADVISORY,
        legal_question="Q",
        factual_background="F",
        services_requested=[],
    )
    result = validate_payload(payload)
    blocking_codes = {i.code for i in result.blocking}
    warning_codes = {i.code for i in result.warnings}
    assert "NO_SERVICES_REQUESTED" in warning_codes
    assert "NO_SERVICES_REQUESTED" not in blocking_codes


def test_complete_payload_passes_with_no_blocking():
    payload = RlsPayload(
        subject="Q",
        department="DS",
        contact_name="J",
        contact_extension="1",
        account_key="ABC123",
        type=RlsType.GENERAL_ADVISORY,
        legal_question="Question text",
        factual_background="Background text",
        services_requested=["written_response"],
    )
    result = validate_payload(payload)
    assert result.blocking == []

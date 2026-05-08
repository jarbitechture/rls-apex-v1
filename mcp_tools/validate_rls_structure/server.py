"""validate_rls_structure — pure-logic structural validator.

Spec §4.3. Returns ValidationResult with blocking + warnings.

This tool has no backend (no Postgres, no retrieval), so per spec §12.2
it has NO L2 breaker. Failures here are input-validation errors that
surface through the existing `blocking` mechanism.
"""
from __future__ import annotations

from typing import Any

from apps.gateway.db.models import (
    RlsPayload,
    ValidationIssue,
    ValidationResult,
)
from mcp_tools._lib.server import build_tool_app

# D1 contract: build_tool_app returns (app, roi, require_actor). Tools call
# require_actor() at the top of every @app.tool function — JWT enforcement
# is per-function in fastmcp 2.3.0 (no app.middleware available).
app, roi, require_actor = build_tool_app("validate_rls_structure")

REQUIRED_FIELDS = {
    "subject": "MISSING_SUBJECT",
    "department": "MISSING_DEPARTMENT",
    "contact_name": "MISSING_CONTACT_NAME",
    "contact_extension": "MISSING_CONTACT_EXTENSION",
    "account_key": "MISSING_ACCOUNT_KEY",
}
SUBJECT_MAX = 50


def validate_payload(payload: RlsPayload) -> ValidationResult:
    """Validate a typed RlsPayload. Convenience wrapper over validate_dict."""
    return validate_dict(payload.model_dump())


def validate_dict(raw: dict[str, Any]) -> ValidationResult:
    """Validate a raw dict against domain.yaml constraints (spec §4.3).

    Pure logic — no I/O. Used directly by /api/validate (E2) and indirectly
    via the @app.tool wrapper for MCP transport.
    """
    blocking: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    for field, code in REQUIRED_FIELDS.items():
        value = raw.get(field, "")
        if not value or (isinstance(value, str) and not value.strip()):
            blocking.append(ValidationIssue(
                code=code,
                severity="blocking",
                message=f"{field} is required.",
                field=field,
            ))

    subject = raw.get("subject", "")
    if isinstance(subject, str) and len(subject) > SUBJECT_MAX:
        blocking.append(ValidationIssue(
            code="SUBJECT_TOO_LONG",
            severity="blocking",
            message=f"Subject is {len(subject)} chars; max is {SUBJECT_MAX}.",
            field="subject",
        ))

    if not raw.get("services_requested"):
        warnings.append(ValidationIssue(
            code="NO_SERVICES_REQUESTED",
            severity="warning",
            message="No legal services requested.",
            field="services_requested",
        ))

    if not raw.get("legal_question") or not raw.get("factual_background"):
        warnings.append(ValidationIssue(
            code="LEGAL_QUESTION_OR_BACKGROUND_THIN",
            severity="warning",
            message="Legal question or factual background is empty.",
            field="legal_question",
        ))

    return ValidationResult(blocking=blocking, warnings=warnings)


@app.tool()
async def validate_rls_structure(rls_payload: dict) -> dict:
    """MCP tool entry point.

    Returns a serialized ValidationResult.
    """
    actor = require_actor()  # D1 contract: every tool calls require_actor() at top
    result = validate_dict(rls_payload)
    await roi.emit("tool_invocation", {
        "actor_id": actor.actor_id,
        "success": True,
        "blocking_count": len(result.blocking),
        "warnings_count": len(result.warnings),
    })
    return result.model_dump()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=30100, log_level="info")

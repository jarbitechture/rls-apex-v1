"""Pydantic models for RLS Apex domain entities.

Hand-written from domain.yaml for v0.2.0a. A future codegen step (deferred)
will regenerate this file. Until then, edits to domain.yaml require
hand-syncing here.

# W4 verified 2026-05-08: no Worksheet polymorphic single-table assumptions
# baked in. Matter and RLS are concrete; adding Permit / HrQa / BudgetMemo
# later means new tables + a thin discriminator view, not a schema rewrite.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class MatterClassification(str, Enum):
    PRIVILEGED = "privileged"
    PUBLIC_RECORD = "public_record"
    CONFIDENTIAL = "confidential"


class RlsStatus(str, Enum):
    DRAFT = "Draft"
    NEEDS_FIXES = "NeedsFixes"
    READY_FOR_CAO = "ReadyForCAO"
    ACKNOWLEDGED = "Acknowledged"
    NEEDS_REVISION = "NeedsRevision"
    REJECTED = "Rejected"


class RlsType(str, Enum):
    PERMIT_OR_ZONING = "permit_or_zoning"
    PROCUREMENT = "procurement"
    PUBLIC_RECORDS = "public_records"
    CODE_ENFORCEMENT_LITIGATION = "code_enforcement_litigation"
    GENERAL_ADVISORY = "general_advisory"


class RlsRecord(BaseModel):
    """Stored RLS row. Mirrors `rls` table in 001_baseline migration."""

    model_config = ConfigDict(frozen=False, extra="forbid")

    rls_id: str = Field(pattern=r"^RLS-\d{2}-\d{4,}$")
    matter_id: str | None = None
    classification: MatterClassification
    status: RlsStatus
    type: RlsType
    subject: str = Field(max_length=240)
    department: str
    contact_name: str
    contact_extension: str
    created_at: datetime
    updated_at: datetime
    lineage_head: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class RlsPayload(BaseModel):
    """Wire shape sent to /api/intake and /api/validate.

    Subset of RlsRecord plus mutable form state; no IDs or timestamps.
    Uses camelCase aliases on the wire, snake_case in Python. Callers must
    pass `by_alias=True` to `model_dump()` / `model_dump_json()` to emit
    the wire shape; default dump uses Python field names (snake_case).
    """

    model_config = ConfigDict(
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
    )

    subject: str = Field(default="", max_length=50)  # spec §4.1 — trimmed at extraction
    department: str = Field(default="")
    division: str = Field(default="")
    account_key: str = Field(default="")
    contact_name: str = Field(default="")
    contact_extension: str = Field(default="")
    director: str = Field(default="")
    type: RlsType | None = None
    legal_question: str = Field(default="")
    factual_background: str = Field(default="")
    services_requested: list[str] = Field(default_factory=list)
    time_considerations: dict[str, Any] = Field(default_factory=dict)


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["blocking", "warning"]
    message: str
    field: str | None = None


class ValidationResult(BaseModel):
    blocking: list[ValidationIssue] = Field(default_factory=list)
    warnings: list[ValidationIssue] = Field(default_factory=list)


class LineageEvent(BaseModel):
    """Hash-chained audit row. Stored in `lineage_event` table."""

    model_config = ConfigDict(extra="forbid")

    rls_id: str
    sequence: int = Field(ge=1)
    prev_hash: str | None = None
    this_hash: str = Field(min_length=64, max_length=64)
    payload: dict[str, Any]

"""Pydantic models for RLS Apex domain entities.

Hand-written from domain.yaml for v0.2.0a. A future codegen step (deferred)
will regenerate this file. Until then, edits to domain.yaml require
hand-syncing here.

# W4 verified 2026-05-08: no Worksheet polymorphic single-table assumptions
# baked in. Matter and RLS are concrete; adding Permit / HrQa / BudgetMemo
# later means new tables + a thin discriminator view, not a schema rewrite.
"""
from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
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


SourceType = Literal[
    "ldc",
    "ordinance",
    "fl_ag_opinion",
    "internal_opinion",
    "procedure",
    "calendar",
]


class CorpusChunk(BaseModel):
    """Versioned corpus chunk — matches alembic corpus_chunks table.

    v0.2.1a Stream A produces these (scraped LDC + ordinances + FL AG opinions
    + calendar holidays); Stream B writes redacted internal_opinion rows;
    Stream C reads via hybrid retrieval. valid_from / valid_to is the
    point-in-time range (ADR-002).
    """

    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    source_id: str
    source_type: SourceType
    section_path: str
    citation: str
    body: str
    sha256: Annotated[str, Field(min_length=64, max_length=64)]
    valid_from: datetime
    valid_to: datetime | None = None
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    @field_validator("sha256")
    @classmethod
    def _sha256_hex(cls, v: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError("sha256 must be 64 lowercase hex chars")
        return v

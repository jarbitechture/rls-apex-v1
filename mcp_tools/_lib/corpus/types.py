"""Pydantic types for retrieval. Hit is the unit of retrieval output."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal[
    "ldc",
    "ordinance",
    "fl_ag_opinion",
    "internal_opinion",
    "procedure",
    "calendar",
]


class Hit(BaseModel):
    """One retrieval hit. Score is normalized to [0, 1] post-RRF."""

    model_config = ConfigDict(extra="forbid")

    id: int
    source_id: str
    source_type: SourceType
    citation: str
    body: str
    score: float = Field(ge=0.0, le=1.0)
    section_path: str | None = None
    metadata: dict = Field(default_factory=dict)
    valid_from: datetime | None = None
    valid_to: datetime | None = None

"""CorpusChunk Pydantic model — matches alembic schema, supports point-in-time queries."""
from __future__ import annotations

import pytest
from datetime import datetime, timezone

from apps.gateway.db.models import CorpusChunk


def test_corpus_chunk_minimal_required():
    chunk = CorpusChunk(
        source_id="municode.ldc.6.4",
        source_type="ldc",
        section_path="Chapter 6 / §6.4",
        citation="Manatee County LDC §6.4 (2024)",
        body="The applicant shall provide...",
        sha256="a" * 64,
        valid_from=datetime.now(timezone.utc),
    )
    assert chunk.valid_to is None
    assert chunk.metadata == {}


def test_source_type_rejects_unknown():
    with pytest.raises(ValueError, match="source_type"):
        CorpusChunk(
            source_id="x",
            source_type="not_a_known_type",
            section_path="x",
            citation="x",
            body="x",
            sha256="a" * 64,
            valid_from=datetime.now(timezone.utc),
        )


def test_sha256_must_be_64_hex():
    with pytest.raises(ValueError, match="sha256"):
        CorpusChunk(
            source_id="x",
            source_type="ldc",
            section_path="x",
            citation="x",
            body="x",
            sha256="too-short",
            valid_from=datetime.now(timezone.utc),
        )

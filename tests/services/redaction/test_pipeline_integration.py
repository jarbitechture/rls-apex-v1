"""Integration tests for the redaction pipeline orchestrator.

Tests use the real DB (db_pool fixture + alembic migrations) but mock:
- LlmDetector.detect — avoids Ollama dependency
- _get_roi_client — avoids real HTTP + filesystem writes
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.redaction.pipeline import PipelineResult, process_document

STUB_PATH = Path(__file__).parents[3] / "corpus-data" / "stubs" / "stub-code_enforcement_litigation-1.md"


@pytest.fixture
async def fresh_redaction_db(db_pool):
    async with db_pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE redaction_audit, corpus_chunks RESTART IDENTITY CASCADE"
        )
    return db_pool


@pytest.mark.integration
async def test_pipeline_detects_spans_from_stub(fresh_redaction_db):
    """Regex detectors find >= 10 spans in the stub doc; all written as pending audit rows."""
    mock_roi_client = MagicMock()
    mock_roi_client.emit_now = MagicMock()

    with patch("services.redaction.pipeline.LlmDetector") as mock_llm_cls, \
         patch("services.redaction.pipeline._get_roi_client", return_value=mock_roi_client):
        # LLM returns empty — regex-only path
        mock_llm_instance = mock_llm_cls.return_value
        mock_llm_instance.detect = AsyncMock(return_value=[])

        async with fresh_redaction_db.acquire() as conn:
            result = await process_document(
                conn,
                path=STUB_PATH,
                source_doc_id="stub-code-enf-1",
                llm_model="phi4",
            )
            rows = await conn.fetch(
                "SELECT * FROM redaction_audit WHERE source_doc_id = 'stub-code-enf-1'"
            )

    assert isinstance(result, PipelineResult)
    assert result.source_doc_id == "stub-code-enf-1"
    # Stub contains 10 Bates labels + 1 SSN + 1 phone = 12 regex spans
    assert result.spans_detected >= 10
    assert len(rows) == result.spans_detected
    # All written as pending (no reviewer)
    assert all(r["reviewer_upn"] is None for r in rows)
    # At least one pii_ssn_or_id span present
    reasons = {r["redaction_reason"] for r in rows}
    assert "pii_ssn_or_id" in reasons
    # ROI was emitted
    assert mock_roi_client.emit_now.called


@pytest.mark.integration
async def test_pipeline_merges_llm_and_regex_spans(fresh_redaction_db):
    """LLM spans that don't overlap with regex spans are added to the audit table."""
    mock_roi_client = MagicMock()
    mock_roi_client.emit_now = MagicMock()

    from services.redaction.detectors.regex_detectors import DetectedSpan

    # One novel LLM span that won't overlap with any regex-detected span
    novel_llm_span = DetectedSpan(
        start=0, end=10, text="Stub Title"[:10], reason="privileged", detector="llm:phi4"
    )

    with patch("services.redaction.pipeline.LlmDetector") as mock_llm_cls, \
         patch("services.redaction.pipeline._get_roi_client", return_value=mock_roi_client):
        mock_llm_instance = mock_llm_cls.return_value
        mock_llm_instance.detect = AsyncMock(return_value=[novel_llm_span])

        async with fresh_redaction_db.acquire() as conn:
            result = await process_document(
                conn,
                path=STUB_PATH,
                source_doc_id="stub-code-enf-2",
                llm_model="phi4",
            )
            rows = await conn.fetch(
                "SELECT redaction_reason FROM redaction_audit WHERE source_doc_id = 'stub-code-enf-2'"
            )

    reasons = {r["redaction_reason"] for r in rows}
    # Both regex spans (pii_ssn_or_id, pii_contact, other) and LLM span (privileged) present
    assert "privileged" in reasons
    assert "pii_ssn_or_id" in reasons
    # Total = regex (>=10) + 1 LLM novel span
    assert result.spans_detected >= 11
    assert mock_roi_client.emit_now.called

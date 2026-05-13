"""Redaction pipeline orchestrator.

Per ADR-007 Stream B: loads a document, runs regex detection, runs LLM
detection (circuit-breaker-wrapped), writes pending spans to redaction_audit,
and emits a ROI event.

Usage:
    result = await process_document(conn, path, source_doc_id)
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import asyncpg

from apps.gateway.sidecar._client import EVENT_KIND_TOOL_INVOCATION, RoiClient

from .audit import write_pending_spans
from .breaker import get_or_create_breaker
from .detectors.llm_detector import LlmDetector
from .detectors.regex_detectors import DetectedSpan, detect_all

logger = logging.getLogger(__name__)

_roi_client: RoiClient | None = None


def _get_roi_client() -> RoiClient:
    global _roi_client
    if _roi_client is None:
        endpoint = os.environ.get("ROI_SIDECAR_ENDPOINT", "http://localhost:8001/events")
        _roi_client = RoiClient(endpoint=endpoint)
    return _roi_client


@dataclass
class PipelineResult:
    source_doc_id: str
    spans_detected: int


async def process_document(
    conn: asyncpg.Connection,
    path: str | Path,
    source_doc_id: str,
    llm_model: str = "phi4",
) -> PipelineResult:
    """Run the full redaction detection pipeline for one document.

    Steps:
    1. Load text from ``path``.
    2. Run regex detectors (always; no breaker needed — pure CPU).
    3. Run LLM detector wrapped in a circuit breaker (failures are non-fatal).
    4. Merge spans (regex + LLM), de-duplicate by (start, end).
    5. Write all pending spans to redaction_audit.
    6. Emit ROI telemetry (fire-and-forget, never blocking).

    Returns a PipelineResult with the count of spans written.
    """
    started = time.monotonic()

    text = Path(path).read_text(encoding="utf-8")

    # Step 2: Regex detection (CPU-only, no breaker needed)
    regex_spans: list[DetectedSpan] = detect_all(text)

    # Step 3: LLM detection — circuit-breaker-wrapped
    llm_spans: list[DetectedSpan] = []
    breaker = get_or_create_breaker(f"llm_{llm_model}")
    detector = LlmDetector(model=llm_model)
    try:
        llm_spans = await breaker.call(lambda: detector.detect(text))
    except Exception as exc:
        logger.warning("LLM detector skipped (breaker open or error): %s", exc)

    # Step 4: Merge + de-duplicate by (start, end) — regex takes precedence
    seen: set[tuple[int, int]] = set()
    merged: list[DetectedSpan] = []
    for span in regex_spans + llm_spans:
        key = (span.start, span.end)
        if key not in seen:
            seen.add(key)
            merged.append(span)

    # Step 5: Write pending spans
    written = await write_pending_spans(conn, source_doc_id=source_doc_id, spans=merged)

    # Step 6: ROI emit — fire-and-forget, never blocks the caller
    duration = time.monotonic() - started
    success = True
    try:
        client = _get_roi_client()
        client.emit_now({
            "event_kind": EVENT_KIND_TOOL_INVOCATION,
            "workflow": "rls_apex.redaction",
            "tool": "rls_apex",
            "surface": "other",
            "task_type": "data_analysis",
            "user_id": "system.redaction",
            "dept": "system",
            "role_band": "system",
            "duration_s": duration,
            "success": success,
            "extra": {
                "source_doc_id": source_doc_id,
                "spans_regex": len(regex_spans),
                "spans_llm": len(llm_spans),
                "spans_total": written,
            },
        })
    except Exception as exc:
        logger.debug("ROI emit failed for %s: %s", source_doc_id, exc)

    return PipelineResult(source_doc_id=source_doc_id, spans_detected=written)

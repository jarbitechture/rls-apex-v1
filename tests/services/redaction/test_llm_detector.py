"""LLM detector — Ollama chat-model wrapper for ambiguous spans (names, addresses, privileged content)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from services.redaction.detectors.llm_detector import LlmDetector
from services.redaction.detectors.regex_detectors import DetectedSpan


@pytest.fixture
def detector():
    return LlmDetector(model="phi4", ollama_url="http://localhost:11434")


@pytest.mark.asyncio
async def test_llm_detector_parses_structured_response(detector):
    """LLM returns structured JSON of spans; detector parses to DetectedSpan list."""
    fake_response = {
        "spans": [
            {"start": 10, "end": 22, "text": "John Synthwood", "reason": "pii_name"},
            {"start": 45, "end": 70, "text": "1234 Synthetic Lane", "reason": "pii_address"},
        ]
    }
    with patch.object(detector, "_call_ollama", new=AsyncMock(return_value=fake_response)):
        spans = await detector.detect("Some document text containing John Synthwood at 1234 Synthetic Lane today.")
    assert len(spans) == 2
    assert spans[0].text == "John Synthwood"
    assert spans[0].reason == "pii_name"
    assert spans[0].detector.startswith("llm:")


@pytest.mark.asyncio
async def test_llm_detector_handles_empty_response(detector):
    with patch.object(detector, "_call_ollama", new=AsyncMock(return_value={"spans": []})):
        spans = await detector.detect("clean text with no PII")
    assert spans == []


@pytest.mark.asyncio
async def test_llm_detector_handles_malformed_response(detector):
    """Defensive: if Ollama returns garbage, log + return empty list (don't raise)."""
    with patch.object(detector, "_call_ollama", new=AsyncMock(return_value={"unexpected_key": "garbage"})):
        spans = await detector.detect("any text")
    assert spans == []

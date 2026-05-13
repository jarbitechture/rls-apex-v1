"""LLM-assisted detection for ambiguous redaction spans.

Per spec ADR-007: LLM catches what regex can't (names, addresses, contextual
privilege markers). Returns structured spans for human review (queue UX in
v0.2.1b; manual psql review in v0.2.1a).

Model: Ollama-hosted chat model (default phi4 — fast + cheap). User can override
via constructor or env var OLLAMA_REDACTION_MODEL.

Prompt strategy: instruct the model to return JSON with explicit (start, end,
text, reason) per span. Mismatches between LLM-claimed start/end and actual
text positions are tolerated by re-locating the span via str.find.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

import httpx

from .regex_detectors import DetectedSpan


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a public-records redaction assistant for the Manatee County Attorney's office.

Identify spans in the input text that should be redacted under Florida public-records law. Categories:
- pii_name: individual names (NOT party names in published case law)
- pii_address: physical addresses
- pii_dob: dates of birth
- pii_contact: emails (phones are caught by regex)
- privileged: attorney-client work product
- settlement_terms: confidential settlement language
- ongoing_litigation: identifiers tied to pending matters

Return ONLY a JSON object: {"spans": [{"start": int, "end": int, "text": str, "reason": str}, ...]}
If nothing should be redacted, return {"spans": []}."""


@dataclass
class LlmDetector:
    model: str = "phi4"
    ollama_url: str = "http://localhost:11434"
    timeout_s: float = 30.0

    async def _call_ollama(self, text: str) -> dict:
        """Single Ollama chat call returning parsed JSON."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "format": "json",
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            r = await client.post(f"{self.ollama_url}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
        # Ollama wraps response in {message: {content: "..."}}
        content = data.get("message", {}).get("content", "{}")
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("LLM detector returned non-JSON content: %r", content[:200])
            return {"spans": []}

    async def detect(self, text: str) -> list[DetectedSpan]:
        """Run LLM detection; return DetectedSpan list."""
        try:
            response = await self._call_ollama(text)
        except Exception as exc:
            logger.warning("LLM detector call failed: %s", exc)
            return []

        raw_spans = response.get("spans", [])
        if not isinstance(raw_spans, list):
            logger.warning("LLM detector returned non-list spans: %r", raw_spans)
            return []

        spans: list[DetectedSpan] = []
        for raw in raw_spans:
            if not isinstance(raw, dict):
                continue
            try:
                start = int(raw["start"])
                end = int(raw["end"])
                t = str(raw["text"])
                reason = str(raw["reason"])
            except (KeyError, ValueError, TypeError):
                continue
            # Sanity: if LLM-reported start/end don't match the actual text, re-locate
            if text[start:end] != t:
                relocated = text.find(t)
                if relocated >= 0:
                    start = relocated
                    end = relocated + len(t)
                else:
                    continue  # span text not found; skip
            spans.append(DetectedSpan(
                start=start, end=end, text=t,
                reason=reason, detector=f"llm:{self.model}",
            ))
        return spans

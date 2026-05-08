"""classify_matter — v0.2.0a mock implementation (spec §4.1, §7 v0.2.0).

Real classifier comes in v0.2.1+ (LLM call to Qwen on Ollama). For v0.2.0a,
this regex mock returns canned classifications based on keyword presence.
The shape matches the real tool's contract.
"""
from __future__ import annotations
import math
import re
from typing import Any

from mcp_tools._lib.server import build_tool_app

app, roi, require_actor = build_tool_app("classify_matter")

KEYWORDS: dict[str, list[str]] = {
    "code_enforcement_litigation": [
        r"\bNOV\b", r"\bnotice of violation\b", r"\bcode enforcement\b",
        r"\blien\b", r"\bspecial magistrate\b", r"\bfine[s]?\b",
    ],
    "permit_or_zoning": [
        r"\bpermit\b", r"\bzoning\b", r"\bvariance\b", r"\bsetback\b",
        r"\bvested rights\b", r"\bLDC\b", r"\bsite plan\b", r"\bapproval\b",
    ],
    "procurement": [
        r"\bprocurement\b", r"\bcontract\b", r"\bRFP\b", r"\bvendor\b",
        r"\bbid\b", r"\bsolicitation\b",
    ],
    "public_records": [
        r"\bpublic records\b", r"\bChapter 119\b", r"\brecords request\b",
        r"\bjournalist\b", r"\bredact\b",
    ],
    "general_advisory": [
        r"\badvisory\b", r"\bethics\b", r"\bopinion\b", r"\bSunshine\b",
    ],
}


def classify_text(text: str) -> dict[str, Any]:
    hits: dict[str, int] = {}
    for type_, patterns in KEYWORDS.items():
        count = sum(1 for p in patterns if re.search(p, text, re.IGNORECASE))
        hits[type_] = count

    best_type = max(hits, key=lambda k: hits[k])
    best_count = hits[best_type]
    if best_count == 0:
        return {"type": "general_advisory", "confidence": 0.2}

    # Confidence: 1 - exp(-0.4 * hits) capped at 0.95.
    confidence = min(0.95, 1.0 - math.exp(-0.4 * best_count))
    return {"type": best_type, "confidence": round(confidence, 3)}


@app.tool()
async def classify_matter(draft_text: str) -> dict:
    actor = require_actor()  # D1 contract
    result = classify_text(draft_text)
    await roi.emit("tool_invocation", {
        "actor_id": actor.actor_id,
        "success": True,
        "type": result["type"],
    })
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=30101, log_level="info")

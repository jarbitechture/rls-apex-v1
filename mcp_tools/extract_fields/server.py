"""extract_fields — v0.2.0a mock (spec §4.1).

Real extractor comes in v0.2.1+ (LLM-driven). For v0.2.0a, this returns
a canned skeleton derived from simple heuristics: first sentence becomes
subject (truncated), full text becomes factual_background, an empty
legal_question prompts the user to fill it.

Note: returns camelCase keys (`legalQuestion`, `factualBackground`,
`servicesRequested`) to match the wire shape in spec §4.1. RlsPayload's
camelCase aliasing (B1) consumes this directly.
"""
from __future__ import annotations
from typing import Any

from mcp_tools._lib.server import build_tool_app

app, roi, require_actor = build_tool_app("extract_fields")

_EMIT_DEFAULTS: dict = {
    "workflow": "rls_apex.mcp.extract_fields",
    "tool": "rls_apex",
    "task_type": "data_analysis",
    "dept": "DEV",
    "role_band": "professional",
}

SUBJECT_MAX = 50


def extract_text(draft_text: str) -> dict[str, Any]:
    text = draft_text.strip()
    first_period = text.find(".")
    first_sentence = text[:first_period] if first_period > 0 else text
    subject = first_sentence[:SUBJECT_MAX].strip()

    return {
        "subject": subject,
        "legalQuestion": "",  # user fills — spec §5.1 co-authoring
        "factualBackground": text,
        "servicesRequested": [],
        "parties": [],
        "dates": [],
    }


@app.tool()
async def extract_fields(draft_text: str) -> dict:
    actor = require_actor()  # D1 contract
    try:
        result = extract_text(draft_text)
    except Exception:
        await roi.emit("tool_invocation", {
            **_EMIT_DEFAULTS,
            "user_id": actor.actor_id,
            "success": False,
        })
        raise
    await roi.emit("tool_invocation", {
        **_EMIT_DEFAULTS,
        "user_id": actor.actor_id,
        "success": True,
    })
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=30102, log_level="info")

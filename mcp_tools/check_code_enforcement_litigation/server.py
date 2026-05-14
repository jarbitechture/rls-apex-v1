"""check_code_enforcement_litigation — L1 MCP tool: deterministic CE-litigation validator.

Spec §7.1 and Plan D Task 1. Pure regex + dict rule engine — no corpus retrieval,
no LLM calls, no database access.

No external calls, no breaker needed (per microservices-architect lens — L1 is pure rule engine)

Port 30105.

Blocking rules (§7.1):
    CE_NOV_DATE_MISSING:         NOV referenced in factualBackground without a date.
    CE_HEARING_DEADLINE_MISSING: Special magistrate hearing mentioned without deadline field.
"""
from __future__ import annotations

import re
from typing import Any

from mcp_tools._lib.server import build_tool_app

# D1 contract: build_tool_app returns (app, roi, require_actor).
app, roi, require_actor = build_tool_app("check_code_enforcement_litigation")

# ---------------------------------------------------------------------------
# Compiled regex patterns (verbatim from spec §7.1)
# ---------------------------------------------------------------------------

_NOV_REGEX = re.compile(r"\b(NOV|notice of violation)\b", re.IGNORECASE)
_NOV_DATE_REGEX = re.compile(
    r"(NOV[^.]*\d{4})|"
    r"(NOV[^.]*\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4})|"
    r"(dated\s+\w+\s+\d{1,2},?\s*\d{4})|"
    r"(dated\s+\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_SPECIAL_MAGISTRATE_REGEX = re.compile(
    r"special\s+magistrate.*(hearing|pending|scheduled)", re.IGNORECASE
)

_EMIT_DEFAULTS: dict[str, Any] = {
    "workflow": "rls_apex.mcp.check_code_enforcement_litigation",
    "tool": "rls_apex",
    "task_type": "validation",
    "dept": "DEV",
    "role_band": "professional",
}


@app.tool()
async def check_code_enforcement_litigation(
    rls_payload: dict,
    matter_type: str | None = None,
) -> dict:
    """Validate a CE-litigation RLS payload against L1 deterministic rules.

    Args:
        rls_payload: The structured RLS packet dict (must include at minimum
            ``factualBackground`` and optionally ``deadline``).
        matter_type: Caller-supplied matter type string. If not
            ``"code_enforcement_litigation"`` the tool returns immediately with
            ``applicable=False`` (no rules apply).

    Returns:
        Dict with keys:
            ``blocking``   — list of blocking-rule dicts (code, message, field)
            ``warnings``   — list of warning dicts (reserved; currently always [])
            ``applicable`` — bool, False when matter_type does not match
    """
    actor = require_actor()

    applicable = matter_type == "code_enforcement_litigation"

    if not applicable:
        # Short-circuit: emit ROI then return
        try:
            await roi.emit(
                "tool_invocation",
                {
                    **_EMIT_DEFAULTS,
                    "user_id": actor.actor_id,
                    "surface": "mcp",
                    "duration_s": 0.0,
                    "success": True,
                    "extra": {
                        "matter_type": matter_type,
                        "applicable": False,
                        "blocking_count": 0,
                    },
                },
            )
        except Exception:
            pass
        return {"blocking": [], "warnings": [], "applicable": False}

    # --- Run deterministic rules -----------------------------------------
    blocking: list[dict] = []
    factual = rls_payload.get("factualBackground", "") or ""
    deadline = rls_payload.get("deadline")

    # Rule 1: CE_NOV_DATE_MISSING
    if _NOV_REGEX.search(factual) and not _NOV_DATE_REGEX.search(factual):
        blocking.append(
            {
                "code": "CE_NOV_DATE_MISSING",
                "message": (
                    "Notice of Violation (NOV) is referenced but no issue date was found. "
                    "Include the NOV date in the factual background."
                ),
                "field": "factualBackground",
            }
        )

    # Rule 2: CE_HEARING_DEADLINE_MISSING
    if _SPECIAL_MAGISTRATE_REGEX.search(factual) and not deadline:
        blocking.append(
            {
                "code": "CE_HEARING_DEADLINE_MISSING",
                "message": (
                    "A special magistrate hearing is referenced but the deadline field "
                    "is missing. Provide the hearing deadline date."
                ),
                "field": "deadline",
            }
        )

    try:
        await roi.emit(
            "tool_invocation",
            {
                **_EMIT_DEFAULTS,
                "user_id": actor.actor_id,
                "surface": "mcp",
                "duration_s": 0.0,
                "success": True,
                "extra": {
                    "matter_type": matter_type,
                    "applicable": True,
                    "blocking_count": len(blocking),
                },
            },
        )
    except Exception:
        pass

    return {"blocking": blocking, "warnings": [], "applicable": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=30105, log_level="info")

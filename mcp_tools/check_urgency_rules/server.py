"""check_urgency_rules MCP tool — port 30106.

Plan D Task 3 (L2). Validates urgency=critical packets for three blocking rules:
  URG_DEADLINE_MISSING   — no deadline provided for a critical matter
  URG_DEADLINE_TOO_FAR   — deadline is > 15 working days from today
  URG_ADVERSE_MISSING    — factual background lacks adverse-action language

A fourth rule is implemented but not tested per spec:
  URG_DEADLINE_INVALID   — deadline is not a parseable date (handled via type hints)
"""
from __future__ import annotations

import os
import re
from datetime import date
from typing import Any

import asyncpg

from mcp_tools._lib.server import build_tool_app
from mcp_tools.check_urgency_rules.calendar import calendar_check_working_days

app, roi, require_actor = build_tool_app("check_urgency_rules")

_db_pool: asyncpg.Pool | None = None

URGENT_WORKDAYS_THRESHOLD = 15

_EMIT_DEFAULTS: dict[str, Any] = {
    "workflow": "rls_apex.mcp.check_urgency_rules",
    "tool": "rls_apex",
    "task_type": "validation",
    "dept": "DEV",
    "role_band": "professional",
}

# Patterns that indicate adverse action language in factual background
_ADVERSE_PATTERN = re.compile(
    r"\b(?:adverse\s+action|revocation|suspension|termination|cancellation|"
    r"denial|forfeiture|enforcement|eviction|foreclosure|levy|seizure|"
    r"hearing|citation|violation)\b",
    re.IGNORECASE,
)


async def _get_db_pool() -> asyncpg.Pool:
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            host=os.environ["DB_HOST"],
            port=int(os.environ["DB_PORT"]),
            database=os.environ["DB_NAME"],
            min_size=1,
            max_size=4,
        )
    return _db_pool


@app.tool()
async def check_urgency_rules(
    rls_payload: dict,
    urgency: str | None = None,
    deadline: date | None = None,
    today: date | None = None,
) -> dict:
    """Validate urgency-critical packets against L2 deadline and adverse-action rules.

    Returns:
        applicable: True when urgency is 'critical'; False otherwise.
        blocking: list of blocking rule dicts with keys: code, field, message.
        warnings: always empty (reserved for future use).
    """
    actor = require_actor()
    today = today or date.today()
    blocking: list[dict[str, Any]] = []

    # Not a critical matter — rules do not apply.
    if urgency != "critical":
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
                        "urgency": urgency,
                        "applicable": False,
                        "blocking_count": 0,
                    },
                },
            )
        except Exception:
            pass
        return {"applicable": False, "blocking": [], "warnings": []}

    # --- Rule: URG_DEADLINE_MISSING ---
    if deadline is None:
        blocking.append(
            {
                "code": "URG_DEADLINE_MISSING",
                "field": "deadline",
                "message": (
                    "A deadline is required for urgency=critical matters. "
                    "Provide the date by which action must be taken."
                ),
            }
        )

    # --- Rule: URG_DEADLINE_TOO_FAR (only when deadline is present) ---
    if deadline is not None:
        try:
            pool = await _get_db_pool()
            working_days = await calendar_check_working_days(pool, start=today, end=deadline)
            if working_days > URGENT_WORKDAYS_THRESHOLD:
                blocking.append(
                    {
                        "code": "URG_DEADLINE_TOO_FAR",
                        "field": "deadline",
                        "message": (
                            f"Deadline is {working_days} working days away. "
                            f"Critical matters must be within {URGENT_WORKDAYS_THRESHOLD} "
                            "working days to qualify for urgency designation."
                        ),
                    }
                )
        except Exception:
            # URG_DEADLINE_INVALID — DB unavailable or parse error; record it
            blocking.append(
                {
                    "code": "URG_DEADLINE_INVALID",
                    "field": "deadline",
                    "message": (
                        "Unable to compute working days for the provided deadline. "
                        "Verify the deadline is a valid date and the calendar service is available."
                    ),
                }
            )

    # --- Rule: URG_ADVERSE_MISSING ---
    factual = rls_payload.get("factualBackground", "") or ""
    if not _ADVERSE_PATTERN.search(factual):
        blocking.append(
            {
                "code": "URG_ADVERSE_MISSING",
                "field": "factualBackground",
                "message": (
                    "Critical urgency requires the factual background to describe "
                    "the adverse action or enforcement event driving the deadline."
                ),
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
                    "urgency": urgency,
                    "applicable": True,
                    "blocking_count": len(blocking),
                },
            },
        )
    except Exception:
        pass

    return {"applicable": True, "blocking": blocking, "warnings": []}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=30106, log_level="info")

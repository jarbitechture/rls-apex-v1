"""
RLS Apex v1 — FastAPI gateway skeleton.

This is the bones, not the body. Each section is a TODO with the contract
documented inline. Filling these in is week-1 work; reviewing the shape is
day-1 work.

Single front door for the React app at rls.mymanatee.org. Responsibilities:

  • Auth         — Entra ID OIDC via MSAL (D-005)
  • Routing      — model selection (Qwen 7B / 32B / OpenAI fallback)
  • DSPy         — uncompiled chains for v0.1.0 (D-009)
  • MCP dispatch — RS256 JWT s2s, per-tool aud, 60s TTL (D-008)
  • Lineage      — every external call stamped (Rule #19)
  • ROI sidecar  — per user-facing action (Rule #18)
  • Phoenix      — OTel traces on every LLM call

Ring 4 of the architecture. Read ARCHITECTURE.md before editing.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

# DEV_AUTH_BYPASS=1 turns on the local click-through:
# - current_user returns a synthetic dev user instead of validating Entra ID
# - /api/query returns a canned mock SSE stream
# - apps/web/static is mounted at /
# Never enable on bcc-ap-llm01 in production.
DEV_MODE = os.environ.get("DEV_AUTH_BYPASS") == "1"

# ─── Lifespan ─────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Boot order: Key Vault → JWT keypair → MCP clients → Phoenix → DSPy.

    On shutdown: drain in-flight DSPy calls, flush ROI sidecar buffer,
    close MCP HTTP clients, sync lineage chain to disk.
    """
    # TODO: load secrets from Azure Key Vault (kv-rls-apex)
    # TODO: load JWT signing keypair from Key Vault, expose to MCP dispatcher
    # TODO: instantiate MCP clients (one per tool, with circuit breakers)
    # TODO: configure Phoenix OTel exporter → bcc-db-llm01:6006
    # TODO: configure DSPy with SGLang base_url + model name
    yield
    # TODO: graceful shutdown


app = FastAPI(
    title="RLS Apex Gateway",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/internal/docs",  # gated by OIDC + admin role in production
)

# ─── Auth (Entra ID OIDC) ─────────────────────────────────────────


async def current_user(request: Request) -> dict:
    """Validate the Entra ID OIDC token, return a typed user.

    Verifies via MSAL against OIDC_AUTHORITY. Extracts:
      • upn
      • display_name
      • groups (mapped to roles per domain.yaml roles[].ad_group)

    Raises 401 if missing, 403 if no role mapping found.

    Group overage: Entra sends an _claim_names hint when a user has > 200
    groups. Implementation must call Microsoft Graph `users/{id}/getMemberObjects`
    in that case — handled below.
    """
    if DEV_MODE:
        return {
            "upn": "dev@local",
            "display_name": "Dev User",
            "role": "general-counsel",
        }
    # TODO: extract Authorization: Bearer <token>
    # TODO: validate against OIDC_AUTHORITY (jwks cached, 5m TTL)
    # TODO: map groups → role per domain.yaml
    # TODO: handle _claim_names overage by calling Graph
    raise HTTPException(status_code=501, detail="oidc not yet wired")


# ─── Routes — health, query, skills, matters ──────────────────────


@app.get("/healthz", tags=["ops"])
async def healthz() -> dict:
    """Liveness. Kept dependency-free so it works even if KV is down."""
    return {"ok": True, "version": app.version}


@app.get("/readyz", tags=["ops"])
async def readyz() -> dict:
    """Readiness. Verifies Postgres, MinIO, SGLang, all 6 MCP tools."""
    # TODO: parallel pings to each backend, surface first failure
    return {"ok": False, "detail": "not yet wired"}


@app.post("/api/query", tags=["agent"])
async def query(request: Request, user: dict = Depends(current_user)) -> StreamingResponse:
    """Run the PrecedentRetriever chain over the user's question.

    Streams Server-Sent Events:
      • event: token       — incremental decode tokens
      • event: citation    — Citation entity rendered inline (D-014)
      • event: lineage     — lineage IDs as they're stamped
      • event: done        — final state with token counts for ROI

    Guardrails enforced before stream completes:
      1. No legal advice classifier on final output
      2. ≥ 1 citation present
      3. Lineage stamp present
    """
    if DEV_MODE:
        body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        question = (body.get("q") or "").strip() or "general procurement question"
        return StreamingResponse(_mock_query_stream(question), media_type="text/event-stream")
    # TODO: parse {q, matter_id?, k?}
    # TODO: classification check — if matter_id is privileged, additional ACL
    # TODO: call DSPy chain (uncompiled v0.1.0)
    # TODO: stream tokens as SSE
    # TODO: emit ROIEvent on stream close
    raise HTTPException(status_code=501, detail="query not yet wired")


# ─── Mock query stream (DEV_MODE only) ────────────────────────────


# Each mock matches an intent pattern. The pattern is a single regex run
# against the lower-cased question. First match wins; otherwise _DEFAULT_MOCK.
# Citations and answers stay close to real RLS-corpus shape so Drew can
# eyeball the citation rendering without us pretending the model is real.

_MOCKS: list[tuple[str, dict]] = [
    (
        r"sole.?source|125\.65|no.?bid|single.source",
        {
            "intent": "sole_source_findings",
            "answer": (
                "Based on three precedents in the County Attorney corpus, the proposed "
                "sole-source procurement is workable but carries one hard cure condition: "
                "Fla. Stat. §125.65(2) requires written findings on file BEFORE contract "
                "execution. RLS-25-0114 was rejected because findings were drafted "
                "concurrently with the contract; RLS-24-0431 was accepted on the same fact "
                "pattern after the findings memo was redated. Recommend revising the draft "
                "to attach the findings memo with a date at least one business day before "
                "the proposed execution date."
            ),
            "citations": [
                {"id": "RLS-25-0114", "source_kind": "opinion", "pinpoint": "p. 4 ¶ 3",
                 "excerpt": "Sole-source findings drafted after execution do not satisfy §125.65(2). Rejected without prejudice; cure path: re-submit with dated findings memo predating execution."},
                {"id": "RLS-24-0431", "source_kind": "opinion", "pinpoint": "p. 2 ¶ 2",
                 "excerpt": "Where written findings predate contract execution and are filed contemporaneously, the §125.65(2) waiver is satisfied even where the procurement is high-value."},
                {"id": "Fla. Stat. §125.65", "source_kind": "statute", "pinpoint": "(2)",
                 "excerpt": "The board may waive competitive bidding upon written findings that the public interest would be best served by a sole-source procurement."},
            ],
        },
    ),
    (
        r"evergreen|renewal|125\.66|36.month|60.month|auto.?renew",
        {
            "intent": "term_cap_evergreen",
            "answer": (
                "The 36-month term cap in Fla. Stat. §125.66(3)(c) is hard. Auto-renewal "
                "language extending the term beyond 36 months without annual board "
                "reauthorization is unenforceable against the County. RLS-24-0289 narrowed "
                "an attempted 60-month evergreen to 36; RLS-23-0512 voided a 5-year IT "
                "services renewal entirely. If the business goal is continuity, the "
                "vendor-side workaround is a 36-month base with explicit board action "
                "for each renewal — not an evergreen clause."
            ),
            "citations": [
                {"id": "RLS-24-0289", "source_kind": "opinion", "pinpoint": "p. 2 ¶ 1",
                 "excerpt": "An evergreen renewal extending an IT services contract beyond 36 months is not enforceable against the County under §125.66(3)(c) absent annual board reauthorization."},
                {"id": "RLS-23-0512", "source_kind": "opinion", "pinpoint": "p. 5 ¶ 4",
                 "excerpt": "A five-year renewal clause in a vendor contract is void to the extent it exceeds the §125.66(3)(c) term cap. Severance preserves the first 36 months only."},
                {"id": "Fla. Stat. §125.66", "source_kind": "statute", "pinpoint": "(3)(c)",
                 "excerpt": "No contract for personal property or services shall extend for a period in excess of 36 months without specific authorization of the board."},
            ],
        },
    ),
    (
        r"permit|zoning|land.use|variance|setback",
        {
            "intent": "permit_or_zoning",
            "answer": (
                "Permit and zoning RLS submissions are governed by the Manatee County "
                "Land Development Code (LDC) cross-referenced with Fla. Stat. ch. 163. "
                "The most common rejection pattern (RLS-25-0067) is a draft that asserts "
                "vested rights without attaching the dated approval predating the LDC "
                "amendment. Recommend including: (a) original approval with date, (b) "
                "LDC section reference at time of approval, (c) evidence of continuous "
                "use. The PrecedentRetriever surfaces matching prior approvals."
            ),
            "citations": [
                {"id": "RLS-25-0067", "source_kind": "opinion", "pinpoint": "p. 3 ¶ 2",
                 "excerpt": "Vested-rights claim under prior LDC §6.4.A.5 must be supported by dated approval predating the 2024 amendment. Bare assertion insufficient."},
                {"id": "LDC §6.4", "source_kind": "regulation", "pinpoint": "A.5",
                 "excerpt": "A vested right is established by good-faith reliance on a county action that authorized the use, and substantial change of position in reliance."},
                {"id": "Fla. Stat. §163.3167", "source_kind": "statute", "pinpoint": "(8)",
                 "excerpt": "Nothing in this section shall limit or modify the rights of any person to complete any development that has been authorized as a development of regional impact…"},
            ],
        },
    ),
    (
        r"public.records|chapter 119|sunshine|exempt",
        {
            "intent": "public_records",
            "answer": (
                "Chapter 119 exemptions are narrow and strictly construed. The draft as "
                "written claims §119.071(2)(d) (active criminal investigation) but the "
                "underlying matter is civil; that exemption does not apply. RLS-24-0904 "
                "and RLS-23-0188 both rejected similar misclassifications. The closest "
                "applicable exemption for this fact pattern is §119.0712(2) "
                "(motor-vehicle records) IF the records contain DAVID-derived data — "
                "verify before relying."
            ),
            "citations": [
                {"id": "RLS-24-0904", "source_kind": "opinion", "pinpoint": "p. 1 ¶ 4",
                 "excerpt": "The §119.071(2)(d) active-investigation exemption is criminal-only and does not extend to parallel civil matters arising from the same underlying facts."},
                {"id": "RLS-23-0188", "source_kind": "opinion", "pinpoint": "p. 6 ¶ 1",
                 "excerpt": "Mislabeling civil-litigation records under a criminal-investigation exemption is a recurring pattern. Strict construction applies; reclassify or release."},
                {"id": "Fla. Stat. §119.0712", "source_kind": "statute", "pinpoint": "(2)",
                 "excerpt": "Personal information contained in motor vehicle records that the department obtains pursuant to chapter 322 is confidential and exempt…"},
            ],
        },
    ),
]

_DEFAULT_MOCK = {
    "intent": "general_procurement",
    "answer": (
        "Based on the three closest precedents in the County Attorney corpus, the "
        "proposed scope is workable in form but two cure conditions apply. First, "
        "the sole-source justification under Fla. Stat. §125.65(2) requires written "
        "findings on file before contract execution — see RLS-25-0114. Second, the "
        "term cap of 36 months in §125.66(3)(c) applies regardless of renewal "
        "language; RLS-24-0289 narrowed an attempted 60-month evergreen to 36."
    ),
    "citations": [
        {"id": "RLS-25-0114", "source_kind": "opinion", "pinpoint": "p. 4 ¶ 3",
         "excerpt": "Sole-source findings drafted after contract execution do not satisfy §125.65(2). Rejected without prejudice."},
        {"id": "RLS-24-0289", "source_kind": "opinion", "pinpoint": "p. 2 ¶ 1",
         "excerpt": "An evergreen renewal extending an IT services contract beyond 36 months is not enforceable against the County under §125.66(3)(c)."},
        {"id": "Fla. Stat. §125.66", "source_kind": "statute", "pinpoint": "(3)(c)",
         "excerpt": "No contract for personal property or services shall extend for a period in excess of 36 months without specific authorization of the board."},
    ],
}


def _pick_mock(question: str) -> dict:
    q = question.lower()
    for pattern, mock in _MOCKS:
        if re.search(pattern, q):
            return mock
    return _DEFAULT_MOCK


# Step trace mirrors the real DSPy chain in agents/precedent-retriever/chain.py.
# Each tuple: (step name, simulated work in ms, optional output summary key).
# Real backends replace this in week 2; the *shape* doesn't change.
_CHAIN_STEPS: list[tuple[str, int, str | None]] = [
    ("classify",          110, "intent"),
    ("retrieve.hybrid",   285, "vector_hits"),
    ("policy_graph.cited_by", 165, "graph_hits"),
    ("rank",               75, None),
    ("compose",             0, None),  # streams tokens; "done" emitted after token loop
]


async def _mock_query_stream(question: str) -> AsyncIterator[bytes]:
    """Canned SSE for the v0.1.0 click-through. Emits step traces matching the
    real PrecedentRetriever chain shape, then streams the answer + citations.
    Replaced by the real chain in week 2; the SSE contract stays."""

    def sse(event: str, data: dict) -> bytes:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()

    mock = _pick_mock(question)
    t0 = time.perf_counter()

    yield sse("step", {"name": "_chain", "status": "start", "t_ms": 0})

    for name, base_ms, output_key in _CHAIN_STEPS:
        yield sse("step", {
            "name": name,
            "status": "start",
            "t_ms": int((time.perf_counter() - t0) * 1000),
        })
        # jitter so the demo feels alive across re-runs
        await asyncio.sleep((base_ms + random.randint(-25, 40)) / 1000)
        if name == "compose":
            # tokens stream from inside compose
            for word in mock["answer"].split(" "):
                yield sse("token", {"text": word + " "})
                await asyncio.sleep(0.022)
        out_summary = {
            "intent": mock["intent"],
            "vector_hits": 12,
            "graph_hits": 4,
        }.get(output_key)
        yield sse("step", {
            "name": name,
            "status": "done",
            "t_ms": int((time.perf_counter() - t0) * 1000),
            **({"output": out_summary} if out_summary is not None else {}),
        })

    for c in mock["citations"]:
        yield sse("citation", c)
        await asyncio.sleep(0.08)

    yield sse("step", {"name": "_chain", "status": "done",
                        "t_ms": int((time.perf_counter() - t0) * 1000)})
    yield sse("done", {
        "prompt_tokens": 64 + random.randint(-8, 8),
        "output_tokens": 110 + random.randint(-15, 20),
        "lineage_id": f"ln-mock-{random.randint(1000, 9999)}",
        "intent": mock["intent"],
    })


# ─── Feedback (mock + real share this contract) ───────────────────


_FEEDBACK_PATH = Path(os.environ.get("FEEDBACK_LOG", "/tmp/rls-apex-feedback.jsonl"))


@app.post("/api/feedback", tags=["agent"])
async def post_feedback(request: Request, user: dict = Depends(current_user)) -> dict:
    """Accept/Reject from the click-through. Append-only JSONL row.
    In production this is a Postgres write + ROIEvent emit; in mock mode
    it's a single file the page can read back."""
    body = await request.json()
    decision = body.get("decision")
    if decision not in ("accept", "reject"):
        raise HTTPException(status_code=400, detail="decision must be 'accept' or 'reject'")
    row = {
        "ts": time.time(),
        "user": user.get("upn"),
        "decision": decision,
        "lineage_id": body.get("lineage_id"),
        "intent": body.get("intent"),
        "question": (body.get("question") or "")[:280],
    }
    _FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _FEEDBACK_PATH.open("a") as f:
        f.write(json.dumps(row) + "\n")
    return {"ok": True, "decision": decision}


@app.get("/api/feedback/recent", tags=["agent"])
async def recent_feedback(user: dict = Depends(current_user)) -> dict:
    """Last 10 decisions, newest first. Drives the right-rail history list."""
    if not _FEEDBACK_PATH.exists():
        return {"items": []}
    lines = _FEEDBACK_PATH.read_text().splitlines()[-10:][::-1]
    return {"items": [json.loads(l) for l in lines if l.strip()]}


@app.get("/api/health/sidecar", tags=["ops"])
async def health_sidecar() -> dict:
    """Rule #19 contract — circuit breaker status. Mock: always closed."""
    return {
        "breaker": "closed",
        "consecutive_failures": 0,
        "last_open_ts": None,
        "sink": str(_FEEDBACK_PATH),
        "mock": DEV_MODE,
    }


@app.get("/api/skills/templates", tags=["skills"])
async def list_templates(user: dict = Depends(current_user)) -> list[dict]:
    """List skill templates from skills/templates/. Frontmatter parsed.
    Filtered by user role (governance.owners)."""
    raise HTTPException(status_code=501, detail="skills not yet wired")


@app.put("/api/skills/templates/{slug}", tags=["skills"])
async def upsert_template(slug: str, user: dict = Depends(current_user)) -> dict:
    """Edit a Template skill. Triggers GitHub App PR (D-011).

    Flow:
      1. Validate user role against governance.owners
      2. Write file to a feature branch via GitHub App service account
      3. Open PR, attribute Co-Authored-By: <user.upn>
      4. Emit LineageEvent + ROIEvent
      5. Return PR URL — caller's UI can deep-link to review
    """
    raise HTTPException(status_code=501, detail="skills edit not yet wired")


# ─── Matter drafts — RESERVED in v0.1.0 ───────────────────────────


@app.api_route("/api/matters/{matter_id}/drafts/{path:path}", methods=["GET", "PUT", "POST", "DELETE"], tags=["skills"])
async def matter_drafts_reserved(matter_id: str, path: str) -> dict:
    """Reserved namespace for v1.0+ matter-draft surface (D-011).

    Returns 501 with Retry-After hint pointing to weeks 5–6.
    DO NOT remove this route — keeping the URL space reserved prevents
    name collision with the Reviser-era schema.
    """
    raise HTTPException(
        status_code=501,
        detail="matter drafts ship in v1.0 alongside Reviser (weeks 5-6)",
        headers={"Retry-After": "1209600"},  # 14 days
    )


# ─── ROI sidecar (D-001) ──────────────────────────────────────────


def emit_roi(event: dict) -> None:
    """Append-only JSONL on bcc-db-llm01. One event per user-facing action.

    Schema bound to apps/gateway/sidecar/manatee_ai_roi.schema.json.
    Power BI Gateway pulls from the file on a 5-minute cadence.

    Only metadata. NEVER prompt bodies, output bodies, or document content.
    """
    # TODO: validate against schema
    # TODO: append to /var/log/rls-apex-v1/roi/YYYY-MM-DD.jsonl


# ─── MCP dispatcher (D-008) ───────────────────────────────────────


async def call_tool(tool: str, method: str, args: dict) -> dict:
    """Sign an RS256 JWT (aud=tool.<tool>, 60s TTL), POST to loopback,
    enforce gateway-side circuit breaker per tool.

    Tool-side circuit breakers are independent — each tool wraps its own
    backend calls. Two layers, identical defaults initially per D-008.
    """
    # TODO: sign JWT with gateway keypair (loaded at boot)
    # TODO: HTTP POST to 127.0.0.1:<port>/<method>
    # TODO: gateway-side breaker (failure threshold, half-open behavior)
    # TODO: stamp LineageEvent before return
    raise NotImplementedError


# ─── Static mount (DEV_MODE only) ─────────────────────────────────
# Mounted last so all /api/* routes register first. Serves the click-through
# page from apps/web/static/index.html. In production the React build is
# served by IIS/nginx, not by FastAPI.

if DEV_MODE:
    _web_root = Path(__file__).resolve().parents[2] / "apps" / "web" / "static"
    if _web_root.exists():
        app.mount("/", StaticFiles(directory=str(_web_root), html=True), name="web")


# ─── Local dev ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)

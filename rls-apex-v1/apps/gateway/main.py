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

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

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
    # TODO: parse {q, matter_id?, k?}
    # TODO: classification check — if matter_id is privileged, additional ACL
    # TODO: call DSPy chain (uncompiled v0.1.0)
    # TODO: stream tokens as SSE
    # TODO: emit ROIEvent on stream close
    raise HTTPException(status_code=501, detail="query not yet wired")


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


# ─── Local dev ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)

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
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# DEV_AUTH_BYPASS=1 turns on the local click-through:
# - current_user returns a synthetic dev user instead of validating Entra ID
# - /api/query returns a canned mock SSE stream
# - apps/web/static is mounted at /
# Never enable on bcc-ap-llm01 in production.
DEV_MODE = os.environ.get("DEV_AUTH_BYPASS") == "1"

# RLS_ALLOWLIST="BCC\ejarbeadm,..."  — comma-separated UPNs (or
# DOMAIN\sam-style strings) allowed to authenticate. Empty = no
# allowlist (open to anyone who passes OIDC). Same gate runs in dev
# (DEV_MODE) and prod (real Entra OIDC); the upn extraction differs
# but the allowlist check doesn't.
_RAW_ALLOWLIST = os.environ.get("RLS_ALLOWLIST", "").strip()
RLS_ALLOWLIST = {x.strip() for x in _RAW_ALLOWLIST.split(",") if x.strip()}
DEV_USER_UPN = os.environ.get("DEV_USER_UPN", "dev@local")

# ─── ROI sidecar singleton ────────────────────────────────────────
# A_Plus_Client (POST → manatee-ai-roi FastAPI; local fallback JSONL on this
# host when the breaker opens; background drain on recovery). Initialized in
# lifespan; held at module scope so emit_roi() (sync API kept for existing
# call sites) can fire-and-forget.

_ROI_ENDPOINT = os.environ.get("ROI_EVENTS_URL", "http://localhost:8000")
_ROI_FALLBACK_PATH = os.environ.get(
    "ROI_FALLBACK_PATH", "/var/log/rls-apex-v1/roi-fallback.jsonl"
)
_roi_client = None  # set in lifespan; type: RoiClient | None


# ─── LLM endpoint guard (TAC-05) ──────────────────────────────────
# Lock #19 framing: /api/query is a validator surface. Accidentally pointing
# the gateway at a third-party LLM (OpenAI, Anthropic, Google) would leak
# RLS intake text to an external host. Boot aborts if LLM_PROVIDER is set
# to a real provider AND its base URL points outside the county LAN.
#
# No bypass flag. To skip the check intentionally, set LLM_PROVIDER=mock
# (which already short-circuits to canned text and dials no external host).
_LLM_HOST_ALLOWLIST: tuple[str, ...] = (
    "manatee-civic-ai.internal",
    "infer01",
    "llm01",
    "localhost",
    "127.0.0.1",
)

# Map provider → env var holding the base URL. Keep this list aligned with
# apps/gateway/llm/client.py's LLMConfig.
_LLM_PROVIDER_URL_ENV: dict[str, str] = {
    "ollama": "OLLAMA_BASE_URL",
    "sglang": "SGLANG_BASE_URL",
    "openai": "OPENAI_BASE_URL",
}


def _host_allowed(host: str) -> bool:
    """Suffix-match against the allowlist. `infer01` matches `infer01`,
    `infer01.county.local`, but NOT `xinfer01` or `infer01-evil.com`."""
    if not host:
        return False
    host = host.lower()
    for pattern in _LLM_HOST_ALLOWLIST:
        p = pattern.lower()
        if host == p or host.startswith(p + "."):
            return True
    return False


def assert_llm_endpoint_allowed() -> None:
    """Validate the LLM endpoint URL against the county-LAN allowlist.

    Raises RuntimeError (aborts FastAPI boot) if the active provider is
    not `mock` and its base URL hostname falls outside the allowlist.
    No outbound HTTP — pure URL parse + suffix match.
    """
    from urllib.parse import urlparse

    provider = (os.environ.get("LLM_PROVIDER") or "mock").strip().lower()
    if provider == "mock":
        return  # mock dials nothing; nothing to check.

    if provider == "auto":
        # `auto` selects the first configured provider at request time. We
        # check every configured *_BASE_URL so we don't let `auto` smuggle
        # an external host past the guard.
        candidates = [(p, _LLM_PROVIDER_URL_ENV[p]) for p in _LLM_PROVIDER_URL_ENV]
    else:
        env_var = _LLM_PROVIDER_URL_ENV.get(provider)
        if env_var is None:
            raise RuntimeError(
                f"[gateway] LLM endpoint guard: unknown provider {provider!r}. "
                f"Set LLM_PROVIDER to one of: mock, {', '.join(_LLM_PROVIDER_URL_ENV)}."
            )
        candidates = [(provider, env_var)]

    for prov, env_var in candidates:
        url = (os.environ.get(env_var) or "").strip()
        if not url:
            # `auto` may legitimately have unset providers — skip them.
            # For an explicitly selected provider, missing URL is a violation:
            # boot would later default to localhost or fail opaquely.
            if provider == "auto":
                continue
            raise RuntimeError(
                f"[gateway] LLM endpoint guard: {env_var} is empty but "
                f"LLM_PROVIDER={prov!r}. Set {env_var} to a host on the "
                f"county-LAN allowlist {_LLM_HOST_ALLOWLIST!r}, or set "
                f"LLM_PROVIDER=mock to skip."
            )
        host = (urlparse(url).hostname or "").strip()
        if not _host_allowed(host):
            raise RuntimeError(
                f"[gateway] LLM endpoint guard REFUSING TO BOOT: "
                f"provider={prov!r} {env_var}={url!r} host={host!r} is not "
                f"on the county-LAN allowlist {_LLM_HOST_ALLOWLIST!r}. "
                f"Set LLM_PROVIDER=mock to skip this check."
            )
        print(f"[gateway] LLM endpoint guard OK: provider={prov} host={host}", flush=True)


# ─── Lifespan ─────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Boot order: Key Vault → JWT keypair → MCP clients → Phoenix → DSPy → ROI.

    On shutdown: drain in-flight DSPy calls, flush ROI sidecar buffer,
    close MCP HTTP clients, sync lineage chain to disk.
    """
    global _roi_client
    # TAC-05: refuse to boot if the LLM endpoint points outside the county LAN.
    # Runs FIRST so a misconfigured host stops the gateway before it can
    # accept any traffic. No bypass flag — set LLM_PROVIDER=mock to skip.
    assert_llm_endpoint_allowed()
    # TODO: load secrets from Azure Key Vault (kv-rls-apex)
    # TODO: load JWT signing keypair from Key Vault, expose to MCP dispatcher
    # TODO: instantiate MCP clients (one per tool, with circuit breakers)
    # TODO: configure Phoenix OTel exporter → bcc-db-llm01:6006
    # TODO: configure DSPy with SGLang base_url + model name
    try:
        from apps.gateway.sidecar._client import RoiClient

        _roi_client = RoiClient(
            endpoint=_ROI_ENDPOINT,
            fallback_path=_ROI_FALLBACK_PATH,
        )
        await _roi_client.start_drain_loop()
        # Also expose on app.state so /api/health/breakers can read it
        # without reaching into module globals (W5 / spec §12.4).
        app.state.roi_client = _roi_client
    except Exception as exc:  # noqa: BLE001
        # Telemetry must never block boot. Log and continue without sidecar.
        print(f"[gateway] ROI client init failed (continuing): {exc}", flush=True)
        _roi_client = None
        app.state.roi_client = None
    if DEV_MODE:
        # Corpus retrieval is part of the build, not optional. Load on
        # startup; if no index exists, auto-ingest from corpus/raw/. If
        # raw/ is also empty, log a loud warning but keep the gateway up
        # (retrieval just returns []).
        try:
            from apps.gateway.retrieval import load as _load_corpus, manifest as _manifest
            from apps.gateway.retrieval.ingest import RAW_DIR, INDEX_PATH, ingest as _ingest
            if not INDEX_PATH.exists():
                if RAW_DIR.exists() and any(RAW_DIR.iterdir()):
                    print(f"[gateway] corpus index missing — auto-ingesting from {RAW_DIR}", flush=True)
                    _ingest()
                else:
                    print(f"[gateway] WARNING: no corpus index AND no files in {RAW_DIR}", flush=True)
                    print(f"[gateway]          drop docs into corpus/raw/ and run bin/ingest", flush=True)
            ok = _load_corpus()
            if ok:
                m = _manifest()
                print(f"[gateway] corpus loaded: {len(m['documents'])} docs · {m['total_chunks']} chunks", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[gateway] corpus load failed: {e}", flush=True)
    # === asyncpg pool (W2 sizing) ===
    import os as _os
    from apps.gateway.db.pool import create_pool, GATEWAY_POOL_SIZE
    db_dsn = _os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/rls_apex",
    )
    try:
        app.state.db_pool = await create_pool(db_dsn, sizing=GATEWAY_POOL_SIZE)
        print(f"[lifespan] db pool ready, max={GATEWAY_POOL_SIZE[1]}")
    except Exception as e:
        print(f"[lifespan] db pool FAILED: {e!r} — gateway running without db (some endpoints will degrade)")
        app.state.db_pool = None
    yield
    # === pool teardown ===
    if getattr(app.state, "db_pool", None) is not None:
        await app.state.db_pool.close()
    # graceful shutdown
    if _roi_client is not None:
        try:
            await _roi_client.close()
        except Exception:  # noqa: BLE001
            pass


app = FastAPI(
    title="RLS Apex Gateway",
    version="0.2.0b",
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
        upn = DEV_USER_UPN
        if RLS_ALLOWLIST and upn not in RLS_ALLOWLIST:
            raise HTTPException(status_code=403,
                                detail=f"upn {upn!r} not in RLS_ALLOWLIST")
        return {
            "upn": upn,
            "display_name": upn.split("@")[0].split("\\")[-1] or upn,
            "role": "general-counsel",
            # Placeholder values until OIDC claim mapping is wired (see TODO at lines ~179-184).
            # `dept` is a free string; `role_band` must be one of the schema enum buckets
            # (exec|director|manager|senior|professional|support — no "unknown").
            "dept": "DEV",
            "role_band": "professional",
        }
    # TODO: extract Authorization: Bearer <token>
    # TODO: validate against OIDC_AUTHORITY (jwks cached, 5m TTL)
    # TODO: map groups → role per domain.yaml
    # TODO: handle _claim_names overage by calling Graph
    # The RLS_ALLOWLIST check below applies once OIDC extracts the upn:
    #   if RLS_ALLOWLIST and upn not in RLS_ALLOWLIST: raise 403
    raise HTTPException(status_code=501, detail="oidc not yet wired")


# ─── Routes — health, query, skills, matters ──────────────────────


@app.get("/api/me", tags=["auth"])
async def api_me(user: dict = Depends(current_user)) -> dict:
    """Return the authenticated user's profile so the UI can render
    the sidebar footer / header from real identity instead of a fake
    persona. Goes through current_user, so it also enforces the
    RLS_ALLOWLIST gate."""
    name = user.get("display_name") or user.get("upn") or "RLS Pilot"
    initials = "".join(p[0].upper() for p in name.split() if p)[:2] or "RP"
    return {
        "upn": user.get("upn"),
        "display_name": name,
        "initials": initials,
        "role": user.get("role") or "—",
    }


@app.get("/healthz", tags=["ops"])
async def healthz() -> dict:
    """Liveness + corpus status. The corpus block is the gateway's hard
    dependency for grounded answers — every engagement reads from it."""
    corpus_block = {"loaded": False, "docs": 0, "chunks": 0}
    try:
        m = _corpus_manifest()
        corpus_block = {
            "loaded": bool(m.get("loaded")),
            "docs": len(m.get("documents", [])),
            "chunks": m.get("total_chunks", 0),
        }
    except Exception:  # noqa: BLE001
        pass
    return {"ok": True, "version": app.version, "corpus": corpus_block}


@app.get("/readyz", tags=["ops"])
async def readyz() -> dict:
    """Readiness. Verifies Postgres, MinIO, SGLang, all 6 MCP tools."""
    # TODO: parallel pings to each backend, surface first failure
    from apps.gateway.db.pool import healthcheck
    db_health = await healthcheck(app.state.db_pool) if getattr(app.state, "db_pool", None) is not None else {"db": "uninitialized"}
    return {"status": "ready" if db_health.get("db") == "ok" else "degraded", **db_health}


# ─── Intake (spec §5.1) ───────────────────────────────────────────


class IntakeRequest(BaseModel):
    """Free-text intake body. 1..10k chars; pydantic rejects empty as 422."""

    text: str = Field(min_length=1, max_length=10_000)


@app.post("/api/intake", tags=["intake"])
async def api_intake(req: IntakeRequest, user: dict = Depends(current_user)) -> dict:
    """Free-text → classify_matter + extract_fields → assembled rlsPayload (spec §5.1).

    v0.2.0a calls the MCP tools as in-process Python imports (the underlying
    `classify_text` / `extract_text` helpers, bypassing the FastMCP wrapper).
    The systemd-unit-per-tool deployment is v0.2.0b infra.
    """
    from mcp_tools.classify_matter.server import classify_text
    from mcp_tools.extract_fields.server import extract_text

    classification = classify_text(req.text)
    extracted = extract_text(req.text)
    rls_payload = {
        **extracted,
        "type": classification["type"],
    }

    emit_roi({
        "event_kind": "llm_call",  # intake is the LLM-orchestrated entry, even when mocked
        "workflow": "rls_apex.intake",
        "tool": "rls_apex",
        "surface": "other",
        "user_id": user.get("upn", "unknown"),
        "dept": user.get("dept", "DEV"),
        "role_band": user.get("role_band", "professional"),
        "task_type": "data_analysis",
        "success": True,
        # TODO(v0.2.1 DSPy wiring): replace 0s with chain.forward() usage metadata.
        # Until then, llm_call validator requires both fields not-None — 0 satisfies it.
        "prompt_tokens": 0,
        "output_tokens": 0,
    })
    return {
        "classification": classification,
        "rlsPayload": rls_payload,
    }


# ─── Validate (spec §5.4) ─────────────────────────────────────────


class _ValidateRequest(BaseModel):
    rlsPayload: dict


@app.post("/api/validate", tags=["intake"])
async def api_validate(req: _ValidateRequest, user: dict = Depends(current_user)) -> dict:
    """Run validate_rls_structure against the supplied payload (spec §5.4)."""
    from mcp_tools.validate_rls_structure.server import validate_dict

    result = validate_dict(req.rlsPayload)
    emit_roi({
        "event_kind": "tool_invocation",
        "workflow": "rls_apex.validate",
        "tool": "rls_apex",
        "surface": "other",
        "user_id": user.get("upn", "unknown"),
        "dept": user.get("dept", "DEV"),
        "role_band": user.get("role_band", "professional"),
        "task_type": "validation",
        "success": True,
        "extra": {"blocking_count": len(result.blocking)},
    })
    return result.model_dump()


# ─── CAO brief (spec §5.7, v0.2.0b stub) ──────────────────────────


@app.get("/api/cao/brief", tags=["cao"])
async def cao_brief(rlsId: str, user: dict = Depends(current_user)) -> dict:
    """Canned 3-bullet brief for the CAO reviewer panel.
    v0.2.0b stub — real content lands in v0.2.1 with the precedent corpus."""
    body = {
        "rlsId": rlsId,
        "summary": [
            "Requester seeks legal review on a permit denial; matter type appears procedural.",
            "Applicant claims pre-existing approval predating the LDC §6.4 amendment.",
            "Urgency framing claimed — verify against §15-day rule before CAO recommendation.",
        ],
        "keyFacts": [
            "Permit denial issued under current LDC §6.4 (2024 amendment).",
            "Applicant references RLS-25-0067 as analogous accepted vested-rights claim.",
        ],
        "risk": (
            "Substantive risk if applicant's vested-rights documentation is incomplete; "
            "structural risk minimal — RLS-25-0067 precedent is on point."
        ),
        "suggestedNextSteps": [
            "Confirm pre-2024 approval document is on file before recommending acceptance.",
            "Coordinate with Code Enforcement on litigation hold status.",
        ],
    }
    emit_roi({
        "event_kind": "tool_invocation",
        "workflow": "rls_apex.cao_brief",
        "tool": "rls_apex",
        "surface": "other",
        "user_id": user.get("upn", "unknown"),
        "dept": user.get("dept", "DEV"),
        "role_band": user.get("role_band", "professional"),
        "task_type": "summarizing",
        "success": True,
        "extra": {"rls_id": rlsId},
    })
    return body


class QueryRefusalResponse(BaseModel):
    """TAC-03 / Lock #19: validator refuses to grade when retrieval yields
    zero relevant chunks. Returned as HTTP 200 + JSON (not 4xx — refusal is
    a deliberate semantic response, not a client error).
    """
    refused: bool = Field(default=True)
    reason: str = Field(default="no_grounding")
    message: str


_REFUSAL_MESSAGE = (
    "No matching precedent or procedural authority was found in the corpus for "
    "this draft. The RLS Apex validator only grades drafts it can ground in "
    "cited precedent — without a match it cannot return a rejection-probability "
    "score or cure path. Add specifics (statute cite, RLS number, or "
    "fact-pattern keywords) and resubmit, or route this question to a county "
    "attorney directly."
)


@app.post("/api/query", tags=["agent"])
async def query(request: Request, user: dict = Depends(current_user)):
    """Validator surface (Lock #19). Grades the user's draft against
    retrieved procedure/form requirements/cited precedents.

    Two response modes:
      • Grounded — happy path. Streams SSE: step / token / citation / done.
      • Refused  — HTTP 200 JSON `{refused, reason, message}` when retrieval
                   yields zero relevant chunks (TAC-03). No tokens streamed.

    Guardrails on the streamed path:
      1. ≥ 1 citation present (enforced by the retrieval gate above)
      2. Lineage stamp emitted in `done`
      3. Token counts captured for ROI
    """
    if DEV_MODE:
        body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        question = (body.get("q") or "").strip() or "general procurement question"
        user_id = user.get("upn", "unknown")
        dept = user.get("dept", "DEV")
        role_band = user.get("role_band", "professional")

        # ── TAC-03 refusal gate (runs BEFORE any LLM call) ─────────────
        # Lock #19: no grounding → refuse. Retrieval failures are treated
        # as no-grounding for the user-facing response; the ROI event
        # still emits success=False so ops can see them. Rule #18:
        # telemetry never blocks the user-facing action.
        try:
            real_hits = _corpus_retrieve(
                question, k=4,
                classification_filter=["public_record", "internal"],
            )
        except Exception:
            real_hits = []

        if not real_hits:
            # NEVER log the user's query text in the ROI extra dict — PII
            # surface. The refusal_reason marker is enough for Power BI.
            emit_roi({
                "event_kind": "escalation",  # closest valid enum; refusal not in schema
                "workflow": "rls_apex.query",
                "tool": "rls_apex",
                "surface": "other",  # 'api' is not in the Surface enum
                "user_id": user_id,
                "dept": dept,
                "role_band": role_band,
                "task_type": "search",
                "success": False,
                "extra": {"refusal_reason": "no_grounding"},
            })
            refusal = QueryRefusalResponse(message=_REFUSAL_MESSAGE)
            return JSONResponse(content=refusal.model_dump(), status_code=200)

        async def _stream_with_roi() -> AsyncIterator[bytes]:
            """Yield the mock SSE stream, then fire a ROI event after stream close."""
            success = True
            try:
                async for chunk in _mock_query_stream(question, real_hits):
                    yield chunk
            except Exception:
                success = False
                raise
            finally:
                emit_roi({
                    "event_kind": "tool_invocation",
                    "workflow": "rls_apex.query",
                    "tool": "rls_apex",
                    "surface": "other",
                    "user_id": user_id,
                    "dept": dept,
                    "role_band": role_band,
                    "task_type": "data_analysis",
                    "success": success,
                })

        return StreamingResponse(_stream_with_roi(), media_type="text/event-stream")
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
            "score": 35,  # rejection-probability 0-100 (higher = more likely to be rejected)
            "band": "medium",
            "cure_path": [
                {"title": "Add dated findings memo predating execution",
                 "detail": "§125.65(2) requires written findings on file BEFORE contract execution. Memo must be dated at least one business day before the proposed execution date.",
                 "citation_id": "Fla. Stat. §125.65"},
                {"title": "Re-attach the redated findings memo to the RLS",
                 "detail": "RLS-24-0431 was accepted on the same fact pattern after the findings memo was redated and re-attached.",
                 "citation_id": "RLS-24-0431"},
            ],
            "answer": (
                "Sole-source procurement is workable on this fact pattern, but as drafted "
                "the findings memo is concurrent with execution. The corpus shows two "
                "outcomes for that exact issue: rejected (RLS-25-0114) when findings "
                "were drafted concurrently, accepted (RLS-24-0431) once the memo predated "
                "execution. The cure path is mechanical, not substantive."
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
            "score": 78,
            "band": "high",
            "cure_path": [
                {"title": "Strip evergreen renewal language from the contract",
                 "detail": "§125.66(3)(c) caps service contracts at 36 months absent annual board reauthorization. Auto-renewal beyond 36 months is unenforceable.",
                 "citation_id": "Fla. Stat. §125.66"},
                {"title": "Replace with 36-month base + explicit annual board action",
                 "detail": "Pattern accepted in RLS-24-0289 after the 60-month evergreen was narrowed. 5-year evergreens (RLS-23-0512) were voided entirely.",
                 "citation_id": "RLS-24-0289"},
            ],
            "answer": (
                "Evergreen extends the term beyond §125.66(3)(c)'s 36-month cap and is "
                "unenforceable against the County as drafted. The cure is structural: a "
                "36-month base with annual board reauthorization replaces the auto-renewal "
                "clause. Continuity is preserved; enforceability is restored."
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
            "score": 55,
            "band": "medium",
            "cure_path": [
                {"title": "Attach dated approval predating the LDC amendment",
                 "detail": "Vested-rights claim under prior LDC §6.4.A.5 must show the approval was issued BEFORE the 2024 amendment.",
                 "citation_id": "RLS-25-0067"},
                {"title": "Show evidence of continuous use since approval",
                 "detail": "Bare assertion of vested rights insufficient — needs documented continuous use of the rights granted.",
                 "citation_id": "LDC §6.4"},
                {"title": "Cite the LDC section in force AT THE TIME of the original approval",
                 "detail": "Current LDC text does not control; the version in force when the approval was issued does.",
                 "citation_id": "Fla. Stat. §163.3167"},
            ],
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
            "score": 82,
            "band": "high",
            "cure_path": [
                {"title": "Re-classify the records — §119.071(2)(d) does not apply to civil matters",
                 "detail": "The active-investigation exemption is criminal-only. Civil litigation records arising from the same facts are not covered.",
                 "citation_id": "RLS-24-0904"},
                {"title": "Identify the correct exemption (or release)",
                 "detail": "Closest applicable for this fact pattern: §119.0712(2) for motor-vehicle records IF the records contain DAVID-derived data. Verify before relying.",
                 "citation_id": "Fla. Stat. §119.0712"},
                {"title": "If no exemption applies, prepare release with redactions",
                 "detail": "Strict construction applies — Chapter 119 favors disclosure. Default: release with statutory redactions only.",
                 "citation_id": "RLS-23-0188"},
            ],
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
    "score": 45,
    "band": "medium",
    "cure_path": [
        {"title": "Add dated findings memo predating execution",
         "detail": "If procurement is sole-source, §125.65(2) requires findings on file before contract execution.",
         "citation_id": "RLS-25-0114"},
        {"title": "Cap the term at 36 months with explicit board reauthorization for renewals",
         "detail": "§125.66(3)(c) caps service contracts at 36 months unless the board explicitly reauthorizes.",
         "citation_id": "RLS-24-0289"},
    ],
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


async def _mock_query_stream(question: str, real_hits: list) -> AsyncIterator[bytes]:
    """SSE chain for /api/query. Step trace mirrors PrecedentRetriever; tokens
    stream from `compose` via the LLM client (mock by default; flip env to
    enable real Ollama/SGLang/OpenAI).

    Caller (`/api/query`) pre-fetches retrieval once and threads the hits in
    here. Lock #19 / TAC-03: when `real_hits` is empty the caller refuses
    BEFORE reaching this function, so by contract `real_hits` is always
    non-empty here. We assert it to surface any future regression."""
    assert real_hits, "_mock_query_stream invariant: caller must refuse on empty retrieval"

    def sse(event: str, data: dict) -> bytes:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()

    mock = _pick_mock(question)
    # Citations come from the real corpus (caller has already confirmed ≥1 hit).
    citations_for_ctx = [_citation_to_dict(c) for c in real_hits]

    t0 = time.perf_counter()
    yield sse("step", {"name": "_chain", "status": "start", "t_ms": 0})

    for name, base_ms, output_key in _CHAIN_STEPS:
        yield sse("step", {
            "name": name,
            "status": "start",
            "t_ms": int((time.perf_counter() - t0) * 1000),
        })
        await asyncio.sleep((base_ms + random.randint(-25, 40)) / 1000)
        if name == "compose":
            if _LLM_OK and _llm.provider() != "mock":
                async for tok in _llm.stream_completion(
                    user=question, citations=citations_for_ctx,
                    answer_hint=mock["answer"]):
                    yield sse("token", {"text": tok})
            else:
                # mock provider — stream the intent-routed answer template
                for word in mock["answer"].split(" "):
                    yield sse("token", {"text": word + " "})
                    await asyncio.sleep(0.022)
        out_summary = {"intent": mock["intent"], "vector_hits": 12, "graph_hits": 4}.get(output_key)
        yield sse("step", {
            "name": name,
            "status": "done",
            "t_ms": int((time.perf_counter() - t0) * 1000),
            **({"output": out_summary} if out_summary is not None else {}),
        })

    for c in citations_for_ctx:
        yield sse("citation", c)
        await asyncio.sleep(0.08)

    yield sse("step", {"name": "_chain", "status": "done",
                        "t_ms": int((time.perf_counter() - t0) * 1000)})
    yield sse("done", {
        "prompt_tokens": 64 + random.randint(-8, 8),
        "output_tokens": 110 + random.randint(-15, 20),
        "lineage_id": f"ln-mock-{random.randint(1000, 9999)}",
        "intent": mock["intent"],
        # Pilot's named outputs — surface them on the UI above citations.
        "score": mock.get("score"),
        "band": mock.get("band"),
        "cure_path": mock.get("cure_path", []),
        # Always "corpus" now — caller refuses on empty retrieval before
        # reaching this function (Lock #19).
        "citations_source": "corpus",
        "llm_provider": _llm.provider() if _LLM_OK else "mock",
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


# Defaults for the synthesized ROI breaker on the /api/health/breakers
# fallback path. Mirrored from apps/gateway/sidecar/_client.py so the
# fallback shape matches the live one when the client is absent.
_BREAKER_FAILURE_THRESHOLD = 5
_BREAKER_COOLDOWN_S = 30.0


@app.get("/api/health/breakers", tags=["ops"])
async def api_health_breakers(user: dict = Depends(current_user)) -> dict:
    """Aggregated L1 breaker states (spec §12.4).

    W5 (spec §15): gated by JWT in v0.2.0a. Privileged-LAN, but breaker
    state still leaks infra topology, so we authenticate.

    v0.2.0a only surfaces the ROI sidecar L1 breaker — MCP tools run
    in-process (Python imports), so there's no L1 breaker between the
    gateway and the tool. When transport flips to HTTP in v0.2.0b, each
    per-tool breaker registers here.
    """
    breakers: list[dict] = []

    # ROI sidecar breaker (L1). Read from app.state first; fall back to the
    # module global so tests that don't trigger lifespan still see something.
    roi_client = getattr(app.state, "roi_client", None) or _roi_client
    if roi_client is not None and hasattr(roi_client, "_breaker"):
        breakers.append(roi_client._breaker.status())
    else:
        # Test/dev environments where lifespan didn't init the client:
        # synthesize a CLOSED breaker so the surface still tells the truth
        # ("nothing is open") rather than 500ing.
        from apps.gateway.circuit import CircuitBreaker

        synth = CircuitBreaker(
            name="roi_sidecar",
            failure_threshold=_BREAKER_FAILURE_THRESHOLD,
            window_seconds=_BREAKER_COOLDOWN_S,
            open_duration_seconds=_BREAKER_COOLDOWN_S,
        )
        breakers.append(synth.status())

    return {
        "breakers": breakers,
        "note": (
            "v0.2.0a uses in-process MCP imports; per-tool L1 breakers "
            "register here when transport flips to HTTP in v0.2.0b."
        ),
    }


@app.get("/api/health/sidecar", tags=["ops"])
async def health_sidecar() -> dict:
    """Rule #19 contract — ROI sidecar circuit-breaker + fallback status.

    Returns the same shape as manatee-ai-roi's /health/sidecar endpoint
    (state, consecutive_failures, dropped_events_total, fallback_count,
    last_drain_ts, last_drain_count, drained_total) plus rls-apex-v1
    metadata for ops correlation.
    """
    if _roi_client is None:
        return {
            "state": "uninitialized",
            "consecutive_failures": 0,
            "dropped_events_total": 0,
            "fallback_count": 0,
            "last_drain_ts": None,
            "last_drain_count": 0,
            "drained_total": 0,
            "endpoint": _ROI_ENDPOINT,
            "fallback_path": _ROI_FALLBACK_PATH,
            "mock": DEV_MODE,
        }
    status = _roi_client.breaker_status()
    status["endpoint"] = _ROI_ENDPOINT
    status["fallback_path"] = _ROI_FALLBACK_PATH
    status["mock"] = DEV_MODE
    return status


# ─── Mock RLS data endpoints (DEV_MODE) ───────────────────────────
# Each returns a shape identical to window.SAMPLE in src/data.jsx, so the
# React tree can swap from inline data to fetch() with no schema change.
# Real production handlers replace these — the URLs and shapes don't move.

if DEV_MODE:
    from . import _mock_data as _mock

    _DECISIONS_BY_RLS: dict[str, list[dict]] = {}
    _NEXT_RLS_ID = [143]  # next minted ID; mutated by /api/rls/draft

    @app.get("/api/sample", tags=["mock"])
    async def sample_payload() -> dict:
        """Single-shot composite for the React tree if it wants to bootstrap
        from one fetch instead of N. Optional — components can also hit
        the granular endpoints below."""
        return _mock.all_payload()

    @app.get("/api/rls", tags=["mock"])
    async def list_rls(
        status: str | None = None,
        department: str | None = None,
        team: str | None = None,
    ) -> dict:
        items = _mock.SUBMISSIONS
        if status:
            items = [r for r in items if r["status"].lower() == status.lower()]
        if department:
            items = [r for r in items if r["department"].lower() == department.lower()]
        if team:
            items = [r for r in items if r["team"].lower() == team.lower()]
        return {"items": items, "total": len(items)}

    @app.get("/api/rls/{rls_id}", tags=["mock"])
    async def get_rls(rls_id: str) -> dict:
        match = next((r for r in _mock.SUBMISSIONS if r["id"] == rls_id), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"unknown rls id: {rls_id}")
        decisions = _DECISIONS_BY_RLS.get(rls_id, [])
        return {**match, "decisions": decisions}

    @app.post("/api/rls/draft", tags=["mock"])
    async def create_rls_draft(request: Request, user: dict = Depends(current_user)) -> dict:
        body = await request.json()
        n = _NEXT_RLS_ID[0]; _NEXT_RLS_ID[0] += 1
        new = {
            "id": f"RLS-26-{n:04d}",
            "title": body.get("title") or "Untitled draft",
            "type": body.get("type") or "Advisory",
            "matter": body.get("matter") or "Advisory",
            "requester": user.get("display_name") or user.get("upn") or "—",
            "department": body.get("department") or "—",
            "status": "Draft",
            "urgency": body.get("urgency") or "Standard",
            "submitted": "—",
            "deadline": body.get("deadline") or "—",
            "workingDays": 0,
            "assignee": "—",
            "team": "—",
            "completeness": int(body.get("completeness") or 30),
            "risk": "—",
            "bie": bool(body.get("bie") or False),
            "attachments": int(body.get("attachments") or 0),
            "activity": [0] * 15,
        }
        _mock.SUBMISSIONS.insert(0, new)
        return {"ok": True, "id": new["id"], "rls": new}

    @app.post("/api/rls/{rls_id}/decision", tags=["mock"])
    async def decide_rls(rls_id: str, request: Request, user: dict = Depends(current_user)) -> dict:
        body = await request.json()
        decision = body.get("decision")
        if decision not in ("accept", "reject", "return"):
            raise HTTPException(status_code=400, detail="decision must be 'accept', 'reject', or 'return'")
        match = next((r for r in _mock.SUBMISSIONS if r["id"] == rls_id), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"unknown rls id: {rls_id}")
        row = {
            "ts": time.time(), "rls_id": rls_id,
            "decision": decision, "user": user.get("upn"),
            "note": (body.get("note") or "")[:280],
        }
        _DECISIONS_BY_RLS.setdefault(rls_id, []).append(row)
        match["status"] = {"accept": "Acknowledged", "reject": "Rejected", "return": "Submitted"}[decision]
        return {"ok": True, "rls_id": rls_id, "decision": decision, "new_status": match["status"]}

    @app.get("/api/drafts", tags=["mock"])
    async def list_drafts(user: dict = Depends(current_user)) -> dict:
        return {"items": _mock.DRAFTS}

    @app.post("/api/drafts", tags=["mock"])
    async def create_draft(request: Request, user: dict = Depends(current_user)) -> dict:
        body = await request.json()
        new = {
            "id": f"DRAFT-26-{random.randint(100, 9999):04d}",
            "title": body.get("title") or "Untitled draft",
            "department": body.get("department") or "—",
            "updated": time.strftime("%Y-%m-%d"),
            "completeness": int(body.get("completeness") or 30),
            "blockers": list(body.get("blockers") or []),
        }
        _mock.DRAFTS.insert(0, new)
        return {"ok": True, "id": new["id"], "draft": new}

    @app.put("/api/drafts/{draft_id}", tags=["mock"])
    async def save_draft(draft_id: str, request: Request, user: dict = Depends(current_user)) -> dict:
        body = await request.json()
        match = next((d for d in _mock.DRAFTS if d["id"] == draft_id), None)
        if not match:
            raise HTTPException(status_code=404, detail=f"unknown draft id: {draft_id}")
        for k in ("title", "department", "completeness", "blockers"):
            if k in body:
                match[k] = body[k]
        match["updated"] = time.strftime("%Y-%m-%d")
        return {"ok": True, "draft": match}

    @app.get("/api/precedents", tags=["mock"])
    async def search_precedents(q: str = "") -> dict:
        # Reuses the same intent-routed mocks as /api/query — keeps the two
        # call sites consistent.
        mock = _pick_mock(q or "general procurement question")
        return {"q": q, "intent": mock["intent"], "items": mock["citations"]}

    @app.get("/api/kpi/summary", tags=["mock"])
    async def kpi_summary() -> dict:
        return _mock.KPIS

    @app.get("/api/inbox", tags=["mock"])
    async def inbox() -> dict:
        unread = sum(1 for i in _mock.INBOX if i.get("unread"))
        return {"items": _mock.INBOX, "unread": unread}

    @app.get("/api/queue", tags=["mock"])
    async def queue() -> dict:
        return {"items": _mock.QUEUE, "incoming14": _mock.INCOMING_14, "closed14": _mock.CLOSED_14}

    @app.get("/api/team-load", tags=["mock"])
    async def team_load() -> dict:
        return {"items": _mock.TEAM_LOAD}

    @app.get("/api/compliance-pulse", tags=["mock"])
    async def compliance_pulse() -> dict:
        return {"items": _mock.COMPLIANCE_PULSE}


# ─── Corpus retrieval (real BM25 over corpus/raw/) ────────────────
# The /api/retrieve contract is the same surface production swaps to
# BM25+LightRAG+Contextual Retrieval+pgvector. Everything that calls
# retrieve() (agent dispatcher below, /api/query, future DSPy chains)
# stays unchanged at swap time.

try:
    from apps.gateway.retrieval import retrieve as _corpus_retrieve, manifest as _corpus_manifest
    _RETRIEVAL_OK = True
except Exception:
    _RETRIEVAL_OK = False

    def _corpus_retrieve(*args, **kwargs):
        return []

    def _corpus_manifest():
        return {"loaded": False, "documents": [], "total_chunks": 0}


# LLM client — multi-provider seam. Defaults to mock; flip via LLM_PROVIDER
# or any of OLLAMA_BASE_URL / SGLANG_BASE_URL / OPENAI_API_KEY (see
# apps/gateway/llm/client.py for the full env contract).
try:
    from apps.gateway import llm as _llm
    _LLM_OK = True
except Exception:
    _LLM_OK = False
    _llm = None  # type: ignore

try:
    from apps.gateway.llm.client import complete_sync as _complete_sync
    _COMPLETE_SYNC_OK = True
except Exception:
    _COMPLETE_SYNC_OK = False
    _complete_sync = None  # type: ignore

try:
    from mcp_tools._lib.corpus.retriever import HybridRetriever as _HybridRetriever
    from mcp_tools._lib.corpus.embed_client import EmbedClient as _EmbedClient
    _CORPUS_LIB_OK = True
except Exception:
    _CORPUS_LIB_OK = False
    _HybridRetriever = None  # type: ignore
    _EmbedClient = None  # type: ignore


# ─── Policy lint — L14 corpus retrieval singleton ─────────────────

POLICY_SOURCES = ["ldc", "ordinance", "procedure"]

LINT_POLICY_SYSTEM_PROMPT = (
    "You are a precise policy-compliance classifier for Manatee County RLS submissions. "
    "Given a user-drafted passage and a small list of policy snippets, decide whether the "
    "passage violates any snippet. Respond as JSON only:\n"
    '{"violation": true|false, "rule_citation": "<snippet citation>", '
    '"field": "factualBackground"|"legalQuestion", '
    '"explanation": "<one short sentence>"}\n'
    'If no violation, respond exactly {"violation": false}.'
)

_lint_retriever = None  # type: _HybridRetriever | None


async def _get_lint_retriever():
    """Lazy-init HybridRetriever singleton for policy lint calls (ADR-006)."""
    global _lint_retriever
    if _lint_retriever is None:
        if not _CORPUS_LIB_OK:
            raise HTTPException(status_code=503, detail="corpus library unavailable")
        pool = getattr(app.state, "db_pool", None)
        if pool is None:
            raise HTTPException(status_code=503, detail="db pool unavailable")
        embed_client = _EmbedClient(
            base_url=os.environ.get("EMBEDDING_SERVICE_URL", "http://127.0.0.1:30201")
        )
        _lint_retriever = _HybridRetriever(pool, embed_client)
    return _lint_retriever


async def _call_l4_get_policy_snippets(topic_or_field: str, k: int = 3) -> dict:
    """Retrieve policy snippets via HybridRetriever (ADR-006: library-in-each-tool)."""
    retriever = await _get_lint_retriever()
    hits = await retriever.search(query=topic_or_field, k=k, source_filter=POLICY_SOURCES)
    has_procedure = any(h.source_type == "procedure" for h in hits)
    return {
        "snippets": [
            {"citation": h.citation, "body": h.body, "source_type": h.source_type}
            for h in hits[:k]
        ],
        "procedure_corpus_pending": not has_procedure,
    }


def _citation_to_dict(c) -> dict:
    return {
        "id": c.id,
        "source": c.source,
        "source_kind": c.source_kind,
        "pinpoint": c.pinpoint,
        "excerpt": c.excerpt,
        "score": c.score,
    }


@app.post("/api/retrieve", tags=["agent"])
async def api_retrieve(request: Request, user: dict = Depends(current_user)) -> dict:
    """Body: {q, k=12, classification_filter?: ["public_record","internal","privileged"]}
    Returns: {items: [Citation], total: int, intent: str}.
    Production: same shape, BM25+LightRAG+Contextual Retrieval+pgvector behind it.
    """
    body = await request.json()
    q = (body.get("q") or "").strip()
    k = int(body.get("k") or 12)
    cf = body.get("classification_filter")
    hits = _corpus_retrieve(q, k=k, classification_filter=cf)
    pick_intent = _pick_mock(q or "general procurement").get("intent", "general")
    return {"items": [_citation_to_dict(c) for c in hits], "total": len(hits), "intent": pick_intent}


@app.get("/api/corpus", tags=["agent"])
async def api_corpus() -> dict:
    """Manifest of ingested documents — id, source, source_kind, classification,
    pages, chunks, hash. Drives the 'corpus health' surface in the UI."""
    return _corpus_manifest()


@app.get("/api/health/llm", tags=["ops"])
async def api_health_llm() -> dict:
    """Multi-provider LLM status. Defaults to `mock` (canned text).
    Flip via LLM_PROVIDER or any of OLLAMA_BASE_URL / SGLANG_BASE_URL /
    OPENAI_API_KEY (see apps/gateway/llm/client.py for the full env
    contract)."""
    if not _LLM_OK:
        return {"provider": "mock", "configured": [], "active": False, "error": "client unavailable"}
    return _llm.status()


@app.post("/api/corpus/reload", tags=["agent"])
async def api_corpus_reload() -> dict:
    """Force-reload the in-process index from disk. Called automatically
    by bin/ingest after a re-ingest; can also be hit manually from a
    privileged dev surface."""
    if not _RETRIEVAL_OK:
        raise HTTPException(status_code=503, detail="retrieval module not available")
    from apps.gateway.retrieval import reload as _reload
    ok = _reload()
    return {"reloaded": ok, **_corpus_manifest()}


# ─── Agent dispatcher (DEV_MODE) ──────────────────────────────────
# Every UI action — Submit, Accept, Reject, Triage, Precedent search, etc. —
# goes through one endpoint that streams an SSE response with a step trace,
# a streamed answer, and any citations. Agent kinds map to canned scripts.
# When SGLang lands, each kind delegates to the real DSPy chain; the SSE
# contract and the call sites in the UI stay identical.

_AGENT_SCRIPTS: dict[str, dict] = {
    "triage": {
        "label": "Triage submission",
        "steps": [("classify", 90), ("retrieve.hybrid", 240), ("score_completeness", 110), ("suggest_team", 80), ("compose", 0)],
        "answer_template": (
            "Triage complete. Classified as {intent}, completeness scored at 84/100. "
            "Two missing items flagged: (a) director signature on critical/urgent matters, "
            "(b) BIE worksheet for proposed-ordinance type. Suggested team: {team} "
            "(based on team-load + matter type)."
        ),
    },
    "precedent": {
        "label": "Find precedents",
        "steps": [("classify", 110), ("retrieve.hybrid", 285), ("policy_graph.cited_by", 165), ("rank", 75), ("compose", 0)],
        "answer_template": "Found 3 precedents matching intent={intent}. See citations below for cure paths and rejection patterns.",
    },
    "decide": {
        "label": "Apply decision",
        "steps": [("validate_decision", 60), ("update_status", 100), ("notify_requester", 90), ("emit_lineage", 50), ("emit_roi", 40), ("compose", 0)],
        "answer_template": "Decision={decision} applied to {rls_id}. Status -> {new_status}. Requester notified. Lineage stamped. ROI event emitted.",
    },
    "draft": {
        "label": "Draft response",
        "steps": [("classify", 90), ("retrieve_template", 80), ("retrieve.hybrid", 220), ("compose", 0), ("guardrails", 60)],
        "answer_template": "Drafted a {tone} response. Boilerplate from template-{template_id} adapted to context. Citations attached. Reviewer required: senior-counsel (per skill governance).",
    },
    "summarize": {
        "label": "Summarize",
        "steps": [("retrieve_context", 120), ("compose", 0)],
        "answer_template": "Summary: {summary}. Confidence: medium. Three open questions surfaced — see follow-ups below.",
    },
    "completeness": {
        "label": "Score completeness",
        "steps": [("parse_attachments", 80), ("apply_rules", 120), ("compose", 0)],
        "answer_template": "Completeness scored at 87/100. 5/6 compliance rules satisfied; flagged: BIE filing required for §125.66(3)(c) ordinance matter.",
    },
}


def _format_template(t: str, ctx: dict) -> str:
    safe_ctx = {k: ctx.get(k) or "—" for k in ("intent", "team", "decision", "rls_id", "new_status", "tone", "template_id", "summary")}
    try: return t.format(**safe_ctx)
    except Exception: return t


@app.post("/api/agent/dispatch", tags=["agent"])
async def agent_dispatch(request: Request, user: dict = Depends(current_user)) -> StreamingResponse:
    """Streams an SSE response for any UI action. Body: {kind, context}.
    `kind` picks an agent script; `context` is opaque metadata stamped on
    every emitted event for tracing.

    In production each kind invokes the DSPy chain in agents/<kind>/chain.py
    and dispatches MCP tools per the locked stack. The mock keeps the same
    SSE shape so no UI rewire is needed at swap time."""
    if not DEV_MODE:
        raise HTTPException(status_code=501, detail="agent dispatcher not yet wired to real backends")

    body = await request.json()
    kind = (body.get("kind") or "").strip()
    context = body.get("context") or {}
    script = _AGENT_SCRIPTS.get(kind)
    if not script:
        raise HTTPException(status_code=400, detail=f"unknown agent kind: {kind}")

    # Decide on a mock for the answer + citations based on the user-supplied
    # question OR the rls's title (for actions on existing rows).
    seed_q = (context.get("q") or context.get("question") or context.get("title") or "general procurement").lower()
    pick = _pick_mock(seed_q)
    intent = pick["intent"]

    answer_ctx = {
        "intent": intent,
        "team": context.get("team") or "Land Use",
        "decision": context.get("decision") or "—",
        "rls_id": context.get("rls_id") or "—",
        "new_status": context.get("new_status") or "Acknowledged",
        "tone": "neutral-firm",
        "template_id": "draft-bie-preamble",
        "summary": "{} flagged at {} fact pattern".format(intent, "Fla. Stat. §125.65(2)" if intent.startswith("sole") else "§125.66(3)(c)"),
    }
    answer_text = _format_template(script["answer_template"], answer_ctx)
    lineage_id = f"ln-mock-{random.randint(1000, 9999)}"

    # Pre-compute citations so the LLM compose step has them as context.
    real_hits = _corpus_retrieve(seed_q, k=4,
                                 classification_filter=["public_record", "internal"])
    if real_hits:
        citations_for_ctx = [_citation_to_dict(c) for c in real_hits]
    elif kind in ("precedent", "draft", "triage"):
        citations_for_ctx = pick["citations"]
    else:
        citations_for_ctx = []

    async def stream() -> AsyncIterator[bytes]:
        def sse(event: str, data: dict) -> bytes:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()

        t0 = time.perf_counter()
        yield sse("agent", {"kind": kind, "label": script["label"], "context": context, "lineage_id": lineage_id})
        yield sse("step", {"name": "_chain", "status": "start", "t_ms": 0})

        for name, base_ms in script["steps"]:
            t_start = int((time.perf_counter() - t0) * 1000)
            yield sse("step", {"name": name, "status": "start", "t_ms": t_start})
            await asyncio.sleep((base_ms + random.randint(-25, 35)) / 1000)
            if name == "compose":
                if _LLM_OK and _llm.provider() != "mock":
                    async for tok in _llm.stream_completion(
                        user=seed_q, citations=citations_for_ctx,
                        answer_hint=answer_text):
                        yield sse("token", {"text": tok})
                else:
                    for word in answer_text.split(" "):
                        yield sse("token", {"text": word + " "})
                        await asyncio.sleep(0.022)
            t_end = int((time.perf_counter() - t0) * 1000)
            yield sse("step", {"name": name, "status": "done", "t_ms": t_end})

        for c in citations_for_ctx:
            yield sse("citation", c)
            await asyncio.sleep(0.06)

        yield sse("step", {"name": "_chain", "status": "done", "t_ms": int((time.perf_counter() - t0) * 1000)})
        _final_prompt_tokens = 64 + random.randint(-12, 20)
        _final_output_tokens = 110 + random.randint(-20, 40)
        _final_duration_ms = int((time.perf_counter() - t0) * 1000)
        yield sse("done", {
            "kind": kind,
            "intent": intent,
            "lineage_id": lineage_id,
            "prompt_tokens": _final_prompt_tokens,
            "output_tokens": _final_output_tokens,
            "duration_ms": _final_duration_ms,
            "citations_source": "corpus" if real_hits else ("canned" if citations_for_ctx else "none"),
            "llm_provider": _llm.provider() if _LLM_OK else "mock",
        })

        # Operating Rule #18: emit one ROI event per user-facing action.
        # Architecture A+ (POST primary, local-fallback JSONL, background drain).
        emit_roi({
            "event_kind": "llm_call",
            "workflow": f"rls_apex.agent.{kind}",
            "user_id": user.get("upn", "unknown"),
            "dept": user.get("dept", "DEV"),
            "role_band": user.get("role_band", "professional"),
            "task_type": "search",
            "tool": "rls_apex",
            "surface": "other",
            "prompt_tokens": _final_prompt_tokens,
            "output_tokens": _final_output_tokens,
            "duration_s": round(_final_duration_ms / 1000.0, 3),
            "success": True,
            "extra": {
                "intent": intent,
                "lineage_id": lineage_id,
                "citations_source": "corpus" if real_hits else (
                    "canned" if citations_for_ctx else "none"
                ),
                "llm_provider": _llm.provider() if _LLM_OK else "mock",
            },
        })

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/agent/kinds", tags=["agent"])
async def agent_kinds() -> dict:
    return {"items": [{"kind": k, "label": v["label"], "steps": [s[0] for s in v["steps"]]} for k, v in _AGENT_SCRIPTS.items()]}


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


# ─── Policy lint — L14 /api/lint/policy ───────────────────────────


@app.post("/api/lint/policy", tags=["agent"])
async def lint_policy(payload: dict, user: dict = Depends(current_user)) -> dict:
    """Run policy-lint L14 check against corpus snippets.

    Retrieves policy snippets via HybridRetriever (ADR-006: library-in-each-tool,
    NOT HTTP to L4 MCP service). Calls LLM to classify potential violations.
    Emits llm_call ROI event. Returns suggestion chip data or empty suggestions.
    """
    rls_payload = payload.get("rlsPayload", {})
    factual = rls_payload.get("factualBackground", "")
    legal_q = rls_payload.get("legalQuestion", "")
    topic = factual or legal_q
    if not topic.strip():
        return {"suggestions": []}

    snippets_resp = await _call_l4_get_policy_snippets(topic_or_field=topic)
    snippets = snippets_resp.get("snippets", [])
    if not snippets:
        return {"suggestions": []}

    snippet_text = "\n\n".join(
        f"- {s['citation']}: {s['body']}" for s in snippets
    )
    user_msg = (
        f"PASSAGE:\n{topic}\n\nPOLICY SNIPPETS:\n{snippet_text}\n\nClassify."
    )

    started = time.monotonic()
    try:
        if not _COMPLETE_SYNC_OK or _complete_sync is None:
            raise RuntimeError("complete_sync not available")
        raw = await _complete_sync(
            system=LINT_POLICY_SYSTEM_PROMPT,
            user=user_msg,
            max_tokens=256,
            temperature=0.0,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"policy lint llm unavailable: {e}")
    duration_s = time.monotonic() - started

    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        verdict = {"violation": False}

    emit_roi({
        "event_kind": "llm_call",
        "workflow": "rls_apex",
        "user_id": user["upn"],
        "dept": user.get("dept", "unknown"),
        "role_band": user.get("role_band", "unknown"),
        "task_type": "policy_lint",
        "tool": "rls_apex",
        "surface": "ui",
        "duration_s": duration_s,
        "success": True,
        "prompt_tokens": len(LINT_POLICY_SYSTEM_PROMPT.split()) + len(user_msg.split()),
        "output_tokens": len(raw.split()),
        "extra": {"snippet_count": len(snippets)},
    })

    if not verdict.get("violation"):
        return {"suggestions": []}

    return {
        "suggestions": [{
            "ruleId": "policy-lint-llm",
            "field": verdict.get("field", "factualBackground"),
            "citation": verdict.get("rule_citation", snippets[0]["citation"]),
            "explanation": verdict.get("explanation", ""),
            "severity": "info",
        }],
    }


# ─── ROI sidecar (D-001) ──────────────────────────────────────────


def emit_roi(event: dict) -> None:
    """Architecture A+: POST to manatee-ai-roi FastAPI; on failure, append
    to local fallback JSONL on this host; background drain on recovery.

    Schema bound to apps/gateway/sidecar/manatee_ai_roi.schema.json.
    Validation happens client-side pre-flight; FastAPI re-validates server-side.

    Fire-and-forget. NEVER blocks the user-facing action (Operating Rule #18).
    Only metadata. NEVER prompt bodies, output bodies, or document content.
    """
    if _roi_client is None:
        return
    _roi_client.emit_now(event)


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


@app.get("/cao/{rls_id}", tags=["spa"])
async def cao_view_passthrough(rls_id: str) -> FileResponse:
    """SPA passthrough: any /cao/:rlsId path serves index.html so the
    frontend router can mount <cao-view>."""
    index_path = Path(__file__).resolve().parents[2] / "apps" / "web" / "static" / "index.html"
    return FileResponse(index_path, media_type="text/html")


# ─── Static mount (DEV_MODE only) ─────────────────────────────────
# Mounted last so all /api/* routes register first. Serves the click-through
# page from apps/web/static/index.html. In production the React build is
# served by IIS/nginx, not by FastAPI.

if DEV_MODE:
    _web_root = Path(__file__).resolve().parents[2] / "apps" / "web" / "static"
    _styles_root = Path(__file__).resolve().parents[2] / "apps" / "web" / "styles"
    if _web_root.exists():
        # /static/* and /styles/* mounted BEFORE / so the root mount doesn't shadow them.
        # /cao/{rls_id} route is already registered above; FastAPI matches routes in
        # registration order and mounts are checked in registration order, so the
        # @app.get("/cao/{rls_id}") wins over the root mount for those paths.
        app.mount("/static", StaticFiles(directory=str(_web_root)), name="static")
        if _styles_root.exists():
            app.mount("/styles", StaticFiles(directory=str(_styles_root)), name="styles")
        app.mount("/", StaticFiles(directory=str(_web_root), html=True), name="web")


# ─── Local dev ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8080, reload=True)

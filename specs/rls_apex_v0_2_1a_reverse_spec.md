# RLS Apex v0.2.1a — As-Shipped Reverse Specification

> Reverse-engineered from the working tree. Read-only analysis. No plan/spec
> docs in `docs/superpowers/` are cited as truth — only code is authoritative.
>
> | | |
> |---|---|
> | Repo | `/Users/ejarbe/Projects/rls-apex-v1` |
> | Branch | `feat/v0.2.0a-backend` |
> | HEAD | `daeeadc766a38f801d6776bce2e58a29d02f61c2` |
> | Tag | `v0.2.1a-rc2` (HEAD is `v0.2.1a-rc2-1-gdaeeadc`, one commit past the tag) |
> | Method | spec-miner: Scope → Explore → Trace → Document (EARS) → Flag |
> | Audience | Feeds task #41 (frontend-parity review). §10 is the handoff table. |

Legend: **[OBSERVED]** = grounded in code at the cited location. **[INFERRED]** =
reasoned from code, not directly asserted. `file:line` cites the working tree.

---

## 1. Technology Stack & Architecture

**[OBSERVED]**

| Layer | Technology | Evidence |
|---|---|---|
| Gateway | FastAPI + Pydantic v2, uvicorn | `apps/gateway/main.py:33-36,1626-1629` |
| MCP tools | FastMCP 2.3.0 (`custom_route`, `get_http_request`; no middleware) | `mcp_tools/_lib/server.py:13-19,26-28` |
| JWT s2s | python-jose RS256, aud=`tool.<name>`, iss=`rls-apex-gateway`, ±5s leeway | `mcp_tools/_lib/jwt_verify.py:15-18,33-71` |
| DB | PostgreSQL 16 + asyncpg pool; pgvector `vector(1024)` + HNSW cosine; GIN tsvector | `apps/gateway/db/pool.py`, `alembic/versions/0abf792e8ba7_*.py`, `c5f2154f8fb3_*.py` |
| ORM/migrations | Alembic; hand-written Pydantic domain models | `alembic/versions/*`, `apps/gateway/db/models.py:1-10` |
| Retrieval (gateway) | In-process BM25 over `corpus/index/bm25.json` (`rank_bm25.BM25Okapi`) | `apps/gateway/retrieval/retrieve.py:50-56,109-151` |
| Retrieval (MCP lib) | HybridRetriever: Postgres `ts_rank_cd` BM25 + pgvector ANN + RRF merge | `mcp_tools/_lib/corpus/retriever.py:1-5,30-201` |
| Embedding | FastAPI service wrapping Ollama `mxbai-embed-large` (1024-d), single-probe breaker | `services/embedding/service.py`, `services/embedding/config.py` |
| LLM | Multi-provider seam: `mock` (default) / `ollama` / `sglang` / `openai` / `auto` | `apps/gateway/llm/client.py:20-69` |
| DSPy chain | `PrecedentRetriever` uncompiled — defined, NOT wired into any request path | `agents/precedent-retriever/chain.py` |
| ROI telemetry | Architecture A+ vendored client (POST + JSONL fallback + drain loop) | `apps/gateway/sidecar/_client.py` |
| Circuit breaker | Shared `CircuitBreaker` (rolling-window, single-probe HALF_OPEN) | `apps/gateway/circuit/breaker.py` |
| Health aggregator | 30s background poller over 6 HTTP services | `apps/gateway/health_aggregator.py` |
| Scraper | Stream A FastAPI service + systemd-timer one-shot orchestrator, 5 sources | `services/scraper/service.py`, `services/scraper/config.py` |
| Redaction | Stream B pipeline: regex + LLM detectors → `redaction_audit` | `services/redaction/pipeline.py`, `services/redaction/detectors/*` |
| Frontend | Lit 3.2.1 web components, native ES modules + importmap (no build step) | `apps/web/static/index.html`, `apps/web/static/components/*` |

**Architecture shape (observed):** A single FastAPI gateway is the front door.
v0.2.0a-style in-process tool imports (`classify_matter`, `extract_fields`,
`validate_rls_structure`) coexist with v0.2.1a standalone HTTP MCP tool services
(`list_rls_precedents`, `get_policy_snippets`, `check_code_enforcement_litigation`,
`check_urgency_rules`) plus the scraper and embedding services. The Lit SPA is
served from `apps/web/static` only in `DEV_MODE`; production serving is by
IIS/nginx (`apps/gateway/main.py:1605-1621`).

**[INFERRED]** The codebase is mid-migration: the gateway still imports the three
v0.2.0a tools as Python functions while the four v0.2.1a tools run over HTTP. The
gateway never calls the four HTTP tools — `call_tool` is `raise NotImplementedError`
(`apps/gateway/main.py:1583-1594`).

---

## 2. Module / Directory Structure

```
apps/gateway/
  main.py                  # FastAPI app, all routes, ROI emit_roi(), mock SSE
  health_aggregator.py     # W8 30s poller over 6 HTTP services
  _mock_data.py            # DEV_MODE canned RLS/KPI/inbox data
  circuit/breaker.py       # shared CircuitBreaker state machine
  db/models.py             # Pydantic domain models (hand-written from domain.yaml)
  db/pool.py               # asyncpg pool factory + healthcheck
  llm/client.py            # multi-provider stream_completion / complete_sync
  retrieval/{ingest,retrieve}.py  # in-process BM25 corpus
  sidecar/_client.py       # vendored A+ RoiClient + validate_event_for_persistence
  sidecar/manatee_ai_roi.schema.json  # vendored JSON Schema
mcp_tools/
  _lib/server.py           # build_tool_app() — FastMCP + ROI + require_actor
  _lib/jwt_verify.py       # RS256 verify, JwtClaims
  _lib/roi_emit.py         # ToolRoiEmitter (per-tool A+ emit)
  _lib/corpus/{retriever,embed_client,types}.py  # HybridRetriever, EmbedClient, Hit
  classify_matter/         # in-process mock (port 30101 only in __main__)
  extract_fields/          # in-process mock (port 30102 only in __main__)
  validate_rls_structure/  # in-process REAL logic (port 30100 only in __main__)
  list_rls_precedents/     # HTTP MCP tool, port 30103 (L3)
  get_policy_snippets/     # HTTP MCP tool, port 30104 (L4)
  check_code_enforcement_litigation/  # HTTP MCP tool, port 30105 (L1)
  check_urgency_rules/     # HTTP MCP tool, port 30106 (L2) + calendar.py
services/
  embedding/               # port 30201, Ollama mxbai-embed-large + breaker
  redaction/               # Stream B pipeline + detectors + audit + CLI
  scraper/                 # port 30200, 5 sources + systemd timer orchestrator
agents/precedent-retriever/chain.py   # DSPy chain (defined, NOT wired)
alembic/versions/          # 001 baseline → corpus_chunks → redaction_audit → vector
apps/web/static/           # Lit SPA (the SHIPPED frontend)
apps/web/static/{rls-api.js,agent-driver.js,chat.html,vendor/react*}  # NOT loaded — legacy
```

---

## 3. Observed Requirements (EARS)

### 3.1 Gateway boot & lifespan

- **R-001** **[OBSERVED]** While `LLM_PROVIDER` is not `mock` and a configured
  provider base URL hostname is outside the county-LAN allowlist
  (`manatee-civic-ai.internal`, `infer01`, `llm01`, `localhost`, `127.0.0.1`,
  suffix-matched), the gateway shall refuse to boot by raising `RuntimeError`.
  `main.py:79-158,175`. No bypass flag; `LLM_PROVIDER=mock` skips the check.
- **R-002** **[OBSERVED]** When the gateway starts, the system shall initialize a
  `RoiClient`, call `start_drain_loop()`, and expose it on `app.state.roi_client`;
  if init raises, the system shall log and continue with `_roi_client=None`
  (telemetry never blocks boot). `main.py:181-196`.
- **R-003** **[OBSERVED]** When the gateway starts, the system shall create an
  asyncpg pool sized `(min=1, max=8)`; if pool creation fails, the system shall
  set `app.state.db_pool=None` and continue (degraded). `main.py:218-230`,
  `db/pool.py:18,22-36`.
- **R-004** **[OBSERVED]** When the gateway starts, the system shall create a
  `HealthAggregator` and run its `run_forever()` poller as a background task;
  on shutdown the task shall be cancelled. `main.py:231-241`.
- **R-005** **[OBSERVED]** While `DEV_AUTH_BYPASS=1`, the system shall attempt to
  load (and auto-ingest if missing) the in-process BM25 corpus from
  `corpus/raw/`. `main.py:45,197-217`.

### 3.2 Authentication & authorization

- **R-006** **[OBSERVED]** While `DEV_AUTH_BYPASS=1`, `current_user` shall return a
  synthetic user `{upn=DEV_USER_UPN, role=general-counsel, dept=DEV,
  role_band=professional}`. `main.py:277-291`.
- **R-007** **[OBSERVED]** While `DEV_AUTH_BYPASS=1` and `RLS_ALLOWLIST` is
  non-empty, when the dev UPN is not in the allowlist, the system shall return
  HTTP 403. `main.py:52-53,279-281`.
- **R-008** **[OBSERVED]** While not in `DEV_MODE`, `current_user` shall raise HTTP
  501 (`oidc not yet wired`). Real Entra ID OIDC is unimplemented. `main.py:292-298`.
- **R-009** **[OBSERVED]** Every MCP HTTP tool function shall call
  `require_actor()` first; the system shall reject requests lacking a
  `Bearer` token or failing RS256 verify (aud=`tool.<name>`,
  iss=`rls-apex-gateway`, required claims `actor_id/actor_role/tenant`) with
  `JwtRejection`. `mcp_tools/_lib/server.py:71-91`, `jwt_verify.py:33-71`, and
  each `server.py` (e.g. `list_rls_precedents/server.py:87`).

### 3.3 Gateway routes (shipped)

The table below is the complete route surface of `apps/gateway/main.py`. "Auth"
= `Depends(current_user)`. DEV-only routes register only while
`DEV_AUTH_BYPASS=1`.

| # | Method | Path | Auth | Request | Response (200) | Other status | Code |
|---|---|---|---|---|---|---|---|
| R-010 | GET | `/api/me` | yes | — | `{upn, display_name, initials, role}` | 403/501 via auth | `main.py:304-317` |
| R-011 | GET | `/healthz` | no | — | `{ok, version, corpus:{loaded,docs,chunks}}` | — | `main.py:320-334` |
| R-012 | GET | `/readyz` | no | — | `{status:"ready"|"degraded", db,...}` | — | `main.py:337-343` |
| R-013 | POST | `/api/intake` | yes | `{text:1..10000}` | `{classification, rlsPayload}` | 422 empty text | `main.py:349-391` |
| R-014 | POST | `/api/validate` | yes | `{rlsPayload:dict}` | `ValidationResult` dump `{blocking,warnings}` | — | `main.py:397-419` |
| R-015 | GET | `/api/cao/brief?rlsId=` | yes | query `rlsId` | `{rlsId,summary[],keyFacts[],risk,suggestedNextSteps[]}` (canned) | — | `main.py:425-461` |
| R-016 | POST | `/api/query` | yes | `{q,...}` | DEV: SSE stream OR HTTP 200 refusal JSON; prod: 501 | 501 non-dev | `main.py:484-565` |
| R-017 | POST | `/api/feedback` | yes | `{decision:"accept"|"reject",...}` | `{ok,decision}` (JSONL append) | 400 bad decision | `main.py:838-858` |
| R-018 | GET | `/api/feedback/recent` | yes | — | `{items:[...]}` last 10 | — | `main.py:861-867` |
| R-019 | GET | `/api/health/breakers` | yes | — | `{breakers:[{name,state,...}], note}` | — | `main.py:877-916` |
| R-020 | GET | `/api/health/sidecar` | no | — | A+ breaker status + endpoint/fallback/mock | — | `main.py:919-945` |
| R-021 | GET | `/api/health/aggregated` | no | — | `{status,tools,checked_at}` | 503 if degraded/uninit | `main.py:948-970` |
| R-022 | POST | `/api/retrieve` | yes | `{q,k=12,classification_filter?}` | `{items:[Citation],total,intent}` | — | `main.py:1222-1234` |
| R-023 | GET | `/api/corpus` | no | — | manifest `{loaded,documents,total_chunks}` | — | `main.py:1237-1241` |
| R-024 | GET | `/api/health/llm` | no | — | `{provider,configured,model,endpoints,active}` | — | `main.py:1244-1252` |
| R-025 | POST | `/api/corpus/reload` | no | — | `{reloaded, ...manifest}` | 503 if retrieval n/a | `main.py:1255-1264` |
| R-026 | POST | `/api/agent/dispatch` | yes | `{kind,context}` | SSE stream | 400 unknown kind / 501 non-dev | `main.py:1319-1436` |
| R-027 | GET | `/api/agent/kinds` | no | — | `{items:[{kind,label,steps}]}` | — | `main.py:1439-1441` |
| R-028 | GET | `/api/skills/templates` | yes | — | — | 501 always | `main.py:1444-1448` |
| R-029 | PUT | `/api/skills/templates/{slug}` | yes | — | — | 501 always | `main.py:1451-1462` |
| R-030 | GET/PUT/POST/DELETE | `/api/matters/{matter_id}/drafts/{path}` | no | — | — | 501 + `Retry-After: 1209600` | `main.py:1468-1480` |
| R-031 | POST | `/api/lint/policy` | yes | `{rlsPayload}` | `{suggestions:[...]}` (may be empty) | 503 LLM unavailable | `main.py:1486-1559` |
| R-032 | GET | `/cao/{rls_id}` | no | — | `index.html` (SPA passthrough) | — | `main.py:1597-1602` |
| R-033 | GET | `/api/sample` | DEV | — | composite mock payload | — | `main.py:984-989` |
| R-034 | GET | `/api/rls` | DEV | `?status&department&team` | `{items,total}` | — | `main.py:991-1004` |
| R-035 | GET | `/api/rls/{rls_id}` | DEV | — | row + `decisions` | 404 unknown | `main.py:1006-1012` |
| R-036 | POST | `/api/rls/draft` | DEV+auth | json body | `{ok,id,rls}` | — | `main.py:1014-1039` |
| R-037 | POST | `/api/rls/{rls_id}/decision` | DEV+auth | `{decision,note}` | `{ok,rls_id,decision,new_status}` | 400/404 | `main.py:1041-1057` |
| R-038 | GET/POST/PUT | `/api/drafts`, `/api/drafts/{id}` | DEV+auth | json | draft objects | 404 unknown | `main.py:1059-1087` |
| R-039 | GET | `/api/precedents?q=` | DEV | — | `{q,intent,items}` | — | `main.py:1089-1094` |
| R-040 | GET | `/api/kpi/summary`,`/api/inbox`,`/api/queue`,`/api/team-load`,`/api/compliance-pulse` | DEV | — | canned dicts | — | `main.py:1096-1115` |

- **R-041** **[OBSERVED]** When `/api/intake` is called, the system shall invoke
  the in-process `classify_text` and `extract_text` functions (bypassing the
  FastMCP wrapper), assemble `rlsPayload = {**extracted, type}`, and emit one
  `llm_call` ROI event (`workflow=rls_apex.intake`, `prompt_tokens=0`,
  `output_tokens=0`). `main.py:363-391`.
- **R-042** **[OBSERVED]** When `/api/validate` is called, the system shall run
  `validate_dict` and emit a `tool_invocation` ROI event with
  `extra.blocking_count`. `main.py:404-419`.
- **R-043** **[OBSERVED]** While `DEV_MODE`, when `/api/query` retrieval yields
  zero hits, the system shall return HTTP 200 `QueryRefusalResponse`
  (`refused=true, reason=no_grounding`) and emit an `escalation` ROI event
  (`success=false`, `extra.refusal_reason=no_grounding`, no query text).
  `main.py:464-535`.
- **R-044** **[OBSERVED]** While `DEV_MODE` and retrieval is non-empty, `/api/query`
  shall stream SSE events `step`/`token`/`citation`/`done`; tokens come from
  the real LLM provider when `_llm.provider()!="mock"`, else from the
  intent-routed mock answer template. `main.py:537-559,763-829`.
- **R-045** **[OBSERVED]** `/api/lint/policy` shall retrieve policy snippets via an
  in-process `HybridRetriever` singleton (NOT an HTTP call to the L4 tool —
  ADR-006 library-in-each-tool), call `complete_sync` for classification, emit
  an `llm_call` ROI event, and return `{suggestions:[...]}` only when the LLM
  verdict has `violation=true`. `main.py:1181-1208,1486-1559`. Raises 503 when
  the corpus library, DB pool, or `complete_sync` is unavailable.

### 3.4 MCP toolbox (7 tools)

- **R-046** **[OBSERVED]** `validate_rls_structure` is real pure-logic: it flags 5
  required-field blocks (`MISSING_*`), `SUBJECT_TOO_LONG` (>50 chars), and 2
  warnings (`NO_SERVICES_REQUESTED`, `LEGAL_QUESTION_OR_BACKGROUND_THIN`). No
  backend; no L2 breaker. `mcp_tools/validate_rls_structure/server.py:33-92`.
- **R-047** **[OBSERVED]** `classify_matter` is a regex keyword-count mock over 5
  types, confidence `min(0.95, 1-exp(-0.4·hits))`, default
  `general_advisory @ 0.2`. `mcp_tools/classify_matter/server.py:24-60`.
- **R-048** **[OBSERVED]** `extract_fields` is a heuristic mock: first sentence →
  `subject` (≤50), full text → `factualBackground`, empty `legalQuestion`;
  returns camelCase keys. `mcp_tools/extract_fields/server.py:30-43`.
- **R-049** **[OBSERVED]** `list_rls_precedents` (L3, port 30103) shall search the
  HybridRetriever over `["internal_opinion","fl_ag_opinion"]`, over-fetch
  `k*4`, post-filter `internal_opinion` by `matter_type` while `fl_ag_opinion`
  always passes, return `{hits,metadata}`, and emit a `rag_hit` ROI event.
  `mcp_tools/list_rls_precedents/server.py:26,66-162`.
- **R-050** **[OBSERVED]** `get_policy_snippets` (L4, port 30104) shall search over
  `["ldc","ordinance","procedure"]` (no over-fetch, no matter filter), set
  `procedure_corpus_pending = not any(source_type=="procedure")`, return
  `{snippets,procedure_corpus_pending}`, and emit a `rag_hit` event.
  `mcp_tools/get_policy_snippets/server.py:26,66-149`.
- **R-051** **[OBSERVED]** `check_code_enforcement_litigation` (L1, port 30105) is
  a pure regex rule engine: returns `applicable=False` unless
  `matter_type=="code_enforcement_litigation"`; otherwise flags
  `CE_NOV_DATE_MISSING` and `CE_HEARING_DEADLINE_MISSING`. No external calls,
  no breaker. `mcp_tools/check_code_enforcement_litigation/server.py:49-145`.
- **R-052** **[OBSERVED]** `check_urgency_rules` (L2, port 30106) returns
  `applicable=False` unless `urgency=="critical"`; otherwise flags
  `URG_DEADLINE_MISSING`, `URG_DEADLINE_TOO_FAR` (>15 working days via a
  Postgres calendar query), `URG_ADVERSE_MISSING`, and `URG_DEADLINE_INVALID`
  on calendar/DB failure. `mcp_tools/check_urgency_rules/server.py:61-177`.
- **R-053** **[OBSERVED]** Each MCP HTTP tool shall expose `GET /health` returning
  `{tool, breakers:[breaker_status]}` via FastMCP `custom_route`.
  `mcp_tools/_lib/server.py:67-69`.
- **R-054** **[INFERRED]** Tool ports `30100/30101/30102` for the three in-process
  tools exist only in `if __name__ == "__main__"` blocks; in v0.2.1a these run
  as Python imports inside the gateway, not as standalone services (consistent
  with their exclusion from `TOOL_HEALTH_ENDPOINTS`). e.g.
  `mcp_tools/validate_rls_structure/server.py:119-122`.

### 3.5 Retrieval & embedding

- **R-055** **[OBSERVED]** `HybridRetriever.search` runs BM25 (`ts_rank_cd`) and
  pgvector ANN (`embedding <=> $1::vector`) in parallel and merges by
  Reciprocal Rank Fusion (`rrf_k=60`, tie-break source_id ASC), normalizing
  scores to [0,1]. `mcp_tools/_lib/corpus/retriever.py:30-201`.
- **R-056** **[OBSERVED]** When `EmbedClient.embed` raises `EmbeddingUnavailable`
  (timeout/connect/HTTP/503), `HybridRetriever` shall fall back to BM25-only and
  tag each hit `metadata.retrieval_mode="bm25_only"`.
  `retriever.py:43-58`, `embed_client.py:20-36`.
- **R-057** **[OBSERVED]** Both retrievers support point-in-time filtering:
  `valid_to IS NULL` when `valid_at` is None, else the
  `valid_from <= t AND (valid_to IS NULL OR valid_to > t)` range.
  `retriever.py:71-74,127-130`.
- **R-058** **[OBSERVED]** The gateway in-process retriever (`/api/retrieve`,
  `/api/query`, `/api/lint/policy` pre-fetch path) is a *separate*
  implementation: BM25 over `corpus/index/bm25.json`, dedupes one chunk per
  doc, filters by `doc.classification`. NOT the HybridRetriever.
  `apps/gateway/retrieval/retrieve.py:109-151`.
- **R-059** **[OBSERVED]** `embedding-service` (port 30201) wraps Ollama
  `mxbai-embed-large`; `/embed` guards a single-probe `EmbeddingBreaker`
  (threshold 3, open 30s), returns 503 when open, 502 on Ollama error or
  wrong dim (≠1024). `/health` returns 503 unless `state==closed AND
  ollama_reachable`. `services/embedding/service.py:33-110`,
  `services/embedding/breaker.py`, `config.py`.
- **R-060** **[OBSERVED]** `corpus_chunks` final schema: `embedding vector(1024)`
  with HNSW cosine index `idx_corpus_chunks_hnsw`, GIN tsvector
  `idx_corpus_chunks_fulltext`, partial unique current index. Migration head
  is `c5f2154f8fb3` (chain: `001 → 0abf792e8ba7 → bf24fe8528f5 → ac6351a1ccd0
  → b1d742f07a46 → c5f2154f8fb3`). `alembic/versions/*`.

### 3.6 Circuit breaker

- **R-061** **[OBSERVED]** `CircuitBreaker` implements closed→open
  (≥`failure_threshold` failures inside `window_seconds`)→half-open (after
  `open_duration_seconds`, lazily via the `state` property)→closed (probe
  success) / →open (probe fail). `apps/gateway/circuit/breaker.py:69-150`.
- **R-062** **[OBSERVED]** In HALF_OPEN the breaker enforces a single probe:
  concurrent callers receive `BreakerOpenError` while `_probe_in_flight` is
  set. `breaker.py:99-104,126-149`.
- **R-063** **[OBSERVED]** `status()` returns `{name,state,consecutive_failures,
  last_failure_ts,last_success_ts}`. `breaker.py:151-159`.
- **R-064** **[OBSERVED]** Wrapped external deps: ROI POST (gateway
  `RoiClient._breaker`, threshold 5 / 30s), per-tool ROI POST
  (`ToolRoiEmitter._breaker`, 5 / 30s), redaction LLM detector
  (`get_or_create_breaker`), embedding→Ollama (`EmbeddingBreaker`), scraper
  per-host (`services/scraper/breaker.py`, threshold 3 / window 300s / open
  3600s). `sidecar/_client.py:224-229`, `roi_emit.py:31-36`,
  `redaction/pipeline.py:73-77`, `scraper/config.py:23-27`.
- **R-065** **[OBSERVED][FLAG]** The gateway↔MCP-tool path has NO L1 breaker:
  `call_tool` is `raise NotImplementedError`; the three v0.2.0a tools are
  in-process imports. `/api/health/breakers` documents this and synthesizes a
  CLOSED `roi_sidecar` breaker when the client is absent.
  `main.py:877-916,1583-1594`.

### 3.7 ROI sidecar (Architecture A+)

- **R-066** **[OBSERVED]** `emit_roi(event)` is fire-and-forget; if
  `_roi_client is None` it is a no-op. `main.py:1565-1577`.
- **R-067** **[OBSERVED]** `RoiClient.emit_now` stamps `started_at`+`event_id`,
  schedules `_dispatch`; on no running loop it increments
  `dropped_events_total` (fail-open). `sidecar/_client.py:253-266`.
- **R-068** **[OBSERVED]** `_dispatch` pre-validates via
  `validate_event_for_persistence` (required keys, valid `event_kind`,
  `llm_call` requires both token counts); invalid → drop+count. POST goes
  through `_breaker.call`; on `BreakerOpenError` or POST failure the event is
  appended to the JSONL fallback. `sidecar/_client.py:131-146,307-323`.
- **R-069** **[OBSERVED]** A background drain loop every 60s drains the JSONL
  fallback when the breaker is CLOSED, halting on first failed re-POST and
  rewriting the remaining tail. `sidecar/_client.py:293-303,353-385`.
- **R-070** **[OBSERVED]** Per-tool emitters (`ToolRoiEmitter`) reuse the same
  `CircuitBreaker` class and `validate_event_for_persistence`, but POST to
  `{ROI_ENDPOINT}/events` (note: gateway client posts to
  `{endpoint}/v1/events`) with their own JSONL fallback. `roi_emit.py:42-71`
  vs `sidecar/_client.py:330,345`. *(Path divergence: `/events` vs
  `/v1/events` — see §7.)*
- **R-071** **[OBSERVED]** `/api/health/sidecar` returns the A+ status
  (`state,consecutive_failures,dropped_events_total,fallback_count,
  last_drain_ts,last_drain_count,drained_total`) + endpoint/fallback/mock.
  `main.py:919-945`.

#### ROI emit-point inventory (every emit in shipped code)

| Surface | event_kind | workflow | Code |
|---|---|---|---|
| `/api/intake` | `llm_call` | `rls_apex.intake` | `main.py:373-387` |
| `/api/validate` | `tool_invocation` | `rls_apex.validate` | `main.py:407-418` |
| `/api/cao/brief` | `tool_invocation` | `rls_apex.cao_brief` | `main.py:449-460` |
| `/api/query` refusal | `escalation` | `rls_apex.query` | `main.py:522-533` |
| `/api/query` stream close | `tool_invocation` | `rls_apex.query` | `main.py:547-557` |
| `/api/agent/dispatch` | `llm_call` | `rls_apex.agent.<kind>` | `main.py:1413-1434` |
| `/api/lint/policy` | `llm_call` | `rls_apex` | `main.py:1532-1546` |
| MCP `validate_rls_structure` | `tool_invocation` | `rls_apex.mcp.validate_rls_structure` | `validate_rls_structure/server.py:105-115` |
| MCP `classify_matter` | `tool_invocation` | `rls_apex.mcp.classify_matter` | `classify_matter/server.py:69-79` |
| MCP `extract_fields` | `tool_invocation` | `rls_apex.mcp.extract_fields` | `extract_fields/server.py:52-62` |
| MCP `list_rls_precedents` | `rag_hit` | `rls_apex.mcp.list_rls_precedents` | `list_rls_precedents/server.py:122-151` |
| MCP `get_policy_snippets` | `rag_hit` | `rls_apex.mcp.get_policy_snippets` | `get_policy_snippets/server.py:109-144` |
| MCP `check_code_enforcement_litigation` | `tool_invocation` | `rls_apex.mcp.check_code_enforcement_litigation` | `check_code_enforcement_litigation/server.py:76-141` |
| MCP `check_urgency_rules` | `tool_invocation` | `rls_apex.mcp.check_urgency_rules` | `check_urgency_rules/server.py:82-173` |
| Scraper per-source | `tool_invocation` | `rls_apex.scrape` | `services/scraper/service.py:200-212` |
| Redaction pipeline | `tool_invocation` | `rls_apex.redaction` | `services/redaction/pipeline.py:97-114` |

- **R-072** **[OBSERVED][FLAG]** `/api/feedback` (R-017) does NOT emit a ROI event
  — it only appends JSONL; the code comment says production should emit but it
  is unimplemented. `main.py:838-858`. Per Operating Rule #18 (every
  user-facing action emits) this is a coverage gap.

### 3.8 Health aggregator (W8)

- **R-073** **[OBSERVED]** `HealthAggregator` polls exactly 6 HTTP services every
  30s (5s per-request timeout): `list_rls_precedents:30103`,
  `get_policy_snippets:30104`, `check_code_enforcement_litigation:30105`,
  `check_urgency_rules:30106`, `scraper_service:30200`,
  `embedding_service:30201`. In-process tools are explicitly excluded.
  `health_aggregator.py:24-31`.
- **R-074** **[OBSERVED]** `overall_status="healthy"` only if every polled tool
  reports `status=="healthy"`; else `"degraded"`. `/api/health/aggregated`
  returns 200 when healthy, 503 when degraded or aggregator uninitialized.
  `health_aggregator.py:79-84`, `main.py:948-970`.

### 3.9 Scraper (Stream A) & Redaction (Stream B)

- **R-075** **[OBSERVED]** The scraper service exposes `/health` (always HTTP 200)
  with `last_run_per_source`, `breaker_states`, `checked_at`; DB-down yields
  null last-runs without 500ing. `services/scraper/service.py:74-120`.
- **R-076** **[OBSERVED]** `run_scrape_job` iterates 5 sources (municode_ldc,
  municode_ch2_26, mymanatee_ldr, mymanatee_calendar, fl_ag_opinions),
  per-source failures isolated, emits one fire-and-forget `tool_invocation`
  ROI event per source. `services/scraper/service.py:157-223`.
- **R-077** **[OBSERVED]** The redaction pipeline runs regex detectors (SSN,
  phone, Bates `MC-NNNNNN`) always + an LLM detector wrapped in a circuit
  breaker (non-fatal), de-dupes by `(start,end)` regex-first, writes pending
  spans to `redaction_audit`, emits a `tool_invocation` ROI event
  (`user_id=system.redaction`). `services/redaction/pipeline.py:46-118`,
  `detectors/regex_detectors.py:23-57`.

### 3.10 Frontend (Lit SPA — the shipped surface)

- **R-078** **[OBSERVED]** `index.html` loads exactly `<rls-shell>` via
  `/static/main.js` with an importmap mapping `lit` → `/static/lib/lit-3.2.1.min.js`.
  No React, no `rls-api.js`, no `agent-driver.js`, no `chat.html`.
  `apps/web/static/index.html:9-16`, `main.js:1`.
- **R-079** **[OBSERVED]** On connect, `rls-shell` calls `api.fetchMe()`
  (`/api/me`), hydrates a localStorage-backed store, attaches router,
  validator-runner, auto-correct, smart-surface, and a 30s breaker poller.
  `rls-shell.js:44-67`.
- **R-080** **[OBSERVED]** The Requester flow is a 5-step single-persona wizard:
  `intake → form → status → cure → submit` driven by `#step=` hash; the only
  other route is `/cao/:rlsId` rendering `<cao-view>`. The app-header role
  `<select>` (`requester`/`cao`) is client-state only — it does not gate any
  backend or change rendering. `router.js:1-30`, `rls-shell.js:77-106`,
  `app-header.js:28-49`.
- **R-081** **[OBSERVED]** `<intake-panel>` POSTs `/api/intake`, merges
  `rlsPayload`+`classification` into the draft store, mints a client-side
  `rls-<uuid>`, and navigates to `form`. It also offers a "Skip — I have a
  draft" branch with manual fields and no API call. `intake-panel.js:35-83`.
- **R-082** **[OBSERVED]** The validator runs as a debounced (750ms) drafting
  assistant: on every `rlsPayload` change it POSTs `/api/validate` (aborting
  the prior request), writes `blocking/warnings/cureSteps/lastValidated` back
  to the store, and pushes an event-log entry. Hash compare prevents
  self-cascade. `validator-runner.js:1-59`.
- **R-083** **[OBSERVED]** `<form-panel>` renders 4 fields (title, department,
  legalQuestion, factualBackground), shows auto-correct suggestion chips with
  Apply/Dismiss, and field errors only for blurred fields (smart-surface).
  `form-panel.js:4,48-82`, `smart-surface.js:3-9`.
- **R-084** **[OBSERVED]** Auto-correct ships 4 rules: 3 synchronous
  (`subject-trim` ≤50, `title-case-fix`, `date-infer`) and 1 async
  `policy-lint-llm` that POSTs `/api/lint/policy` — gated to fire only for
  fields in `ui.blurredFields`, with dismiss-dedup by `(ruleId,field,hash)`.
  Errors are swallowed (advisory, never blocking). `auto-correct.js:8-170`.
- **R-085** **[OBSERVED]** `<status-panel>` derives `ready` vs `fixes` from
  `blocking.length===0 && lastValidated`; `<cure-path-panel>` lists
  `draft.cureSteps` with a disabled "Mark Done"; `<submit-panel>` is a disabled
  Submit + copy-JSON escape hatch (v0.2.1 deferral). No API calls in these
  three. `status-panel.js:28-56`, `cure-path-panel.js:26-46`,
  `submit-panel.js:30-49`.
- **R-086** **[OBSERVED]** `<cao-view>` GETs `/api/cao/brief?rlsId=`; the
  Accept/Return/Reject buttons only show a transient toast
  ("decision write goes live in v0.2.1") — there is NO backend decision write
  path wired in the shipped SPA. `cao-view.js:28-58`.
- **R-087** **[OBSERVED]** `<copilot-feed>` is a read-only view of
  `session.eventLog` (last 200). `<rls-disclaimer-banner>` is static.
  `copilot-feed.js:30-49`.

---

## 4. Non-Functional Observations

- **Auth:** Real OIDC unimplemented (501). The only working auth is the
  `DEV_AUTH_BYPASS` synthetic user + `RLS_ALLOWLIST` gate. MCP tools enforce
  RS256 JWT per-function (FastMCP has no middleware) — but the gateway never
  signs/sends one (`call_tool` is `NotImplementedError`). `main.py:1583-1594`.
- **Telemetry isolation:** Architecture A+ everywhere — POST + JSONL fallback +
  breaker; telemetry never blocks the user action (R-066/067). Coverage gap at
  `/api/feedback` (R-072).
- **Circuit breaking:** Every cross-process external dep is breaker-wrapped
  except the (non-existent) gateway→tool HTTP path (R-064/065). Two breaker
  *implementations* coexist: the shared `CircuitBreaker` and the
  embedding-service's own `EmbeddingBreaker` (functionally equivalent
  single-probe, intentionally mirrors manatee-civic-ai).
- **DB pool sizing:** gateway `(1,8)`; MCP tool pools created ad-hoc in
  `list_rls_precedents`/`get_policy_snippets`/`check_urgency_rules` with
  `max_size=4..5` (note: `db/pool.py` documents `(1,2)` for tools but the HTTP
  tools do not import that factory — they call `asyncpg.create_pool` directly,
  so the documented aggregate ≤32 is not enforced). `list_rls_precedents/server.py:47-55`.
- **PII discipline:** ROI extra dicts never carry query/prompt bodies; refusal
  path explicitly omits query text (R-043). Redaction writes spans to an audit
  table with `reviewer_upn IS NULL` = pending (`db/models.py:176-206`).
- **No DSPy in any request path:** `PrecedentRetriever` is defined but unused;
  all "agent" behavior is canned SSE mocks (R-044/R-026).

---

## 5. Inferred Acceptance Criteria

- **[INFERRED]** AC-1: With `DEV_AUTH_BYPASS=1` and the corpus index present,
  `POST /api/query {q:"sole-source ..."}` streams `step/token/citation/done`
  with `citations_source="corpus"`; an unmatched query returns HTTP 200
  `{refused:true}`.
- **[INFERRED]** AC-2: `POST /api/validate {rlsPayload:{}}` returns 5 blocking
  `MISSING_*` issues + 2 warnings.
- **[INFERRED]** AC-3: A misconfigured `LLM_PROVIDER=openai` with an external
  `OPENAI_BASE_URL` aborts gateway boot (R-001).
- **[INFERRED]** AC-4: `GET /api/health/aggregated` returns 503 until all 6 HTTP
  services report healthy.
- **[INFERRED]** AC-5: When `embedding-service` returns 503, an MCP retrieval
  call still returns BM25-only hits tagged `retrieval_mode=bm25_only`.
- **[INFERRED]** AC-6: The Lit SPA loads, fetches `/api/me`, and the 5-step
  Requester wizard advances on debounced validation; CAO buttons are inert.

---

## 6. Uncertainties & Questions

> Recommendation table (decisions with ≥2 options). Single-option items are
> stated as flags, not questions.

| # | Uncertainty | Option A | Option B | Posterior | Recommended |
|---|---|---|---|---|---|
| Q1 | `/api/feedback` emits no ROI (R-072) — Rule #18 gap | Treat as known v0.2.1a deferral; document only | File as a defect for v0.2.1 | A 0.70 / B 0.30 | A — code comment shows intentional deferral; B if Rule #18 is a hard gate |
| Q2 | ROI POST path divergence: gateway `/v1/events` vs per-tool `/events` (R-070) | Intentional (different sidecar API versions) | Bug — tool emits will 404 against current sidecar | A 0.35 / B 0.65 | B — likely a real drift; verify against `manatee-ai-roi` route table before v0.2.1 |
| Q3 | MCP tool DB pools bypass `db/pool.py` sizing (≤32 aggregate not enforced) | Acceptable at pilot scale (≤4 conns/tool) | Re-route through factory before prod | A 0.60 / B 0.40 | A for pilot; B before any multi-tenant load |

Single-option flags (no decision, just record):
- **F1** `breakerStatus` shape mismatch makes the breaker-open banner dead code
  (see §7, primary #41 risk).
- **F2** Gateway→tool HTTP transport (`call_tool`) is unimplemented; MCP JWT
  path is exercised only by tests, never by the gateway in production.

---

## 7. Recommendations

1. **Fix the breaker-open banner (F1).** `/api/health/breakers` returns
   `{breakers:[{name,state,...}]}` (a **list of objects**, `main.py:889-916`,
   `breaker.py:151-159`). `rls-shell.js:72` stores `r.breakers` (the array)
   into `errorState.breakerStatus`. `smart-surface.js:11-14` iterates
   `Object.entries(breakerStatus)` expecting a `{name: stateString}` map and
   tests `state === 'open'`. On an array, `state` is the breaker object, so the
   `breaker-open` banner can never fire. Either reshape the API to a map or fix
   the consumer to `r.breakers.find(b => b.state === 'open')`.
2. **Resolve the ROI POST path divergence (Q2)** before v0.2.1 so per-tool
   emits don't silently 404.
3. **Decide `/api/feedback` ROI coverage (Q1)** against Operating Rule #18.
4. **Treat the legacy frontend files as deletion candidates** after confirming
   no IIS/nginx config serves them: `apps/web/static/rls-api.js`,
   `agent-driver.js`, `chat.html`, `vendor/react*`, `vendor/babel.min.js`.
5. **Document the dual retriever** (in-process BM25 vs HybridRetriever) so #41
   and future work don't assume one path. `/api/query` and `/api/retrieve` use
   BM25-over-JSON; only `/api/lint/policy` uses the pgvector HybridRetriever.

---

## 8. #41 Frontend-Parity Inputs

### 8.1 Backend endpoint → consuming UI component

| Backend endpoint | Method | Consumed by (file) | Notes for #41 |
|---|---|---|---|
| `/api/me` | GET | `rls-shell.js:47` via `core/api.js:9` | Drives upn/role; role is display-only |
| `/api/intake` | POST | `intake-panel.js:38` via `api.js:13` | Real call; wires classify+extract mocks |
| `/api/validate` | POST | `validator-runner.js:29` via `api.js:22` | Debounced drafting-assist; the live validator loop |
| `/api/cao/brief` | GET | `cao-view.js:30` via `api.js:31` | Canned brief; CAO route only |
| `/api/health/breakers` | GET | `rls-shell.js:71` via `api.js:35` | **GAP/BUG** shape mismatch — banner dead (F1) |
| `/api/lint/policy` | POST | `auto-correct.js:91` (direct fetch) | Async L14 chip; gated to blurred fields |
| `/cao/{rls_id}` | GET | browser nav → SPA passthrough | `router.js` parses `/cao/:id` |

### 8.2 Backend surface with NO UI consumer (orphans for #41)

| Endpoint | Status | Why orphaned |
|---|---|---|
| `/api/query` (SSE validator) | shipped (DEV) | No Lit component calls it; only legacy `rls-api.js`/`agent-driver.js` (not loaded) |
| `/api/agent/dispatch`, `/api/agent/kinds` | shipped (DEV) | Only `agent-driver.js` (legacy, not loaded) |
| `/api/feedback`, `/api/feedback/recent` | shipped | No SPA consumer; legacy only |
| `/api/retrieve`, `/api/corpus`, `/api/corpus/reload` | shipped | No SPA consumer |
| `/api/health/sidecar`, `/api/health/aggregated`, `/api/health/llm` | shipped | No SPA consumer (ops/W8 only) |
| `/healthz`, `/readyz` | shipped | Ops probes; no UI |
| `/api/sample`,`/api/rls*`,`/api/drafts*`,`/api/precedents`,`/api/kpi/summary`,`/api/inbox`,`/api/queue`,`/api/team-load`,`/api/compliance-pulse` | DEV mock | Only `rls-api.js` (legacy, not loaded) |
| `/api/skills/templates*` | 501 stub | Not implemented |
| `/api/matters/{id}/drafts/{path}` | 501 reserved | Namespace reservation |

### 8.3 UI calling a non-existent / changed endpoint

| UI element | Expectation | Reality | #41 action |
|---|---|---|---|
| `smart-surface.js` breaker banner | `breakerStatus` is `{name:state}` map | `/api/health/breakers` returns `{breakers:[obj]}` (F1) | Reshape API or consumer |
| `cao-view.js` Accept/Return/Reject | implies a decision write | No backend write exists (toast only) | Confirm scope: stub vs missing endpoint |
| `submit-panel.js` Submit | implies submission | Disabled by design (copy-JSON escape hatch) | Expected v0.2.1 deferral |
| `cure-path-panel.js` Mark Done | implies progress write | Disabled by design | Expected v0.2.1 deferral |
| `validator-runner.js` reads `result.cureSteps` | endpoint returns `cureSteps` | `/api/validate` → `ValidationResult` has only `blocking`/`warnings`; `cureSteps` is always absent → UI defaults to `[]` | Cure-path panel will always be empty in shipped backend |

### 8.4 Persona scoping

**[OBSERVED]** The Lit shell is Requester-only by construction: 5 steps
(intake/form/status/cure/submit). `/cao/:rlsId` is a separate, read-only route.
The app-header role selector mutates only `session.role` client-side and gates
nothing (`app-header.js:28-49`, `rls-shell.js:77-106`). There is no
backend-enforced persona.

---

*End of reverse specification. Generated read-only at HEAD `daeeadc`.*

# Decision Log

All locks from the planning session. Every entry is `Decision · Rationale · Reversal cost`. Append-only.

---

## Lock #1 — Telemetry: no PostHog

**Decision:** Phoenix (LLM traces) + Power BI (exec narrative, off the ROI sidecar) + promptfoo (prompt regression) + Inspect AI (correctness/safety eval) + `manatee_ai_roi` sidecar (per-action telemetry, Rule #18). PostHog is **not** added in v0.1.0.

**Rationale:** Existing stack already covers traces, exec dashboards, prompt regression, eval, and per-action ROI. PostHog's only novel capability is session replay — and session replay on a tool used to review privileged matters is its own large governance decision (mouse paths + timing + redaction-region geometry leak signal that can be subpoenaed). Re-evaluate at week 6 only if a specific gap surfaces.

**Reversal cost:** Low if added later (self-hosted on a new VM, ~8 services); zero if not added.

---

## Lock #2 — GitHub repo: `jarbitechture/rls-apex-v1`

**Decision:** Plan for `jarbitechture/rls-apex-v1` (private). I do not push from here. Actions workflows reference this path in `infra/github/`.

**Reversal cost:** Trivial — single rename in workflows.

---

## Lock #3 — RunPod: out of scope for v0.1.0

**Decision:** All inference on `bcc-ap-infer01` (SGLang + Qwen2.5-FP8). RunPod planned only as future offload for batch GEPA optimization — not in v0.1.0.

**Rationale:** Track B residency lock + RunPod mixes data plane with third-party. State on county infra means inference latency to RunPod (10–80ms each, 8–20 round-trips per query) makes UX worse, not better.

**Reversal cost:** Low — gateway model router is already abstracted; flipping to a RunPod endpoint is one config block.

---

## Lock #4 — Inference runtime: SGLang + Qwen2.5-FP8 on `bcc-ap-infer01`

**Decision:** SGLang's structured-output + radix cache is materially better for agent tool calling than vLLM. FP8 weights fit the L4 24GB.

**Reversal cost:** Medium — swap entails re-tuning sampling params and re-running smoke eval.

---

## Lock #5 — Auth: Entra ID OIDC at gateway, new hostname

**Decision:**
- New hostname `rls.mymanatee.org` (ITS request day 1 — slow path).
- FastAPI gateway verifies Entra ID OIDC tokens via MSAL.
- Group claim → role mapping (`attorney`, `paralegal`, `general-counsel`, `admin`).
- **Independent of cookbook's IIS/NTLM chain at `mcgpt.mymanatee.org`.** No `X-Forwarded-User` borrowing.
- Placeholders: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `OIDC_AUTHORITY`, `OIDC_REDIRECT_URI`.

**Rationale:** Cookbook is a different project. Sharing the IIS edge propagates cookbook's cert/DNS lead-time risk and conflates blast radii. Entra OIDC is the modern county pattern; rules of the cookbook (NTLM at IIS, ARR forwarding) don't apply here.

**Reversal cost:** High after launch — auth is hard to swap. Do it right now.

---

## Lock #6 — State: `bcc-db-llm01`

**Decision:** Install AGE extension on existing Postgres (verify version supports AGE — PG 11–16). Add MinIO as a new systemd unit on the same host. Expose only to `bcc-ap-llm01` + `bcc-ap-infer01` via firewalld.

**Rationale:** Server already provisioned, AD access in place, no Chris/ops lead time. AGE is self-managed only (Azure Database for PostgreSQL Flexible Server doesn't support it). Co-location with retrieval avoids 10–80ms per round-trip the WAN path would add.

**Watch-outs:**
- Single VM is a SPOF — schedule `pg_basebackup` + MinIO snapshot to a second host.
- Capacity: separate disks for `$PGDATA` and MinIO data dir; SSD for both.
- Per Rule #19, every cross-process call (Postgres, MinIO, AGE) gets a circuit breaker on the client side.
- ROI sidecar wraps the LLM call, not state calls — but log retrieval latency in the event payload to detect when state becomes the bottleneck.

**Reversal cost:** Medium — moving state means re-tuning latency budgets.

---

## Lock #7 — MCP authn boundary: separate processes, s2s auth

**Decision:** FastMCP 2.0, each tool = systemd unit (`mcp-tool@<name>.service`), HTTP transport on loopback only (`127.0.0.1:30100–30105`). Auth: RS256 JWT, gateway keypair, `aud=tool.<name>`, 60-second TTL. Each tool pulls its own Key Vault secret at boot. Two-layer circuit breakers: gateway-side per tool, tool-side per backend.

**Rationale:** Operating Rule #19 (circuit-break every external dependency) is structurally unenforceable in an in-process trust model. Per-tool least privilege is unenforceable in-process. The locked stack says this template propagates to N peer pilots — governance-as-foundation propagates well; bolt-on does not.

**Honest costs:** 6 services to operate instead of 1 (mitigated by systemd template). Two layers of breakers means two sets of thresholds (start with identical defaults, differentiate after real failure data). Loopback HTTP adds 0.3–1ms per call (negligible at chat scale).

**Open question (deferred):** Is `pilot.report_roi` a separate MCP tool (so other pilots can emit ROI uniformly) or an in-process gateway helper? Default: separate tool. If it turns out only the gateway emits, demote to in-process and we're at 5 tools.

**Reversal cost:** Medium — separate-to-monolith is easier than monolith-to-separate; the cost is the operational drift accumulated.

---

## Lock #8 — DSPy/GEPA scope: scaffold day 1, optimize weeks 5–6

**Decision:** Day-1 work — DSPy signatures + uncompiled chain + smoke eval. First GEPA compile in weeks 5–6, **gated on first 50–100 attorney-redlined examples**.

**Smoke eval naming:** `eval/smoke/smoke_eval_DO_NOT_OPTIMIZE_AGAINST.jsonl`. README in that directory explicitly states "this is plumbing, not quality." Anyone reading scores from this file as a quality T signal is misreading.

**Rationale:** GEPA against synthetic data optimizes against the wrong objective. Then real redlines arrive and 60% of outputs get rejected because the optimizer baked in a synthetic preference. Worse than no optimizer. But scaffolding the framework day 1 means week 5 is a `dspy.GEPA(metric=...).compile(student, trainset=redlines)` line, not a setup scramble.

**Reversal cost:** Trivial — DSPy is library, not infrastructure.

---

## Lock #9 — First slice: 2-week PrecedentRetriever, internal week-1 click-through

**Decision:**
- End of week 1: assistant-ui shell + mock retriever returning canned 3-doc result + citation rendering + accept/reject UI wired to no-op. **Internal audience only (you + Drew).**
- End of week 2: same shell, real BM25+LightRAG retrieval over redacted 50-opinion corpus, real DSPy chain (uncompiled), SSE streaming, ROI events firing. Stakeholder demo.

**Trap avoided:** A clickable demo at week 1 reads as "80% done" to anyone who hasn't built one. External pressure on a mocked demo anchors stakeholder feedback on UX before retrieval is real, and violates the verifiability bar ("never ship unverified claims").

**Regression condition:** If a stakeholder meeting appears on the week-1 calendar, this collapses to plain 2-week with no interim demo, and we manage the political side separately.

**Reversal cost:** N/A — this is a scoping rule, not infrastructure.

---

## Lock #10 — Skills: Templates-only in v0.1.0

**Decision:**
- **Templates** (`/skills/templates/*.md`) — UI edit triggers GitHub App service-account commit on a draft branch → senior-counsel review → merge → hot-load. Frontmatter carries governance (`reviewer_required`, `owners`, `kind`). Audit row in Postgres on every UI edit.
- **Matter drafts** — URL space reserved at `/matters/<id>/drafts/*` returning HTTP `501` with `Retry-After: weeks 5-6 semantics`. Schema, UI surface, and lineage hash all deferred to post-Reviser.

**Visual differentiation (not chrome uniformity):**

| Cue | Template surface | Matter draft surface |
|---|---|---|
| Header band | Slate ("shared") | Amber ("privileged") |
| Header label | "Template — affects all future matters" | "Matter draft — RLS-XX-XXXX — privileged" |
| Storage indicator | "Git: skills/templates/draft-bie-preamble.md" | "Postgres: matters.drafts row XXXX" |
| Save button | "Open PR for review" | "Save draft (auto-versioned)" |

**Rationale:** M depends on Reviser (weeks 5–6). M's governance (per-matter RLS in Postgres + AD group scoping + public-records exemption flags + lineage hash from T→M divergence + privileged-matter access controls) is genuinely harder than T's. Building it under deadline pressure in weeks 4–6 is strictly worse than weeks 7–10 once attorney behavior is observable.

**Reversal cost:** Low — M URL space is reserved; adding the implementation later doesn't require rewiring T.

---

## Lock #11 — Branding: prototype tokens now, brand-overlay later

**Decision:**
- `apps/web/styles/tokens/_base.css` — prototype tokens (Manatee teal, Inter, Notion-warm sidebar). Ships in v0.1.0.
- `apps/web/styles/tokens/_brand-overlay.css` — empty placeholder with comment block. Drop county brand kit here later via single PR.
- `apps/web/styles/index.css` — imports `_base` then `_brand-overlay` so cascade naturally overrides.
- Components consume CSS variables, never hex literals.

**Reversal cost:** Trivial — one PR to drop the kit in.

---

## Lock #12 — `domain.yaml` seed entities

**Decision:** Seed from prototype vocabulary plus three flagged additions. Redline before any codegen runs against it.

**Entities seeded:**

| # | Entity | Origin | Notes |
|---|---|---|---|
| 1 | `Matter` | Prototype | Container — keys per-matter ACLs, audit, classification |
| 2 | `Worksheet` | Prototype (renamed from `BIEWorksheet`) | **Polymorphic with `kind: BIE \| permit \| hr_qa \| budget_memo`.** Per the BIE PDF (Fla. Stat. §125.66(3)(c)), BIE is one statutorily-defined worksheet kind; the locked stack says this template propagates to Permit pre-screen / HR Q&A / Budget memo, so polymorphic now is cheap and refactoring later is not. |
| 3 | `Statute` | Prototype | — |
| 4 | `Opinion` | Prototype | Description disambiguates judicial opinion vs. county legal opinion |
| 5 | `Skill` | Prototype | Polymorphic per Lock #10 — `kind: template \| matter_draft`. Only `template` lives in git for v0.1.0 |
| 6 | `LineageEvent` | Prototype | T→M divergence point + downstream edit chain (per the lineage MCP tool) |
| 7 | `ROIEvent` | Prototype | Schema-bound to `manatee_ai_roi.schema` per Rule #18 — imported, not redefined |
| 8 | `Citation` | **Claude addition** | Pinpoint refs inside Statute/Opinion. Legal RAG without citation as first-class hides provenance — and provenance is the whole reason for the pilot. |
| 9 | `Redline` | **Claude addition** | Attorney review markup. Gates GEPA week 5–6 (Lock #8). Without a typed entity, the GEPA training set has no schema. |
| 10 | `MatterClassification` | **Claude addition** | `privileged \| public_record \| confidential`. Drives per-matter ACL on `mcp-tools/docs`, exclusion from corpus indexing, public-records exemption flags. Load-bearing across at least four prior decisions in this session. |

**Reversal cost:** Low while no migrations have run; medium after Alembic baseline.

---

## v0.1.1 increments (session 2026-05-06)

### D-001 implementation — Architecture A+ wire-up

**Decision:** ROI sidecar emits via Architecture A+ (POST primary to manatee-ai-roi FastAPI, local-fallback JSONL on this host when the breaker opens, background drain on recovery). Vendored async client at `apps/gateway/sidecar/_client.py` (~290 LoC, self-contained — no `manatee_ai_roi` Python dep per Lock #1 spirit).

**Schema:** `apps/gateway/sidecar/manatee_ai_roi.schema.json` regenerated from manatee-ai-roi schema 1.1.0 (adds `event_kind` enum with 11 values). Drift caught by CI in the manatee-ai-roi repo (`tests/test_json_schema_drift.py`).

**Defaults (per spec §9 sign-off):**

- POST timeout: 3s
- Drain interval: 60s
- Breaker: 5 consecutive failures → open 30s → half-open probe
- Endpoint: `$ROI_EVENTS_URL` (default `http://localhost:8000`)
- Fallback path: `$ROI_FALLBACK_PATH` (default `/var/log/rls-apex-v1/roi-fallback.jsonl`)

**Wired emit points:**

| # | Location | event_kind | Status |
|---|---|---|---|
| 1 | `agent_dispatch` mock stream "done" event | `llm_call` | wired |
| 2 | `/api/query` real handler stream close | `llm_call` | TODO (handler currently 501) |
| 3 | citation surface | `rag_hit` | TODO |
| 4 | decision write | `tool_invocation` (`tool=decision_writer`) | TODO |
| 5 | workflow step boundary | `tool_invocation` | TODO |
| 6 | MCP tool invocation hook | `tool_invocation` (`tool=<systemd_unit>`) | TODO (gated on Lock #7 wire-up) |

**Health:** `/api/health/sidecar` returns the same shape as manatee-ai-roi's `/health/sidecar` (state, consecutive_failures, dropped_events_total, fallback_count, last_drain_ts, last_drain_count, drained_total) plus rls-apex-v1 metadata (endpoint, fallback_path, mock).

**Reversal cost:** Low — `_client.py` can swap transports without touching `emit_roi(event: dict)` call sites.

---

## v0.2.0 reframe (session 2026-05-08)

Full spec: [`docs/superpowers/specs/2026-05-08-rls-apex-mcp-reframe-design.md`](./docs/superpowers/specs/2026-05-08-rls-apex-mcp-reframe-design.md).

These six Locks supersede the v0.1.0 stack assumptions for L1 / L3 / L4 / L6. They do not touch Lock #2 (repo location), Lock #5 (auth), Lock #7 (MCP isolation pattern), Lock #11 (token strategy).

---

## Lock #13 — Apex as procedural LLM agent (MCP-first)

**Decision:** Apex presents as the official RLS gate agent, not a model demo. Three sharply-separated layers:

- **LLM orchestrator** — language, reasoning, drafting, narration. Calls MCP tools. Cannot override their decisions.
- **MCP toolbox** — every County-specific rule, lookup, lifecycle action lives here as a separate systemd unit (Lock #7 isolation pattern).
- **Apex UI** — surfaces statuses, checks, cure paths. No model guts visible.

The LLM-facing API is ~12 RLS-domain tools (`classify_matter`, `extract_fields`, `validate_rls_structure`, `check_code_enforcement_litigation`, `list_rls_precedents`, etc.), not the original six generic tools (retrieve, policy-graph, ontology, lineage, docs, report-roi). The generic tools become substrate underneath.

**Rationale:** The LLM as single source of truth was the load-bearing assumption that justified DSPy/GEPA scaffolding, multi-provider seams, and assistant-ui — none of which the pilot needs. Inverting to "tools decide, LLM narrates" fixes governance (rules are deterministic and auditable), portability (model swap doesn't change the surface), and scope (no optimizer scaffold day 1).

**Reversal cost:** High — touches every layer. Effectively a v0.2 redirect.

---

## Lock #14 — Boring official UI · narrative status · co-authoring intake

**Decision:**

- Drop `assistant-ui`. The UI is an institutional gate, not a chat app. Build the surface from scratch using the existing `apps/web` React tree at the `f7009cb` design pass; do not migrate to Next.js again.
- Replace numeric "55/100 REJECTION PROBABILITY" with binary status (`NeedsFixes` | `ReadyForCAO`) plus a one-sentence narrative. Internal scoring stays internal — surfaced only via the ROI layer if at all.
- Intake is "What's going on?" free text. LLM + `classify_matter` + `extract_fields` co-author the RLS draft. The user edits a pre-populated form, not a blank form.
- Cure path is interactive: each step has Mark Done that triggers a re-validation; status flips automatically when blocking issues clear.

**Rationale:** The UI has been replaced twice already (May 6 Next.js rollback). assistant-ui was a forward bet on chat sophistication the pilot doesn't have. Numeric scoring creates false precision and is illegible to attorneys. Co-authoring is the actual value over paste-and-grade.

**Reversal cost:** Medium — UI rewrite scoped to `apps/web`. The token system (Lock #11) survives.

---

## Lock #15 — Single inference provider for v0.2

**Decision:** v0.2 runs against **Qwen2.5:7b on the existing Ollama instance on `bcc-ap-infer01`**. No SGLang. No multi-provider seam. No OpenAI fallback. The Manatee SLM swap is a config change behind the unchanged MCP surface.

**Rationale:** SGLang + Qwen14B-FP8 + Ollama + OpenAI was four providers behind one seam for an LLM that's not even in the LLM-facing API of the new design (the LLM only narrates around tool outputs). One provider is enough until evidence shows it isn't. Cookbook already runs Qwen2.5 on Ollama on the same GPU; reusing that capacity halves operational complexity.

**Watch-outs:**

- Single GPU SPOF on `bcc-ap-infer01`. Acceptable for v0.2 pilot scale (10 concurrent, 50 RLSs/day).
- GPU contention with cookbook. Mitigation: SGLang radix cache shares prefixes; queue at gateway if contention shows.

**Reversal cost:** Low — gateway model router stays abstracted. Adding SGLang or a second provider is a config block, not a refactor.

---

## Lock #16 — Defer AGE · MinIO · OnBase

**Decision:** v0.2 ships with Postgres 16 + pgvector only on `bcc-db-llm01`. AGE is not installed. MinIO is not installed. OnBase integration is not built. Attachments live as `bytea` columns or filesystem; policy-graph queries become recursive CTEs and FK joins.

**Rationale:** AGE / MinIO / OnBase were forward bets on graph queries, large attachments, and existing legal-doc integration that the v0.2 user journey doesn't exercise. AGE specifically forces self-managed Postgres (Azure managed PG flavor doesn't support it), adding operational tax for a benefit that doesn't exist yet. domain.yaml entities make the schema portable — these can be added as new MCP tools without changing the LLM-facing surface.

**Reversal cost:** Low — additive. AGE installation is a Lock #6 reactivation. MinIO is a new systemd unit + a new MCP tool. OnBase is a connector behind `mcp.docs`.

---

## Lock #17 — `manatee-ai-roi` is the single metrics surface

**Decision:** Co-pilot's Metrics tab and any other "metrics" surface in Apex queries the `manatee-ai-roi` dataset via a gateway endpoint. No separate metrics database. No PostHog (Lock #1 stands). Internal scores or counts that aren't ROI events don't get a UI surface.

Every action emits a ROI event using schema 1.1.0:

- LLM call (intake, lint, brief, cure narration) → `llm_call`
- MCP tool call (each of the 12) → `tool_invocation`
- Precedent / policy retrieval → `rag_hit`
- Status transition (`update_rls_status`) → `tool_invocation`
- Cure step validation → `tool_invocation`
- Co-pilot Ask → `llm_call` + dependent `tool_invocation`s

**Rationale:** Operating Rule #18 already requires this. Locking it as a project-level Lock prevents drift. Two metrics surfaces would mean two pipelines, two access patterns, two governance reviews — and the Power BI / renewal narrative is built off `manatee-ai-roi` already.

**Reversal cost:** Low — already the architectural direction. The Lock just makes it explicit so future PRs can't grow a parallel telemetry path.

---

## Lock #18 — Two-layer circuit breaker spec

**Decision:** Operating Rule #19 (circuit-break every external dependency) is made concrete with a two-layer pattern and explicit thresholds.

**Layer 1 (gateway-side)** — one breaker per outbound dependency:

| Boundary | Threshold | Open | Fallback |
|---|---|---|---|
| Gateway → Ollama | 5 fails / 30s | 30s + probe | 503 to UI; status surface |
| Gateway → manatee-ai-roi | 5 consecutive | 30s + probe | JSONL local fallback (already implemented) |
| Gateway → MCP tool (×12) | 5 fails / 30s | 30s + probe | Per-tool: read=empty+flag; write=fail loud |

**Layer 2 (tool-side)** — one breaker per backend each tool calls:

| Tool | Backend | Fallback |
|---|---|---|
| `list_rls_precedents` | PG + retrieval | Empty list + `breaker_open=true` |
| `get_policy_snippets` | PG + retrieval | Empty list + flag |
| `update_rls_status` | PG (write) | Fail loudly |
| `get_rls_metadata` | PG (read) | Cached + staleness flag |
| `calendar.check_working_days` | calendar table | Conservative (assume non-working) |
| Pure-logic tools (`validate_*`, `check_*`) | n/a | Input-validation errors as `blocking` issues |

**States:** closed → (5 fails / 30s) → open → (30s) → half-open → (probe) → closed | open

**Health surface:**

- `GET /api/health/breakers` on gateway — all L1 breakers
- Each MCP tool exposes `GET /health` with its L2 breakers in the same shape
- Phoenix span attribute `breaker.state` on every spanned call
- ROI event `success=false`, `error_class=breaker_open` when a breaker drops a call
- Power BI tile: "% of requests with any breaker open in the last hour"
- Alert: any breaker stays open > 5 min during business hours

**Implementation note:** A small breaker library lives in `apps/gateway/circuit/` and is vendored into each MCP tool. Pattern matches the existing ROI client in `apps/gateway/sidecar/_client.py` so the operator has one mental model.

**Rationale:** Lock #7 already commits to two layers; this Lock makes the layout, thresholds, and fallbacks specific enough to implement without re-arguing each one. Pure-logic tools intentionally have no breaker — their failures are input validation errors that surface through the existing `blocking` mechanism.

**Reversal cost:** Medium — operational pattern. Reversing means rewriting fallback paths and the health surface. Tuning thresholds is cheap; restructuring the layout is not.

---

## Lock #19 — `/api/query` is a validator, not a generator

**Decision:** rls-apex-v1 is a validator. Structured intake in (`RlsPayload` via `/api/intake`), critique with citations + rejection-probability score out (via `/api/query`). The LLM grades the user's draft RLS against retrieved procedure / form requirements / cited precedents and emits a cure path. It does NOT write packet prose. No packet artifact exists; therefore no packet footer.

**Implications:**
- `/api/query` response shape is structured critique (rejection probability + blocking gaps + cure-path tokens), not free-form packet text
- TAC-03 refusal contract triggers when retrieval returns zero relevant chunks: "insufficient precedent to grade" — NOT "won't generate"
- TAC-03 sidecar emit uses `event_kind="escalation"` (closest valid kind in EventKind enum) with `extra={"refusal_reason": "no_grounding"}`. `event_kind="refusal"` is NOT in the schema.
- TAC-06 (packet disclaimer footer) is dropped from scope — no packet exists to footer
- TAC-02 banner copy ("does not provide legal advice. does not cite case law.") is the canonical UX hedge across the validator surface
- Plan C retrieval feeds the critique prompt
- Plan D L1-L14 are deterministic validators of the user's intake fields (not of LLM output)

**Rationale:** README §"What this is" already says "grades [an RLS] against procedure / form requirements / cited precedents, and returns a rejection-probability score plus a cure path." Reframe spec (2026-05-08) locked "MCP-first procedural agent." `/api/intake` accepts structured `RlsPayload`, not user paste. Plans A/C/D are coherent with validator framing. The 2026-05-11 tactical work order (TAC-03/06) leaned generator and conflicted with the actual code surfaces, file paths, and schema enum — `event_kind="refusal"` is not in the EventKind enum; `apps/gateway/handlers/generate.py` doesn't exist; no packet-generation prompt or endpoint exists.

**Reversal cost:** Medium — flipping to generator requires (a) a new prompt artifact + packet-generation endpoint, (b) the packet footer surface (TAC-06), (c) the disclaimer-shown response field, (d) a different L1-L14 target (LLM output instead of user intake). The validator-direction code (Plans A/C/D + existing /api/query streaming) does NOT need to be undone first.

---

## Lock #20 — Lineage canonicalization + link algorithm (the legal tamper-evidence anchor)

**Decision:** The RLS lineage chain's tamper-evidence is a **self-specified, normative algorithm** — spec `2026-05-18-rls-persistence-genesis-design.md` §5.1 rules (1)–(6) + §5.2 byte construction — carried under `chain_version` (currently `"1"`). It is **not** RFC 8785 (JCS) and no JCS library may be assumed to reproduce it. Essence: the hashed `payload` is a strict **string-only** object (every value a string; no floats/booleans/nulls/nested; absence = omitted key; ISO-8601-UTC-`Z` timestamps; NFC-normalized strings; `chain_version` always present), serialized as `json.dumps(payload, sort_keys=True, separators=(",",":"), ensure_ascii=False)` UTF-8 (keys ordered by Unicode code point; escaping exactly CPython `json` with `ensure_ascii=False`). The link is `sha256( (prev_hash or "GENESIS").encode("ascii") + b"\x1f" + str(sequence).encode("ascii") + b"\x1f" + canonical_bytes(payload) ).hexdigest()` (lowercase 64-hex). Genesis = `prev_hash=None`, `sequence=1`, sentinel `"GENESIS"`.

**Implications:**
- The algorithm is reproducible by an auditor from the spec/this lock **alone**, without our source and without any external standard — that is the entire point; do not "tidy" it toward JCS or a library.
- `chain_version` is the only sanctioned evolution path. Any change to canonicalization or the link construction is **chain-breaking**: it requires a new `chain_version`, retention of the v1 algorithm for verifying all pre-existing events, and a documented migration — never an in-place edit.
- One shared pure module (`apps/gateway/db/lineage.py`) implements it; **both** `PgRepo` and `_MockRepo` call it, so the DEV path exercises the real chain math (no faked head).
- `verify_chain` (spec §5.3) is the public verification contract: contiguous `1..N` sequences, genesis `prev_hash is None`, each `prev_hash == prior this_hash`, each `compute_link(...) == this_hash`.
- Provenance (`authn`, `actor_id`) lives **inside** the hashed payload: chain integrity proves a tamper-evident record of the *asserted* (not authenticated) actor — integrity ≠ identity assurance.

**Alternatives considered:**
- **RFC 8785 / JCS** — rejected: we do not implement JCS; adopting the *claim* without the implementation is a false-conformance defect (the original spec defect that triggered this lock). A conforming library would add a supply-chain dependency requiring county review, and JCS's UTF-16 code-unit key ordering + distinct escaping table differ from stdlib `json`, so "use a JCS lib" would *not* reproduce our bytes anyway.
- **CBOR / protobuf canonical form** — rejected: byte-opaque to a non-engineer auditor; the value here is that a records/legal reviewer can recompute from a written rule.
- **No canonicalization (hash raw request bytes)** — rejected: non-deterministic across clients/serializers; unverifiable.
- **Per-field concatenation without JSON** — rejected: reinvents escaping/ordering with more edge cases than a constrained JSON profile.

**Rationale:** A legal tamper-evidence anchor must be independently recomputable years later from a written specification, by someone who does not have (or trust) our codebase. Constraining the payload to strings-only sidesteps JSON's only hard canonicalization problem (number forms) and makes the documented profile genuinely sufficient. No runtime dependency keeps it inside county supply-chain governance. `chain_version` gives forward evolvability without ever silently invalidating prior chains.

**Reversal cost:** **Very high — effectively irreversible once a single real chain exists.** Any change to §5.1/§5.2 retroactively breaks `verify_chain` for every prior `lineage_event`. The only forward-safe path is a new `chain_version` that keeps the v1 algorithm available for historical verification in perpetuity. This irreversibility is precisely why this lock is a **precondition to `writing-plans`**, authored and accepted as part of P1 design sign-off rather than deferred into the implementation plan.


---

## Lock #21 — RLS genesis at explicit Submit (not at intake)

**Decision:** A durable `rls` row + genesis `lineage_event` is created ONLY at explicit Submit (after validate, `blocking==0`), never at `/api/intake`. Drafts stay client-side until Submit.

**Rationale:** Lock #19 privileged-matter hygiene — every half-typed exploratory legal question persisted as a durable privileged row is an ACL/records-retention liability. Intake/validate stay stateless (spec §1/§3).

**Reversal cost:** Low — adding draft autosave later is additive; no chain rewrite.

---

## Lock #22 — `DEV_AUTH_BYPASS` selects the persistence backend

**Decision:** `get_repo` resolves per-request: `DEV_AUTH_BYPASS=="1"` OR no `app.state.db_pool` → `MockRepo`; else `PgRepo`. Auth-bypass and store-choice are deliberately fused on one pilot flag.

**Rationale:** Keeps the no-DB DEV click-through working (standing pilot pattern) without a second flag. Accepted limitation: no real-auth+mock-DB or bypass-auth+real-DB combination (spec §4).

**Reversal cost:** Low — splitting into two env flags later is mechanical.

---

## Lock #23 — Per-year `id_counter` row over a sequence

**Decision:** `rls_id` (`RLS-YY-NNNN`) is allocated from a per-year `id_counter` row via atomic `INSERT … ON CONFLICT (year) DO UPDATE … RETURNING` inside the genesis tx. Calendar year (UTC).

**Rationale:** Contiguous, gap-free official legal numbering (a rolled-back genesis consumes no number); a Postgres SEQUENCE leaks numbers on rollback. Single-row-lock scaling limit (~≤1 submit/s) documented in spec §13 — acceptable at county intake volume.

**Reversal cost:** Medium — moving to hi-lo/sequence allocation later changes the numbering guarantee; needs a documented transition.

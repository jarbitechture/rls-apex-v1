# Stack

The full server + LLM canon for RLS Apex v1. One page, table-driven, no prose padding.
For *system shape* see [`ARCHITECTURE.md`](./ARCHITECTURE.md). For *why* each choice was locked see [`DECISION_LOG.md`](./DECISION_LOG.md). For *operations* see [`RUNBOOK.md`](./RUNBOOK.md).

## Hosts

| Host | Hardware / OS | Role | Inbound from |
|---|---|---|---|
| `bcc-ap-llm01` | Win 2025 (gateway via Hyper-V Linux VM or future Linux app host) | FastAPI gateway, 6 MCP tools (loopback), ADO build agent | `rls.mymanatee.org:443` |
| `bcc-db-llm01` | RHEL | Postgres 16 + pgvector + **AGE** + MinIO + Phoenix backend | `bcc-ap-llm01` only |
| `bcc-ap-infer01` | RHEL 10, NVIDIA L4 24GB (CC 8.9) | SGLang + Qwen2.5-14B-Instruct-FP8 | `bcc-ap-llm01` only |

All three on the county AD LAN. No DMZ, no public IP. OpenAI egress is allowlist-gated and **disabled by default** in v0.1.0 (Lock #4 fallback path only).

## The seven layers

| Layer | Choice | Runner-up | Why locked |
|---|---|---|---|
| L1 — UI | **assistant-ui** (React component library) on top of the cookbook-gov fork. Tokens: `_base.css` + empty `_brand-overlay.css` (Lock #11). | Hand-rolled React | Production-grade chat surface with native streaming + first-class citation rendering. Replaces the prototype's hand-rolled chat. |
| L2 — Gateway | FastAPI on `bcc-ap-llm01`, MSAL OIDC, governed proxy from `manatee-civic-ai`, ROI sidecar emit on every action (Rule #18). Two-layer circuit breakers (Rule #19). | Express/Node | Reuses proven civic-ai breaker pattern; Python keeps DSPy/MCP in-process. |
| L3 — Orchestration | **DSPy + GEPA** (multi-objective Genetic-Pareto optimizer). Four signatures: `PolicyMatcher` → `PrecedentRetriever` → `ComplianceGrader` → `Reviser`, plus a one-pass critic. **Compiled in weeks 5–6** against ≥50 attorney redlines (Lock #8). MIPROv2 is the documented fallback if installed `dspy.teleprompt` lacks GEPA. | LangGraph | GEPA optimizes (faithfulness × cycle-time × rejection-rate) jointly; MIPROv2 only optimizes the metric you hand it. |
| L4 — Inference | **SGLang** serving **`Qwen2.5-14B-Instruct-FP8`** on `bcc-ap-infer01`. Optional upgrade path: **`Qwen3-30B-A3B`** (MoE, 30B total / 3B active, FP8) **if L4 VRAM headroom permits**. Cheap-tier fallback: **Ollama `llama3.1:8b`** for simple classification. Cold-start fallback only: OpenAI `gpt-4o-mini`, allowlist-gated, disabled by default. | vLLM | SGLang's structured output + radix cache is materially better for agent tool calling. FP8 fits L4 24GB. |
| L5 — Retrieval | **BM25 lexical + LightRAG (HKUDS, MIT) + Contextual Retrieval preprocessing**. Contextualizer = local **Qwen3** call (not the closed Anthropic prompt-cache feature, not the Anthropic API). Dense embeddings via **Qwen3-Embedding** on infer01. pgvector on Postgres for vectors; AGE on the same Postgres for the policy graph. | Microsoft GraphRAG; dense-only naive RAG | LightRAG is cheaper and self-managed; Contextual Retrieval gives ~49% retrieval-failure-reduction on chunk-level recall — both with zero Anthropic-API spend. |
| L6 — Data plane | Postgres 16 + AGE + MinIO on `bcc-db-llm01`. Azure Key Vault (`kv-bcc-rls-prod`) for secrets, 90-day rotation, gMSA on Windows hosts. OnBase connector for existing legal docs. | Azure Database for PostgreSQL Flexible Server | AGE is self-managed only — the managed PG flavor doesn't support it. Co-location with retrieval saves 10–80ms per round-trip. |
| L7 — Observability + Eval | OpenTelemetry → **Phoenix** (Arize OSS, per-trace UI, on `bcc-db-llm01`) + **Power BI** (exec/renewal narrative, pulls from ROI JSONL via Gateway) + **promptfoo** (CI prompt regression, day 1) + **Inspect AI** (correctness/safety, week 4+) + **`manatee_ai_roi`** sidecar (per-action telemetry, Rule #18). | PostHog | PostHog's only novel capability is session replay; replay on a privileged-matter tool is its own governance decision. Re-evaluate week 6 only if a specific gap surfaces. |

## MCP tools (Lock #7)

Each = systemd unit `mcp-tool@<name>.service`. **FastMCP 2.0**, HTTP loopback, **RS256 JWT** with 60-second TTL, per-tool Key Vault scope, two-layer circuit breakers.

| Port | Tool | Backend | Owns |
|---|---|---|---|
| 30100 | `retrieve` | Postgres+pgvector, AGE | BM25 + LightRAG + Contextual Retrieval fan-out |
| 30101 | `policy-graph` | AGE | Cypher (`findStatutes`, `cited_by`, `preempts`) |
| 30102 | `ontology` | `domain.yaml` | Validates entities/edges before write |
| 30103 | `lineage` | Postgres | Hash-chain audit writer (T→M divergence) |
| 30104 | `docs` | MinIO | Per-matter ACL, classification-aware |
| 30105 | `report-roi` | local JSONL → Power BI Gateway pull | `manatee_ai_roi.schema` events |

After L2–L5 stabilize, this set wraps as the **County Pilot MCP** — the same six tools become the reusable substrate for Permit pre-screen, HR policy Q&A, Budget memo drafter, and the next N county pilots. Don't extract before RLS works end-to-end with mocks.

## Day-1 bolt-ons

Four items ship in v0.1.0 because RLS Apex v1 is the **template** every future county pilot inherits:

1. **GEPA** — replaces MIPROv2 as the optimizer. Verify presence in `dspy.teleprompt` at scaffold time; document MIPROv2 fallback if absent.
2. **Contextual Retrieval preprocessing** — Qwen3-driven, no Anthropic API call, no closed prompt-cache dependency.
3. **assistant-ui** — replaces hand-rolled React chat. Citation rendering is first-class.
4. **promptfoo** — CI prompt regression from commit 1, gates merges.

## Not in scope (and why)

| Excluded | Reason |
|---|---|
| Pydantic AI | Would replace DSPy; wrong tradeoff for an optimizer-driven legal pipeline. |
| Microsoft GraphRAG | Cost + complexity vs LightRAG; no signal it beats LightRAG on this corpus. |
| Hatchet / Inngest (durable workflows) | RLS is request/response with SSE streaming; durable workflow engines solve a problem we don't have. |
| Letta / MemGPT | RLS is stateless validation per query; agent memory is the wrong tool. |
| PostHog | See L7 row above. |
| RunPod (in v0.1.0) | All inference on infer01; RunPod is reserved for batch GEPA offload if a single host can't optimize in a 6-hour window. |

## Track A ↔ Track B intersection

| Track | Path | Owns |
|---|---|---|
| A — `manatee-ai-roi` | `~/Projects/manatee-ai-roi/` | The ROI sidecar SDK, JSONL schema, Power BI dataset spec. Imported as a dependency by every county AI project per Rule #18. |
| B — RLS Apex v1 | `~/Projects/rls-apex-v1/` | The pilot. Imports `manatee_ai_roi`, emits one event per action, exposes `/health/sidecar` on the gateway. |

The two tracks intersect at the Power BI dashboard only. RLS does not vendor or fork the sidecar — it imports the package. ROI schema is the contract.

## Network ACLs

| Source | Destination | Notes |
|---|---|---|
| Browser | `rls.mymanatee.org:443` | New hostname (ITS request day 1, slow path) |
| `bcc-ap-llm01` (gateway only) | `bcc-ap-llm01:30100–30105` (loopback) | Six MCP tools |
| `bcc-ap-llm01` | `bcc-db-llm01:5432` | Postgres + AGE |
| `bcc-ap-llm01` + `bcc-ap-infer01` | `bcc-db-llm01:9000` | MinIO |
| `bcc-ap-llm01` | `bcc-ap-infer01:8000` | SGLang OpenAI-compatible REST |
| `bcc-ap-llm01` (allowlist) | `api.openai.com` | Disabled by default in v0.1.0 |

## Readiness — when this is usable

| Milestone | Date | Capability | Hard gate |
|---|---|---|---|
| v0.1.0 scaffold | 2026-05-05 | Repo + scaffold; nothing runs end-to-end | (shipped) |
| Internal click-through (you + Drew) | 2026-05-12 (week 1) | assistant-ui shell, mock retriever returning canned 3-doc result, citation rendering, accept/reject wired to no-op | None — author-owned |
| Stakeholder demo | 2026-05-19 (week 2) | Real BM25 + LightRAG retrieval over the redacted 50-opinion corpus, real DSPy chain (uncompiled), SSE streaming, ROI events firing, Phoenix traces | County Attorney redacted corpus · Carlos egress + intake sign-off · `rls.mymanatee.org` provisioned · Qwen2.5-14B-FP8 running on infer01 (currently 7B for cookbook) · AGE installed on `bcc-db-llm01` |
| Real RLS triage | mid-June (weeks 5–6) | GEPA-compiled chain + Reviser; production traffic on a fenced pilot group | 50–100 attorney redlines from weeks 2–4 (Lock #8) |
| Reviser + matter-draft surface | post-pilot | M-surface at `/matters/<id>/drafts/*`, T→M lineage stamping, per-matter ACLs | Reviser proven |

## Hard rules (non-negotiable)

1. **Residency binds.** No county data crosses the LAN boundary. PostHog Cloud out, Azure managed PG out for stateful data, RunPod for state out.
2. **Governance is foundation.** Frontmatter on every skill. Every MCP tool gets s2s auth. Every LLM call carries a lineage hash. Audit rows are written before the user sees output.
3. **No optimization without evidence.** GEPA waits for attorney redlines. The smoke eval is plumbing, never a quality signal — see [`eval/smoke/README.md`](./eval/smoke/README.md).
4. **Cookbook is not RLS.** No shared edge, no shared hostname, no shared auth chain. RLS gets its own everything.

# RLS Apex v1

**Pre-submission AI validator for Manatee County Requests for Legal Services.** A county staffer pastes a draft RLS, the agent grades it against the procedure / form requirements / cited precedents, and returns a rejection-probability score plus a cure path. That's the whole pilot. Everything else (dashboard, lists, reviewer surfaces) is supporting context for that one flow.

## Status

Proof of Concept. Not for production deployment.

Production track (v0.3+) is gated on:
- PM assignment
- Security review signoff
- Infrastructure signoff (GPU strategy, deployment topology)

> **Status:** v0.1.0 scaffold. Gateway + retrieval + agent dispatcher are real and wired. The LLM call itself is mocked behind a multi-provider seam (`LLM_PROVIDER=ollama|sglang|openai|mock`) — flip it on when SGLang lands on `bcc-ap-infer01`.

## What this is

```
Surface     React UI (lifts prototype) · Entra ID OIDC · Static Web App
Harness     Claude Agent SDK pattern — agents = system prompt + skills + tool allowlist
Tools       MCP servers (FastMCP 2.0, separate processes, RS256 JWT, loopback)
Skills      ./skills/templates/*.md  — versioned in git, hot-loaded
Optimizer   DSPy + GEPA (offline batch, weeks 5–6, gated on attorney redlines)
Inference   SGLang + Qwen2.5-FP8 on bcc-ap-infer01 (county LAN)
State       bcc-db-llm01 — Postgres+pgvector+AGE + MinIO
Observ.     Phoenix + Power BI + promptfoo + Inspect AI + manatee_ai_roi sidecar
```

## First-time reader path

1. [`DECISION_LOG.md`](./DECISION_LOG.md) — every locked decision and its rationale
2. [`ARCHITECTURE.md`](./ARCHITECTURE.md) — the rings, where they run, how they call each other
3. [`RUNBOOK.md`](./RUNBOOK.md) — boot order, healthchecks, recovery
4. [`domain.yaml`](./domain.yaml) — single source of truth for entities, relations, constraints

## Users

- **Records clerk** — high-volume intake (records desk staff). Primary persona.
- **Department specialist** — occasional edge-case intake from operating departments.
- **IT power user** — rare complex multi-source search; admin endpoints.

## Layout

```
rls-apex-v1/
├── README.md                     ← you are here
├── ARCHITECTURE.md
├── DECISION_LOG.md
├── RUNBOOK.md
├── domain.yaml                   single source → Pydantic + Alembic + MCP schemas
├── apps/
│   ├── web/                      React UI rewired to gateway via SSE
│   └── gateway/                  FastAPI · MSAL OIDC · Phoenix instr · MCP host · ROI sidecar
├── mcp-tools/                    Each = systemd unit, FastMCP 2.0, RS256 JWT, loopback
│   ├── retrieve/                 BM25 + LightRAG + Contextual Retrieval (pgvector + AGE)
│   ├── policy-graph/             AGE Cypher
│   ├── ontology/                 domain.yaml validation
│   ├── lineage/                  hash-chain audit writer
│   ├── docs/                     MinIO read/write, per-matter ACL
│   └── report-roi/               manatee_ai_roi.schema event emitter (Rule #18)
├── skills/
│   └── templates/                T-skills, frontmatter governed, PR-on-edit
├── agents/
│   └── precedent-retriever/      DSPy signatures + chain (uncompiled in v0.1.0)
├── eval/
│   ├── datasets/rls-v1/          .gitignored — pulled from county records, redacted
│   ├── smoke/smoke_eval_DO_NOT_OPTIMIZE_AGAINST.jsonl
│   ├── promptfoo/                CI smoke set
│   └── inspect-ai/               full-trace agent eval
├── infra/
│   ├── systemd/mcp-tool@.service
│   ├── azure/main.bicep          Static Web App, Key Vault, Entra app reg
│   ├── github/                   Actions workflows
│   └── bcc-db-llm01/             AGE install + MinIO unit + firewalld
├── codegen/                      domain.yaml → Pydantic + Alembic + MCP schemas
└── index.html                    browseable scaffold map (open in browser)
```

## Two-week target (Lock #9)

| End of week | Deliverable | Audience |
|---|---|---|
| 1 | assistant-ui shell + mock PrecedentRetriever returning canned 3-doc result + citation rendering + accept/reject UI wired to no-op | Internal (you + Drew) |
| 2 | Same shell, real BM25+LightRAG over redacted 50-opinion corpus, real DSPy chain (uncompiled), end-to-end SSE streaming, ROI events firing | Stakeholder demo |

GEPA compile and Reviser are post-pilot (weeks 5–6). Matter-draft UI surface is post-Reviser. See [DECISION_LOG.md](./DECISION_LOG.md) Lock #10.

## Hard constraints (do not negotiate)

- **Residency binds.** No prompts, embeddings, or document content cross the county boundary. OpenAI fallback is allowlisted egress only and disabled by default in v0.1.0.
- **Governance is foundation.** Per-matter ACL, audit rows, lineage hashes, classification at intake — all built in, not bolted on.
- **No optimization against synthetic signal.** GEPA waits for attorney redlines. The smoke eval is plumbing, not quality.

## Non-goals for v0.1.0

- Matter-draft UI surface (deferred — `M` route returns 501 with `Retry-After`)
- GEPA compile (deferred — scaffold ready, no real run)
- Reviser, ComplianceGrader, PolicyMatcher (weeks 3–6)
- PostHog (out — re-evaluate at week 6)
- RunPod (out — inference stays on `bcc-ap-infer01`)

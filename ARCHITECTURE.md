# Architecture

Five concentric rings, each swappable. Today wired against OpenAI fallback only for cold-start; tomorrow flipped to SGLang + Qwen on `bcc-ap-infer01` with one env var.

```
┌──────────────────────────────────────────────────────────────────┐
│  5. UI            React app (lifts prototype) · Entra ID OIDC    │
│  4. Agent runtime DSPy modules · lineage · guardrails            │
│  3. Inference     Gateway router → SGLang/Qwen | OpenAI fallback │
│  2. Knowledge     pgvector + AGE + ontology (domain.yaml)        │
│  1. Substrate     Postgres + MinIO + Phoenix + ROI sidecar       │
└──────────────────────────────────────────────────────────────────┘
```

## Hosts

| Host | OS | Role |
|---|---|---|
| `bcc-ap-llm01` | Win 2025 | Gateway (FastAPI in Hyper-V Linux VM, or directly on a future Linux app host), MCP tools, ADO agent |
| `bcc-db-llm01` | RHEL | Postgres + pgvector + **AGE**, MinIO, Phoenix backend |
| `bcc-ap-infer01` | RHEL 10, L4 24GB | SGLang + Qwen2.5-FP8 |

All three sit on the county AD LAN. No DMZ, no public IP. ACLs:
- `rls.mymanatee.org` (new) → `bcc-ap-llm01:443`
- `bcc-ap-llm01:30100–30105` ← gateway only (loopback)
- `bcc-db-llm01:5432` ← `bcc-ap-llm01` only
- `bcc-db-llm01:9000` (MinIO) ← `bcc-ap-llm01` + `bcc-ap-infer01`
- `bcc-ap-infer01:8000` (SGLang) ← `bcc-ap-llm01` only
- OpenAI egress ← county proxy with allowlist on `api.openai.com`, **disabled by default in v0.1.0**

## Request flow — PrecedentRetriever (week 2 target)

```
┌────────────┐    ┌─────────────┐    ┌─────────────────┐    ┌────────────┐
│ React UI   │ ─▶ │ FastAPI     │ ─▶ │ DSPy chain      │ ─▶ │ MCP        │
│ assistant- │ ◀─ │ gateway     │ ◀─ │ (uncompiled)    │ ◀─ │ retrieve   │
│ ui         │    │ + MSAL OIDC │    │                 │    │ (loopback) │
└────────────┘    └─────────────┘    └─────────────────┘    └────────────┘
                       │   │                  │                    │
                       │   ▼                  ▼                    ▼
                       │  ROI sidecar    SGLang/Qwen          Postgres + AGE
                       │  → manatee_ai   on infer01           + MinIO on db-llm01
                       │  _roi.jsonl
                       ▼
                    Phoenix traces
```

Every gateway request:
1. MSAL verifies Entra ID JWT (`Authorization: Bearer ...`)
2. Group claim mapped to role (`attorney`, `paralegal`, `general-counsel`, `admin`)
3. Lineage hash stamped (`ln-<sha>` — content-derived but salted)
4. DSPy chain runs — calls `mcp.retrieve` → `mcp.policy-graph` → SGLang for synthesis (week 2)
5. Phoenix span emitted per LLM call
6. After successful action, `mcp.report-roi` emits one event per the `manatee_ai_roi.schema`
7. SSE-streamed back to UI with citations rendered as first-class entities

## MCP tools (Lock #7)

Each = systemd unit `mcp-tool@<name>.service`. FastMCP 2.0, HTTP loopback, RS256 JWT bearer auth, per-tool Key Vault secrets, two-layer circuit breakers.

| Port | Tool | Backends | Notes |
|---|---|---|---|
| 30100 | `retrieve` | Postgres+pgvector, AGE | BM25 + LightRAG + Contextual Retrieval fan-out |
| 30101 | `policy-graph` | AGE | Cypher (`findStatutes`, `cited_by`, `preempts`) |
| 30102 | `ontology` | `domain.yaml` | Validates entities/edges before write |
| 30103 | `lineage` | Postgres | Hash-chain audit writer (T→M divergence) |
| 30104 | `docs` | MinIO | Per-matter ACL, classification-aware |
| 30105 | `report-roi` | local JSONL → Power BI Gateway pull | `manatee_ai_roi.schema` events |

## Guardrails (non-negotiable)

1. **No legal advice.** Classifier on every output blocks if it crosses the line.
2. **Citations required.** Any factual claim carries a vector or graph hit.
3. **Lineage stamped.** Nothing reaches the UI without an `ln-…` ID.
4. **Classification gate.** `mcp.docs` refuses to surface `privileged` content to roles below `attorney`.

## Observability stack (Lock #1)

| Concern | Tool | Where |
|---|---|---|
| Per-LLM-call traces | Phoenix | `bcc-db-llm01` |
| Exec/renewal narrative | Power BI | County tenant, pulls from sidecar JSONL via Gateway |
| Prompt regression in CI | promptfoo | GitHub Actions |
| Correctness/safety eval | Inspect AI | Nightly on `bcc-ap-llm01` |
| Per-action telemetry | `manatee_ai_roi` sidecar | Gateway emits to local JSONL |

The sidecar event schema lives in [`apps/gateway/manatee_ai_roi.schema.json`](./apps/gateway/manatee_ai_roi.schema.json) and is **the** ROI surface — no other event shape leaves the gateway.

## What's deferred (and why)

| Deferred to | Item | Gating condition |
|---|---|---|
| Weeks 3–4 | PolicyMatcher + ComplianceGrader | PrecedentRetriever proves the chain |
| Weeks 5–6 | Reviser, GEPA compile, full Power BI dashboard, pilot onboarding | First 50–100 attorney redlines |
| Post-pilot | Matter-draft UI surface (`/matters/<id>/drafts/*`) | Reviser real |
| Post-pilot | `mcp.report-roi` demoted to in-process | If gateway is the only emitter |
| Post-pilot | RunPod offload for batch GEPA | When a single host can't run optimization in a 6-hour window |
| Re-evaluate week 6 | PostHog | Specific gap (session replay, feature flags, experiments) surfaces |

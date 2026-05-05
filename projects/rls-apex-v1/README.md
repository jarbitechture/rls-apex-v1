# RLS Apex v1

Manatee County **Request for Legal Services** AI pilot.

> **Status:** v0.1.0 scaffold — bones only. No code generates against assumptions
> until [`domain.yaml`](./domain.yaml) is locked.

## Quick links

- [ARCHITECTURE.md](./ARCHITECTURE.md) — five rings, hosts, deploy
- [DECISION_LOG.md](./DECISION_LOG.md) — 15 locks from session 2026-05
- [domain.yaml](./domain.yaml) — single source of truth (entities, graph, access)
- [RUNBOOK.md](./RUNBOOK.md) — day-2 ops on `bcc-db-llm01` + gateway

## v0.1.0 deliverable

PrecedentRetriever end-to-end in 2 weeks:
1. Attorney signs in via Entra ID at `rls.mymanatee.org`.
2. Asks "find prior opinions citing §163.31801".
3. Gateway routes through DSPy `PrecedentRetriever` → `retrieve` MCP tool → SGLang/Qwen on `bcc-ap-infer01`.
4. Returns 3-doc result with typed `Citation` provenance + lineage hash.
5. ROI event fires to `manatee_ai_roi` sidecar.

Internal click-through end of week 1 (you + Drew). Stakeholder demo end of week 2.

## Layout

```
apps/web/              React UI (lifts prototype, rewires to gateway via SSE)
apps/gateway/          FastAPI · MSAL OIDC · ROI sidecar · MCP host · Phoenix
mcp-tools/             FastMCP 2.0 servers, one per capability, separate systemd units
skills/templates/      Template skills, frontmatter governed, PR-on-edit
agents/                DSPy modules (uncompiled in v0.1.0)
eval/                  promptfoo + Inspect AI + smoke_eval (DO NOT OPTIMIZE AGAINST)
infra/                 systemd, Bicep (Entra app reg, KV), GitHub Actions
domain.yaml            single source → Pydantic + Alembic + MCP schemas
```

## Out of scope for v0.1.0

RunPod · PostHog · Matter-draft skills · GEPA compile · PolicyMatcher / ComplianceGrader / Reviser · Permit / HRQA pilots.

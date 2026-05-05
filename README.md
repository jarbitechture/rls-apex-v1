# RLS Apex v1

**Manatee County BCC — Request for Legal Services pilot.**
Production scaffold for the agent-driven RLS workflow. Independent of the cookbook project at `mcgpt.mymanatee.org` — learns its patterns, doesn't share its infrastructure.

This project is the **production scaffold**. The interaction-design prototype it descends from lives separately and remains the reference for UI shape only.

## Status

`v0.1.0` — scaffold phase. No production traffic. See `DECISION_LOG.md` for the locked decisions that shaped this layout, and `ARCHITECTURE.md` for the runtime shape.

## Two-week target

PrecedentRetriever end-to-end against the redacted RLS-v1 corpus, served through assistant-ui, instrumented with Phoenix + the manatee_ai_roi sidecar, gated by Entra ID OIDC.

Internal click-through (you + Drew) at end of week 1. No external stakeholder demo until end of week 2.

## What's here

```
apps/web/                React UI (lifts the prototype, rewires to gateway via SSE)
apps/gateway/            FastAPI · MSAL OIDC · ROI sidecar · MCP host · Phoenix
mcp-tools/               Each = systemd unit, FastMCP 2.0, RS256 JWT, loopback
  retrieve/              BM25 + LightRAG + Contextual Retrieval
  policy-graph/          AGE Cypher
  ontology/              domain.yaml validation
  lineage/               hash-chain audit writer
  docs/                  MinIO read/write, per-matter ACL
  report-roi/            manatee_ai_roi emitter (Rule #18)
skills/templates/        T-skills, frontmatter governed, PR-on-edit
agents/precedent-retriever/   DSPy signatures + chain (uncompiled)
eval/                    promptfoo + Inspect AI + smoke set
domain.yaml              single source → Pydantic + Alembic + MCP schemas
infra/                   systemd, Azure Bicep, GitHub Actions, bcc-db-llm01 install
```

## Hard rules

1. **Residency binds.** No county data crosses the LAN boundary. PostHog Cloud out, Azure managed PG out for stateful data, RunPod for state out.
2. **Governance is foundation.** Frontmatter on every skill. Every MCP tool gets s2s auth. Every LLM call carries a lineage hash. Audit rows are written before the user sees output.
3. **No optimization without evidence.** GEPA waits for attorney redlines. The smoke eval is plumbing, never a quality signal — see `eval/smoke/README.md`.
4. **Cookbook is not RLS.** No shared edge, no shared hostname, no shared auth chain. RLS gets its own everything.

## Getting started

Not yet runnable end-to-end. See `RUNBOOK.md` for the bring-up sequence as it lands.

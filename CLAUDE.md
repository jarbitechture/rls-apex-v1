# RLS Apex v1 — Claude Context

> **DORMANT/dead per user (2026-06-29).** Do not resume work here without explicit user direction; sections below describe the state at pause.

Pre-submission AI validator for Manatee County RLS. MCP-first procedural agent
(LLM orchestrator + RLS-domain tools + boring official UI). County-governed,
legal-liability surface — treat decisions as load-bearing.

## Active branch
`feat/v0.2.0a-backend` (NOT main). GitHub `origin` only — no Azure DevOps remote.
Commit + push every phase boundary.

## Commands
- Backend tests: `python -m pytest -q`   (currently 261 green)
- Frontend tests: `cd apps/web && npx vitest run`   (currently 65 green)
- Never claim done without running these (verification-before-completion).

## Where decisions live (READ before designing — do not re-derive)
- `DECISION_LOG.md` — Locks #1–#19 + ADRs (authoritative; Lock #18 breaker,
  Lock #19 legal-liability, ADR-006 in-process-library topology)
- `docs/superpowers/specs/` — design specs;  `docs/runbooks/` — deploy/runbooks

## Gotchas (each cost a prior session)
- **pytest discovery:** never add `tests/<subdir>/__init__.py` — shadows real
  top-level packages.
- **`DEV_AUTH_BYPASS=1`** gates BOTH auth-skip AND (per P1 spec) the
  in-memory persistence backend. Real auth is 501 — pilot runs on bypass.
- **Lit tests:** Vitest env MUST be `jsdom`, not happy-dom (happy-dom escapes
  `.map(html``)` directive markers).
- **Breakers:** every cross-process dep wraps a breaker; write tools
  (`update_rls_status`) = **fail-loud**, reads = empty+flag (Lock #18).
- **ROI (Rule #18):** every user-facing action + tool invocation emits a
  schema-valid ROI event; `RoiClient` takes the sidecar BASE url (it appends
  `/v1/events` — do not pass an `/events`-suffixed endpoint).
- **Lifespan ordering:** the DB pool is created in the FastAPI lifespan, not
  at import — resolve pool-dependent state per-request, never at module load.
- **Servo can't verify ≥1024px layout on Retina** — use Playwright geometry.

## Status
v0.2.1a-rc2 tagged. P1 (RLS persistence + lineage genesis) spec written +
architecture-reviewed (`docs/superpowers/specs/2026-05-18-rls-persistence-genesis-design.md`);
P2 (CAO decision-write) decisions captured in that spec §11. README §Status
may lag — trust DECISION_LOG + specs over README.

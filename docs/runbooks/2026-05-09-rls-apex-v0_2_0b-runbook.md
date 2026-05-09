# RLS Apex v0.2.0b — Operational Runbook

**Created:** 2026-05-09 (covers session work May 8–9, 2026)
**Branch shipped:** `feat/v0.2.0a-backend` at HEAD `577232d` on GitHub `origin`
**Status:** v0.2.0a backend + v0.2.0b backend ROI fixes + v0.2.0b frontend (all 24 plan tasks) all green.

---

## 1. What's in the box

### 1.1 Test gates (all green)

| Layer | Tool | Count | How to run |
|---|---|---|---|
| Backend | pytest | 64 / 64 | `.venv/bin/python -m pytest -q` |
| Frontend unit | Vitest + jsdom | 50 / 50 | `cd apps/web && npm test` |
| E2E browser | Playwright + Chromium | 2 / 2 | `cd apps/web && npm run test:e2e` |
| Visual regression | Servo screenshots | 7 / 7 | `cd apps/web && BASE_URL=http://127.0.0.1:8090 bash tests/visual/run.sh` |

### 1.2 What ships in `feat/v0.2.0a-backend`

**Backend (gateway, Python/FastAPI):**

- v0.2.0a backend MCP-first agent runtime (intake, validate, query, agent endpoints) — pytest harness, Pydantic+Alembic+asyncpg pool, circuit breaker library w/ single-probe enforcement, MCP framework + 3 tools (validate real, classify+extract mocks), 3 gateway endpoints, E2E smoke
- v0.2.0b backend ROI emit cleanup — every `emit_roi` call site (gateway endpoints + 3 MCP tool servers) now satisfies the `validate_event_for_persistence` schema gate per Operating Rule #18; pre-flight guard added; non-schema `ts` field removed; `success=False` on tool exceptions
- New `GET /api/cao/brief?rlsId=` (canned 3-bullet brief, full Rule #18 emit)
- New `GET /cao/{rls_id}` SPA catch-all serving index.html
- DEV-mode static mounts at `/static` (apps/web/static) + `/styles` (apps/web/styles) + root `/` (index.html via html=True)

**Frontend (apps/web/, Lit 3.2.1, vanilla JS, no build):**

- 9 Lit components: `<rls-shell>`, `<app-header>`, `<step-bar>`, `<intake-panel>`, `<form-panel>`, `<status-panel>`, `<cure-path-panel>`, `<submit-panel>`, `<copilot-feed>`, `<cao-view>`
- 4 core modules: `store.js` (4-slice observable store), `persist.js` (localStorage namespaced by upn + schemaVersion), `api.js` (typed wrappers), `router.js` (HTML5 history + hash steps)
- 3 single-responsibility automation modules under `core/automation/`: `validator-runner.js` (debounced + AbortController + cascade-suppression hash), `auto-correct.js` (3 rules: subject-trim, title-case, date-infer), `smart-surface.js` (blur-gated error rendering)
- Lit vendored at `static/lib/lit-3.2.1.min.js` (esm.sh build)
- Pre-existing Manatee teal tokens at `apps/web/styles/tokens/_base.css` + `_brand-overlay.css` (oklch color space)
- 17 Vitest unit test files + 2 Playwright E2E specs + Servo visual harness with 7 baselines

---

## 2. How to run locally

### 2.1 Backend tests

```bash
cd /Users/ejarbe/Projects/rls-apex-v1
.venv/bin/python -m pytest -q
```

Expected: `64 passed`. If a clean install is needed first: `python3.12 -m venv .venv2 && .venv2/bin/pip install -r apps/gateway/requirements.txt`.

### 2.2 Dev gateway (foreground)

```bash
cd /Users/ejarbe/Projects/rls-apex-v1
DEV_AUTH_BYPASS=1 .venv/bin/python -m uvicorn apps.gateway.main:app --host 127.0.0.1 --port 8090 --reload
```

Open `http://127.0.0.1:8090/` in a browser. Note: **port 8080 conflicts with Docker Desktop** on the dev workstation — use 8090 (or any free port). Port 8080 is hardcoded in some plan-era docs but the Playwright config and harness both use 8090 now.

### 2.3 Frontend unit tests

```bash
cd /Users/ejarbe/Projects/rls-apex-v1/apps/web
npm install   # first time only
npm test
```

Expected: `50 passed`. Test environment is jsdom (NOT happy-dom — see §4.1).

### 2.4 Playwright E2E

```bash
cd /Users/ejarbe/Projects/rls-apex-v1/apps/web
npx playwright install chromium   # first time only
npm run test:e2e
```

Expected: `2 passed`. Playwright's `webServer` block starts the gateway on 8090 with `DEV_AUTH_BYPASS=1`.

### 2.5 Servo visual baselines

```bash
# Terminal 1: gateway
cd /Users/ejarbe/Projects/rls-apex-v1
DEV_AUTH_BYPASS=1 .venv/bin/python -m uvicorn apps.gateway.main:app --host 127.0.0.1 --port 8090

# Terminal 2: visual harness
cd /Users/ejarbe/Projects/rls-apex-v1/apps/web
BASE_URL=http://127.0.0.1:8090 bash tests/visual/run.sh             # compare against baseline
BASE_URL=http://127.0.0.1:8090 bash tests/visual/run.sh --update    # write new baseline
```

Servo binary expected at `~/Projects/servo/target/release/servoshell`. Override with `SERVO=/path/to/servoshell`.

---

## 3. Architecture quick-reference

### 3.1 Frontend component graph

```
<rls-shell> (root, hydrates store from localStorage on mount)
├── <app-header>       (Manatee logo, role dropdown, banner row)
├── <step-bar>         (5 steps, click to navigate)
├── main panel (router outlet, switches by store.session.currentStep):
│   ├── <intake-panel>      (#step=intake — free-text + paste-skip toggle)
│   ├── <form-panel>        (#step=form — editable fields, inline lint, autocorrect chips)
│   ├── <status-panel>      (#step=status — narrative + blocking/warnings)
│   ├── <cure-path-panel>   (#step=cure — steps render, mark-done disabled)
│   └── <submit-panel>      (#step=submit — disabled stub + JSON copy escape hatch)
├── <copilot-feed>     (subscribes to session.eventLog, capped 200)
└── <cao-view>         (mounted only when path matches /cao/:rlsId)
```

### 3.2 Store slices (single observable, sliced subscriptions)

```js
store.draft        // PERSISTED to localStorage — rlsPayload + classification + cureSteps + blocking + warnings + lastValidated
store.session      // in-memory — currentStep + eventLog + role + upn
store.ui           // ephemeral — blurredFields + autocorrectSuggestions + pendingValidation + validatorAbortController
store.errorState   // cleared on success — breakerStatus + validatorFailures + lastApiError
```

### 3.3 LLM automation layer (continuous, in background)

- `validator-runner.js` — subscribes to `draft`, debounced 750ms trailing edge, hash-compares `rlsPayload` to suppress cascade from validator's own writeback. Owns `AbortController` lifecycle: each new fire aborts the previous in-flight request.
- `auto-correct.js` — pure-function subscriber on `draft.rlsPayload`. Three rules. Pushes `ui.autocorrectSuggestions[]` for the panel to render as Apply/Dismiss chips. NEVER auto-applies.
- `smart-surface.js` — pure-function subscriber on `draft + ui + errorState`. Computes `{fieldErrors, banners}` derived signals. Inline lint hidden until the user blurs the field; banners surface validator-unavailable / breaker-open.

### 3.4 Backend endpoints

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | /api/me | Identity (upn, role, dept, role_band) | DONE v0.2.0a |
| POST | /api/intake | classify + extract → rlsPayload draft | DONE v0.2.0a |
| POST | /api/validate | validate_rls_structure | DONE v0.2.0a |
| POST | /api/query | DEV mock SSE stream + ROI emit | DONE v0.2.0a + W6 |
| POST | /api/agent/{kind} | LLM chat stream + ROI emit | DONE v0.2.0a |
| GET | /api/health/breakers | Per-tool breaker state (polled 30s by frontend) | DONE v0.2.0a |
| GET | /api/cao/brief?rlsId= | Canned brief stub for CAO panel | DONE v0.2.0b |
| GET | /cao/{rls_id} | SPA catch-all → index.html | DONE v0.2.0b |

### 3.5 Static asset routing

| URL | Backed by |
|---|---|
| `/` | `apps/web/static/index.html` (html=True default) |
| `/static/*` | `apps/web/static/` (lit bundle, main.js, components/, core/) |
| `/styles/*` | `apps/web/styles/` (tokens — pre-existing v0.1.0 oklch palette) |
| `/cao/{rls_id}` | FastAPI route → returns `apps/web/static/index.html` |

---

## 4. Lessons learned (so we don't relive them)

### 4.1 happy-dom escapes Lit directive markers

**Symptom:** `${array.map(i => html\`...\`)}` renders as `<?>` in the shadow DOM under happy-dom. 12 of 50 frontend tests failed with TypeError (null elements) or assertion mismatches.

**Root cause:** happy-dom's Comment node handling escapes the marker comments Lit uses to track template arrays.

**Fix:** Vitest config uses `environment: 'jsdom'`. Production browser still uses the vendored esm.sh Lit bundle via importmap — only the test environment changed. `lit` is also a devDep so Vitest resolves the proper npm package, not the esm.sh build.

### 4.2 Validator-runner cascade

**Symptom:** Single user edit triggered 2-4 backend validate calls. eventLog grew faster than reality.

**Root cause:** `store.subscribe('draft', ...)` in validator-runner fires on ANY draft mutation. The runner itself writes back to `draft.{blocking,warnings,cureSteps,lastValidated}`, which re-fires its own subscriber, scheduling another timer.

**Fix:** Hash-compare `JSON.stringify(store.draft.rlsPayload)` against the last fired hash. Re-fire only when the user-editable payload actually changed. Fix is at `apps/web/static/core/automation/validator-runner.js`.

### 4.3 Background subagent skipped TDD verification

**Symptom:** Subagent reported DONE_WITH_CONCERNS — wrote all source + tests, never ran `npm install` or test runs. Foreground verification revealed 12 test failures.

**Root cause:** The background sandbox blocked `npm install` (HTTP downloads of npm registry blocked or timing out). Subagent flagged the gap honestly but did not iterate.

**Fix going forward:**
- Background subagents are good for code-write tasks but flaky for tasks needing network installs.
- For Node-tooled plans: do `npm install` in the foreground first, then dispatch background-only for source/test writes.
- Always run the test suite manually after a background subagent reports DONE_WITH_CONCERNS.

### 4.4 Port 8080 collides with Docker

**Symptom:** Playwright `webServer.url` health check timed out even though uvicorn started successfully.

**Root cause:** Docker Desktop on the dev workstation listens on `:8080` (`http-alt`). Both the gateway and Docker tried to bind; Docker won, gateway started but Playwright's URL check hit Docker's 404 instead of the gateway.

**Fix:** Switched to port 8090 throughout (Playwright config, runbook, plan §2.5). `reuseExistingServer: false` so Playwright doesn't pick up a stale gateway from a previous run.

### 4.5 Static mount paths must match index.html refs

**Symptom:** Browser console errors: `/static/lib/lit-3.2.1.min.js 404`, `/styles/tokens/_base.css 404`. Page rendered but unstyled / Lit imports failed.

**Root cause:** Gateway only mounted `apps/web/static/` at `/`. Index.html references `/static/*` (Lit + main.js) and `/styles/*` (CSS) — neither matched the root mount's directory tree.

**Fix:** Three mounts in DEV_MODE block (registration order matters):
1. `/static` → `apps/web/static/` (so `/static/lib/...` works)
2. `/styles` → `apps/web/styles/` (so `/styles/tokens/...` works)
3. `/` → `apps/web/static/` with `html=True` (serves index.html for bare `/`)

Mounts registered AFTER `/cao/{rls_id}` route, but that's OK — FastAPI checks routes in registration order and the route registers before the DEV_MODE block runs.

### 4.6 Test timing under jsdom

**Symptom:** Intake-panel test failed with `expected '' to be 'drafted'` — async fetch chain didn't resolve in 30ms.

**Root cause:** Test code path: input → @input handler updates `_text` → button click triggers `_draft()` → `await postIntake()` → mock fetch resolves → microtask queue → `store.update`. Under jsdom this chain takes 50-100ms variably.

**Fix:** Replace `setTimeout(r, 30)` with `await el.updateComplete` after input event + a poll loop on `store.draft.rlsPayload.title === 'drafted'` (10ms × 50 retries = 500ms upper bound). Same pattern works for any test waiting on backend response → store mutation.

---

## 5. Carry-forward for v0.2.1

These items are deferred (some are explicit spec deferrals, some surfaced this session):

| # | Item | Source |
|---|---|---|
| L1 | Real `check_code_enforcement_litigation` validator | Spec §7 v0.2.1 |
| L2 | Real `check_urgency_rules` + `calendar.check_working_days` | Spec §7 v0.2.1 |
| L3 | `list_rls_precedents` against 50-opinion BM25 + LightRAG corpus | Spec §7 v0.2.1, Lock #9 |
| L4 | `get_policy_snippets` against Procedure 26-104.001 + LDC | Spec §7 v0.2.1 |
| L5 | Cure path mark-done re-runs validation | Spec §7 v0.2.1 |
| L6 | Co-pilot Ask tab (LLM + scoped tool access, READ-ONLY) | Spec §7 v0.2.1 |
| L7 | `update_rls_status` atomic protocol (audit + lineage + ROI in one tx) | Spec §15 W1 |
| L8 | Co-pilot Metrics tab against manatee-ai-roi | Spec §7 v0.2.1 |
| L9 | Real LLM wiring (replace `prompt_tokens=0` placeholders from cleanup #17) | DSPy chain integration |
| L10 | JWT claims gain `dept` + `role_band` (removes `_EMIT_DEFAULTS` placeholders) | Contract hardening W7 |
| L11 | Frontend Co-pilot Feed swaps to gateway audit endpoint when parallel fan-out lands | Frontend ADR-003 |
| L12 | County brand colors confirmed against Manatee Communications style guide | Frontend §15 OQ-1 |
| L13 | CAO route gating (Entra group claim vs current dropdown) | Frontend §15 OQ-2 |
| L14 | LLM-driven auto-correct against `get_policy_snippets` corpus | Frontend §15 OQ-3 |
| L15 | Pilot Mac-vs-Windows render parity check | Frontend §15 OQ-5 |

Hard prerequisite for several: **`manatee-ai-roi` FastAPI deployed on `bcc-ap-llm01`** (still pending). Without it, ROI events drain to local JSONL fallback indefinitely. ~30 min RDP work; tracked as the highest-leverage item in `pending_work.md`.

Two from contract hardening design also still open: W6 (breaker test extension), W8 (gateway aggregating per-tool /health), W10 (dead-letter JSONL).

---

## 6. Repo map (where things live)

```
rls-apex-v1/
├── apps/
│   ├── gateway/                    Backend (Python/FastAPI)
│   │   ├── main.py                 Routes + DEV-mode static mounts
│   │   ├── circuit.py              Two-layer circuit breaker library
│   │   ├── db/                     Pydantic models + asyncpg pool + Alembic
│   │   ├── sidecar/                manatee-ai-roi A+ client (HTTP + JSONL fallback + drain)
│   │   └── requirements.txt        Pinned (sqlalchemy[asyncio]==2.0.49, greenlet>=3.0,<4)
│   ├── web/                        Frontend (Lit + vanilla JS)
│   │   ├── package.json            devDeps only (lit, vitest, jsdom, playwright)
│   │   ├── vitest.config.js        jsdom env (NOT happy-dom — see §4.1)
│   │   ├── playwright.config.js    Port 8090 (NOT 8080 — see §4.4)
│   │   ├── static/                 Frontend served from /static
│   │   │   ├── index.html
│   │   │   ├── main.js
│   │   │   ├── lib/lit-3.2.1.min.js
│   │   │   ├── core/               store, persist, api, router, automation/
│   │   │   ├── components/         9 Lit components
│   │   │   └── _archive/           Rolled-back v0.1.0 17k-line prototype
│   │   ├── styles/                 Frontend CSS served from /styles
│   │   │   └── tokens/             _base.css + _brand-overlay.css (oklch)
│   │   └── tests/
│   │       ├── unit/               17 Vitest files
│   │       ├── e2e/                2 Playwright specs
│   │       └── visual/
│   │           ├── run.sh          Servo screenshot harness
│   │           └── baseline/       7 PNG baselines
│   └── web-next/                   May 6 rolled-back Next.js scaffold (untracked, archive only)
├── mcp_tools/
│   ├── _lib/                       Shared tool framework (build_tool_app, JWT, ROI emit)
│   ├── classify_matter/            Mock classifier
│   ├── validate_rls_structure/     Real domain.yaml validator
│   └── extract_fields/             Mock extractor
├── tests/                          Backend pytest (60+4=64 passing)
├── alembic/                        Migrations
├── scripts/
│   └── smoke.sh                    Manual E2E smoke for backend
└── docs/
    ├── superpowers/
    │   ├── specs/                  Reframe + contract hardening + frontend design
    │   └── plans/                  v0.2.0b-backend + v0.2.0b-frontend implementation plans
    └── runbooks/
        └── 2026-05-09-rls-apex-v0_2_0b-runbook.md   (this file)
```

---

## 7. Commit history (May 8–9)

For full session arc, read in chronological order:

```
6e5c583  fix(roi): close Rule #18 schema gap on gateway endpoints + non-vacuous e2e
e8eeb1a  feat(roi): pre-flight validate guard + drop unschema'd ts field in ToolRoiEmitter (W1)
939a512  docs(roi): correct emit() docstring re: ValueError on pre-flight failure
d708b6b  test(roi): parametrized MCP tool emit compliance (W5, RED)
946a81e  feat(roi): classify_matter emit contract hardening (W2, W9)
4d140c1  feat(roi): validate_rls_structure emit contract hardening (W3, W9)
032458c  feat(roi): extract_fields emit contract hardening (W4, W9)
2b757d5  feat(roi): /api/query DEV_MODE emits ROI event after stream close (W6)
79077bd  docs(v0.2.0b): backend ROI emit cleanup plan + contract hardening design
d8d8f92  docs(v0.2.0b-frontend): design spec — Lit + stepper + aggressive LLM automation
a9cbaff  docs(v0.2.0b-frontend): implementation plan — 24 tasks, 112 TDD steps
d23b3db  feat(web): T1 bootstrap — archive prototype, vendor Lit 3.2.1, new index.html
99141b5  feat(gateway): GET /api/cao/brief — canned v0.2.0b stub + Rule #18 emit
b63ed29  feat(gateway): GET /cao/{rls_id} catch-all serving index.html for SPA router
3a7aee2  chore(web): frontend source scaffold — T2-T20 (npm tests pending)
8a0f5e5  fix(web): GREEN frontend test verification — 4 fixes from RED→GREEN cycle
577232d  feat(web): T23 E2E + T24 Servo baselines green; static mount fixes
```

Backend ROI cleanup landed first; frontend stack landed in two waves (source-scaffold by background subagent, then GREEN-fixes in foreground when verification surfaced).

---

## 8. Pickup notes for next session

If picking up cold:

```bash
cd /Users/ejarbe/Projects/rls-apex-v1
git checkout feat/v0.2.0a-backend
git pull origin feat/v0.2.0a-backend
.venv/bin/python -m pytest -q                                    # 64 expected
cd apps/web && npm install && npm test                           # 50 expected
DEV_AUTH_BYPASS=1 ../../.venv/bin/python -m uvicorn apps.gateway.main:app --host 127.0.0.1 --port 8090 --reload
# Open http://127.0.0.1:8090/ in a browser to click through the UI
```

For v0.2.1 kickoff: `superpowers:brainstorming` against the L1-L15 list above to break it into sub-projects, then `superpowers:writing-plans` per sub-project. The hard prereq (manatee-ai-roi FastAPI on llm01) should be done first or v0.2.1 ROI metrics will keep accumulating in local JSONL.

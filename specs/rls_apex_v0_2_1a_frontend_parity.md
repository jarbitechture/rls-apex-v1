# RLS Apex v0.2.1a — Frontend-Parity Audit (#41)

Read-only audit. Repo `/Users/ejarbe/Projects/rls-apex-v1`, branch `feat/v0.2.0a-backend`, HEAD `daeeadc` (tag `v0.2.1a-rc2`). No source modified, no tests run.

Method: traced the live import graph from the served HTML entry, read every loaded
component / core module / automation module, then read every gateway route handler
and Pydantic model each one touches. The reverse-spec (#52) §8 was treated as a
hypothesis set and independently confirmed against code with file:line evidence.

**Live entry chain (verified):** `apps/web/static/index.html:14-15` mounts
`<rls-shell>` and loads only `static/main.js` → `main.js:1` imports
`components/rls-shell.js` → `rls-shell.js:1-19` imports 3 core modules
(`store`, `persist`, `api`), `router`, 3 automation modules
(`validator-runner`, `auto-correct`, `smart-surface`), and 10 components
(`app-header`, `rls-disclaimer-banner`, `step-bar`, `intake-panel`,
`form-panel`, `status-panel`, `cure-path-panel`, `submit-panel`,
`copilot-feed`, `cao-view`). The importmap (`index.html:9-11`) maps only
`lit`. Nothing in the live graph references `rls-api.js`, `agent-driver.js`,
`chat.html`, or `vendor/react*`.

---

## 1. Verified spec-claims table

| # | Spec claim (#52 §8) | Verdict | Evidence |
|---|---|---|---|
| 1 | `/api/health/breakers` returns `{breakers:[{name,state}]}` but `smart-surface.js` iterates it as a `{name:state}` map → breaker-open banner is dead code | **CONFIRMED** | Backend: `main.py:910-911` returns `{"breakers": [<list>], "note": ...}`; each list element = `breaker.status()` = `{name,state,consecutive_failures,last_failure_ts,last_success_ts}` (`circuit/breaker.py:151-158`). Wiring: `rls-shell.js:72` sets `errorState.breakerStatus = r.breakers` — i.e. an **array**. Consumer: `smart-surface.js:12` `for (const [name, state] of Object.entries(breakerStatus))` then `if (state === 'open')`. `Object.entries` over an array yields `["0", {…obj…}]`, so `state` is an object, never `=== 'open'`. Banner is unreachable. Double mismatch: container shape (array vs map) **and** element shape (object vs string). |
| 2 | `validator-runner.js` reads `result.cureSteps` but `ValidationResult` has no `cureSteps` → cure-path panel permanently empty | **CONFIRMED (refined)** | `ValidationResult` (`apps/gateway/db/models.py:100-102`) = `blocking`, `warnings` only. `validate_dict` returns `ValidationResult(blocking=…, warnings=…)` (`mcp_tools/validate_rls_structure/server.py:92`); endpoint does `result.model_dump()` (`main.py:419`). JSON never contains `cureSteps`. `validator-runner.js:33` writes `d.cureSteps = result.cureSteps || []` → always `[]`. `cure-path-panel.js:27,30-31` then renders the **"No cure steps — status is ReadyForCAO. Continue to Submit."** empty state. Refinement: not a crash or blank panel — it is an affirmatively *wrong* "ReadyForCAO" message shown even when `blocking` is non-empty (`status-panel.js:51-52` still routes the user to the cure step on blockers). Worse than empty: misleading. |
| 3 | `cao-view.js` Accept/Return/Reject only toast — no backend decision-write endpoint exists | **CONFIRMED** | `cao-view.js:34-37` `_decision(kind)` sets `this._toast = "<kind> — decision write goes live in v0.2.1"`; no `fetch`. The only decision-write route `/api/rls/{rls_id}/decision` (`main.py:1041`) is inside `if DEV_MODE:` (`main.py:978`, `DEV_MODE = os.environ.get("DEV_AUTH_BYPASS")=="1"` at `main.py:45`). In a production deploy (no bypass) it does not exist. |
| 4 | Gateway→MCP HTTP transport is `NotImplementedError`; the 4 HTTP tools (:30103-30106) are unreachable; `/api/lint/policy` uses in-process import not HTTP | **CONFIRMED** | `call_tool()` (`main.py:1583-1594`) body is `raise NotImplementedError` (3 TODOs: JWT sign, loopback POST, breaker). `/api/lint/policy` (`main.py:1486`) → `_call_l4_get_policy_snippets` (`main.py:1197-1208`) → `HybridRetriever` imported in-process (`main.py:1155`, `1199-1200`) per ADR-006 ("library-in-each-tool, NOT HTTP to L4 MCP service", `main.py:1490-1491`). No live UI path reaches an HTTP MCP tool. |
| 5 | Orphan SPA files (`rls-api.js`, `agent-driver.js`, `chat.html`, React vendor) present but never loaded by the live importmap/entry; their DEV endpoints are not parity targets | **CONFIRMED** | `grep` of `main.js` + `components/` + `core/` for `rls-api`/`agent-driver`/`react`/`vendor/`/`chat.html` → no live reference. `index.html` loads only `main.js`. The orphan files are a second, unmounted SPA. Their endpoints (`/api/query`, `/api/agent/*`, `/api/rls*`, `/api/drafts*`, mock dashboards) are out of scope for parity (see §4). |

All five spec claims hold. The reverse-spec §8 tables are accurate; this audit adds the claim-2 refinement (misleading "ReadyForCAO" rather than benign empty) and the claim-1 double-mismatch detail.

---

## 2. Component → endpoint contract map (live graph only)

Six endpoints are reachable from the live UI. Disabled-by-design buttons (no fetch) are noted but are not contract surfaces.

| Component (file:line) | Endpoint | Method | Request fields it sends | Response fields it consumes | Result |
|---|---|---|---|---|---|
| `rls-shell.js:47` (via `api.js:9`) | `/api/me` | GET | — (cookie/header auth) | `upn`, `role` | **MATCH** — backend returns `upn,display_name,initials,role` (`main.py:312-317`); UI reads `upn`,`role` only |
| `intake-panel.js:38` (via `api.js:13`) | `/api/intake` | POST | `{text}` | `rlsPayload`, `classification` (`.type`) | **MATCH** — backend returns `{classification, rlsPayload}` (`main.py:388-391`); `intake-panel.js:40-44` reads both |
| `validator-runner.js:29` (via `api.js:22`) | `/api/validate` | POST | `{rlsPayload}` | `blocking`, `warnings`, **`cureSteps`** | **GAP-1** — backend returns only `blocking`,`warnings` (`models.py:100-102`); `cureSteps` never present |
| `status-panel.js:29-30` (store-fed by validator-runner) | `/api/validate` (indirect) | — | — | `draft.blocking`, `draft.warnings` | **MATCH** — renders `b.message ?? b.code` from real fields (`status-panel.js:43,47`) |
| `cure-path-panel.js:27` (store-fed) | `/api/validate` (indirect) | — | — | `draft.cureSteps` | **GAP-1 (same root)** — always `[]`; renders false "ReadyForCAO" |
| `cao-view.js:30` (via `api.js:31`) | `/api/cao/brief?rlsId=` | GET | `rlsId` (query) | `rlsId,summary,keyFacts,risk,suggestedNextSteps` | **MATCH** — backend returns exactly these (`main.py:429-448`) |
| `cao-view.js:34` Accept/Return/Reject | (none) | — | — | — | **GAP-2** — UI implies a decision write; no production endpoint; toast-only |
| `rls-shell.js:71` (via `api.js:35`) | `/api/health/breakers` | GET | — | `breakers` (consumed as `{name:state}` map) | **GAP-3** — backend returns `{breakers:[{name,state,…}]}`; shape + element mismatch; banner dead |
| `auto-correct.js:91` (`policyLintLlm`, direct fetch) | `/api/lint/policy` | POST | `{rlsPayload}` | `suggestions[]` (`.ruleId,.field`) | **MATCH** — backend returns `{suggestions:[{ruleId,field,citation,explanation,severity}]}` (`main.py:1551-1558`); UI dedup reads `ruleId`,`field` |
| `submit-panel.js:38` Submit | (none) | — | — | — | Not a gap — disabled by design; copy-JSON escape hatch (`submit-panel.js:42-46`); explicit v0.2.1 deferral |
| `cure-path-panel.js:37` Mark Done | (none) | — | — | — | Not a gap — disabled by design, v0.2.1 deferral |
| `app-header.js:29` role `<select>` | (none) | — | — | — | Client-only; mutates `session.role`, gates nothing. Not a contract. |
| `step-bar.js:29`, `form-panel.js`, `copilot-feed.js`, `rls-disclaimer-banner.js` | (none) | — | — | store-derived only | No endpoint dependency |

**Counting rule:** unique live endpoints (6 total), classified by parity outcome. Disabled-by-design buttons and client-only controls are not endpoints and are excluded from the tally.

**Tally: MATCH = 4, GAP = 2, ORPHAN = 10.**
- **MATCH = 4 endpoints:** `/api/me`, `/api/intake`, `/api/cao/brief`, `/api/lint/policy` (UI contract == backend contract).
- **GAP = 2 endpoints:** `/api/validate` (GAP-1, `cureSteps` field absent — one root cause that breaks both `validator-runner.js` and `cure-path-panel.js`), `/api/health/breakers` (GAP-3, shape + element mismatch).
- **Plus 1 missing-endpoint defect (GAP-2):** CAO Accept/Return/Reject has no production decision-write endpoint — counted in the GAP register (§3) but not among the 6 live endpoints, since the endpoint does not exist to classify.
- **ORPHAN = 10:** backend endpoint groups with zero live UI consumer (§4 — the 10 endpoint-group rows; the orphan-files row and the `call_tool()` transport row are listed for context but are not endpoints).

### Persona scoping & validator behavior — confirmed against shipped backend

- **Requester-only wizard:** `router.js:1` `STEPS = [intake,form,status,cure,submit]`; `parseLocation` yields only `view:'requester'` (5-step) or `view:'cao'` (`router.js:3-11`). `rls-shell.js:79-94` renders the CAO view as `<rls-disclaimer-banner>` + `<cao-view>` with **no** wizard chrome.
- **Read-only CAO route:** `cao-view.js` only GETs `/api/cao/brief`; its three action buttons are toast-only (GAP-2). No backend write is wired and none exists outside DEV. Read-only by construction — matches the shipped backend.
- **No backend-enforced persona:** `app-header.js:29` role selector writes only `session.role` client-side and gates nothing — consistent with reverse-spec §8.4 and the backend (`/api/me` `role` is display-only, `main.py:306-309`).
- **Validator = drafting assist:** `validator-runner.js:6-16` is debounced (750 ms), hash-guarded against its own write-back cascade, abortable; it never blocks input and only annotates `blocking`/`warnings` (drafting-assist, Lock #19). The single behavioral defect is GAP-1 (it also tries to read a non-existent `cureSteps`). Backend `/api/validate` is a pure structural grader (`server.py:48-92`) — matches the drafting-assist contract.

---

## 3. Ranked GAP register

Severity = user-facing impact. Effort = engineering cost. Rank = severity-weighted, lowest-effort-first within a severity tier.

| Rank | ID | Severity | Effort | Defect | Minimal fix | Owning side |
|---|---|---|---|---|---|---|
| 1 | **GAP-1** | **High** — a Requester with blocking issues is shown "status is ReadyForCAO. Continue to Submit." The cure-path step (the product's core remediation surface) is permanently blank and actively misleading. Governed legal-intake workflow tells the user the wrong thing. | **Low** | `validator-runner.js:33` reads `result.cureSteps`; `ValidationResult` has no such field. | Decision required (2 options): **(A) UI-side, lowest effort:** in `cure-path-panel.js`, derive the empty/non-empty state from `store.draft.blocking.length` instead of `cureSteps`; drop the `cureSteps` read in `validator-runner.js:33`; when `blocking>0` show "Resolve the N required items in Step 3 before CAO review" instead of the false ReadyForCAO line. No backend change; honest UI; no real cure-step content (acceptable for v0.2.1a since cure-step generation is a v0.2.1 deferral per `cure-path-panel.js:38`). **(B) backend-side:** add a `cure_steps: list[CureStep]` field to `ValidationResult` and populate it — larger, pulls forward a v0.2.1 feature. Recommend **(A)** for v0.2.1b: it removes the falsehood at near-zero cost without scope creep. | UI (Option A) |
| 2 | **GAP-3** | **Medium** — breaker-open banner never renders, so a Requester gets no signal when the ROI sidecar / future MCP breakers are open. Degrades gracefully (silent), not actively wrong. W5 ops affordance is dead. | **Low** | `rls-shell.js:72` assigns the raw `breakers` array to `errorState.breakerStatus`; `smart-surface.js:12-13` expects a `{name:state}` map. | UI-side, one line: in `rls-shell.js:72` reshape — `e.breakerStatus = Object.fromEntries((r.breakers||[]).map(b => [b.name, b.state]))`. This matches the existing `smart-surface.js` contract exactly, no consumer change, no backend change. (Alternative: change `smart-surface.js` to iterate the array — equivalent effort but touches the more-tested derivation module; prefer the shell shim.) | UI |
| 3 | **GAP-2** | **Low** — CAO Accept/Return/Reject buttons toast "decision write goes live in v0.2.1". This is an honest, labeled deferral, not a silent failure; CAO route is read-only by design for v0.2.1a. Flagged only so it is a deliberate scope decision, not an accident. | **Low (label)** / High (full feature) | No production decision-write endpoint; `/api/rls/{id}/decision` is DEV-only (`main.py:978,1041`). | No code change for v0.2.1b beyond confirming scope. Minimal hardening: keep the toast but also `disabled` the buttons (match `submit-panel.js`/`cure-path-panel.js` deferral pattern) so the UI is consistent about "not yet wired". Full decision-write is a v0.2.1 backend feature (out of scope here). | UI (cosmetic) / backend (full feature, deferred) |

No GAP requires a backend change for v0.2.1b under the recommended options. GAP-1 and GAP-3 are both one-to-few-line UI fixes; GAP-2 is a scope confirmation plus an optional cosmetic consistency tweak.

---

## 4. Orphans — explicitly out of scope (do not re-flag)

These backend surfaces have **no live UI consumer**. They are reachable only by the unmounted legacy SPA (`rls-api.js` / `agent-driver.js` / `chat.html`) or are ops/DEV-only. Listed here so a future review does not re-open them as parity gaps.

| Surface | Status | Why orphaned (not a parity target) |
|---|---|---|
| `rls-api.js`, `agent-driver.js`, `chat.html`, `vendor/react*` | Files present, never imported | Not in the `index.html` → `main.js` → `rls-shell.js` graph. Separate dead SPA. |
| `/api/query` (SSE validator) | Shipped (DEV path) | Called only by legacy `rls-api.js`/`agent-driver.js` |
| `/api/agent/dispatch`, `/api/agent/kinds` | Shipped | Legacy SPA only |
| `/api/feedback`, `/api/feedback/recent` | Shipped | No live consumer |
| `/api/retrieve`, `/api/corpus`, `/api/corpus/reload` | Shipped | No live consumer |
| `/api/health/sidecar`, `/api/health/aggregated`, `/api/health/llm` | Shipped | Ops / W8 telemetry; no UI |
| `/healthz`, `/readyz` | Shipped | Liveness/readiness probes |
| `/api/sample`, `/api/rls*`, `/api/drafts*`, `/api/precedents`, `/api/kpi/summary`, `/api/inbox`, `/api/queue`, `/api/team-load`, `/api/compliance-pulse` | DEV mock (`if DEV_MODE`) | Legacy SPA only; not served in prod |
| `/api/skills/templates*` | 501 stub | Not implemented |
| `/api/matters/{id}/drafts/{path}` | 501 reserved | Namespace reservation |
| `call_tool()` MCP-HTTP transport (:30103-30106) | `NotImplementedError` | No live UI path reaches it; L14 lint uses in-process `HybridRetriever` per ADR-006 |

The orphan SPA's DEV endpoints are **not** parity obligations for v0.2.1a/b. If the legacy SPA is not slated to ship, recommend deleting `rls-api.js`, `agent-driver.js`, `chat.html`, `vendor/react*` in a future cleanup task to prevent recurring confusion (out of scope for this read-only audit; flagged only).

---

## 5. Recommended fix sequence for v0.2.1b

All UI-side, all low effort, no backend change, no scope creep.

1. **GAP-1 (Option A) — kill the false ReadyForCAO.** Highest user-facing severity. In `cure-path-panel.js`, gate the empty/filled state on `store.draft.blocking.length` not `cureSteps`; when `blocking>0`, render "Resolve the N required items in Step 3 before CAO review." Remove the `cureSteps` read in `validator-runner.js:33` (and the `d.cureSteps` write). Add/adjust a Vitest (jsdom, not happy-dom — Lit directive markers) asserting: blockers present → no "ReadyForCAO" text.
2. **GAP-3 — restore the breaker banner.** One-line reshape in `rls-shell.js:72`: `e.breakerStatus = Object.fromEntries((r.breakers||[]).map(b => [b.name, b.state]))`. Add a Vitest feeding `{breakers:[{name:'roi_sidecar',state:'open'}]}` and asserting a `breaker-open` banner via `computeSurface`.
3. **GAP-2 — confirm CAO-read-only scope, then cosmetic consistency.** Get product sign-off that v0.2.1a/b CAO route stays read-only. If yes, `disabled` the Accept/Return/Reject buttons in `cao-view.js` to match the established deferral pattern (`submit-panel.js`, `cure-path-panel.js` Mark Done). Backend decision-write stays a v0.2.1 item.
4. **(Optional, separate cleanup task — not v0.2.1b code)** Delete the orphan legacy SPA files once product confirms it will not ship, to stop this surface from being re-audited.

Suggested gate: each of fixes 1-3 is its own commit; run the Lit Vitest suite in **jsdom** (per the standing constraint — happy-dom escapes `.map(html\`\`)` directive markers) and capture a Servo/Playwright visual baseline of Step 4 (cure path with blockers) and the breaker banner since both are visible changes.

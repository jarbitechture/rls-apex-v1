# RLS Apex v0.2.0b — Frontend Design Spec

**Spec date:** 2026-05-08
**Branch:** `feat/v0.2.0a-backend` (v0.2.0b work continues here, then merges/branches at plan execution time)
**Spec author:** Claude (Opus 4.7) via brainstorming + architecture-designer + circuit-breaker-design
**Predecessor:** `2026-05-08-rls-apex-mcp-reframe-design.md` (full reframe spec, 642 lines, §7 v0.2.0 scope)
**Companion:** `2026-05-08-roi-emit-contract-hardening-design.md` (closed in v0.2.0b-backend; commits e8eeb1a → 2b757d5)

---

## 1. Goal + scope

Build the requester + CAO frontend surface against the v0.2.0a backend so a 10-user pilot group can run a complete RLS through the system in their browser within two weeks.

**Concrete deliverable:** seven Lit-based panels (intake, form, status, cure-path scaffold, submit-stub, CAO view, Co-pilot Feed) wired to the existing gateway endpoints, with localStorage-backed draft auto-save, aggressive LLM-driven automation in the background, and Servo-verified visual baselines per panel.

**Non-goals (deferred to v0.2.0c or v0.2.1):**

- Server-side matter persistence (Track C; deferred to v0.2.0c)
- Real `update_rls_status` write tool (spec §7 v0.2.1)
- Cure path mark-done re-validation (v0.2.1)
- Co-pilot Ask + Metrics tabs (v0.2.1)
- Real precedent corpus retrieval (v0.2.1, Lock #9)
- Real Entra OIDC role gating (v0.2.0a returns hardcoded role; v0.2.0b uses dev-mode role switcher; v0.2.1 wires JWT group claim)
- Mobile-responsive layout (county uses desktop)
- Accessibility audit beyond keyboard navigation defaults

---

## 2. Locked constraints (from brainstorm)

| # | Constraint | Source |
|---|---|---|
| C1 | Pilot ship target: 2 weeks | User decision |
| C2 | Layout: stepper + persistent Co-pilot rail (not peer tabs, not single-screen dashboard) | User decision (browser mockup A) |
| C3 | Draft persistence: localStorage auto-save; no server-side persistence | User decision (Track C deferred) |
| C4 | Stepper policy: linear with paste-skip toggle on Intake | User decision |
| C5 | LLM automation tier: aggressive (continuous validation + auto-correct + smart-surface) | User decision |
| C6 | Implementation stack: Lit 3.x via vendored ES module, no build step | User decision |
| C7 | Lock #11: `_base.css` + `_brand-overlay.css`; CSS variables; no hex literals in components | reframe spec §10 |
| C8 | Lock #5: gateway hosts at `rls.mymanatee.org` (planned); Entra OIDC at gateway boundary | reframe spec §10 |
| C9 | Operating Rule #18: every user-facing action emits a ROI event (already wired in v0.2.0a + v0.2.0b-backend) | CLAUDE.md |
| C10 | Browser target: Edge 110+ / Chrome 110+ (ES2020 baseline, Lit 3 minimum) | This spec |

---

## 3. Architecture

### 3.1 Component graph

```
┌─────────────────────────── <rls-shell> (root) ─────────────────────────────┐
│ ┌──────── <app-header> ──────────┐                                         │
│ │  Manatee logo · role dropdown  │                                         │
│ └────────────────────────────────┘                                         │
│ ┌──────── <step-bar> ─────────────────────────────────────────────────┐   │
│ │  [1 Intake] [2 Form] [3 Status] [4 Cure] [5 Submit]                 │   │
│ └─────────────────────────────────────────────────────────────────────┘   │
│ ┌────────── main panel (router outlet) ────────┐ ┌──── <copilot-feed> ──┐│
│ │ <intake-panel>     (#step=intake)            │ │  live event log      ││
│ │ <form-panel>       (#step=form)              │ │  capped at 200       ││
│ │ <status-panel>     (#step=status)            │ │  filtered to session ││
│ │ <cure-path-panel>  (#step=cure)              │ │                      ││
│ │ <submit-panel>     (#step=submit)            │ │  subscribes to       ││
│ │                                              │ │  store.session.events││
│ └──────────────────────────────────────────────┘ └──────────────────────┘│
└────────────────────────────────────────────────────────────────────────────┘

Separately at /cao/:rlsId — <cao-view> (3-bullet brief, gated by store.session.role)
```

### 3.2 Project layout

```
apps/web/static/
├── index.html                      # bootstrap; importmap + <script type="module" src="main.js">
├── _archive/                       # rolled-back 17k-line prototype, NOT imported
├── css/
│   ├── _base.css                   # design tokens (Lock #11)
│   └── _brand-overlay.css          # Manatee blue/gold + county seal
├── lib/
│   └── lit-3.2.1.min.js            # vendored Lit 3.2.1 (SHA256 documented in this spec §10)
├── core/
│   ├── store.js                    # observable store (4 slices: draft, session, ui, errorState)
│   ├── persist.js                  # localStorage save/load (debounced 250ms, namespaced by upn)
│   ├── api.js                      # typed wrappers for /api/me, /api/intake, /api/validate, /api/cao/brief, /api/health/breakers
│   ├── router.js                   # HTML5 history router (#step=... within /; /cao/:rlsId standalone)
│   └── automation/
│       ├── validator-runner.js     # debounced /api/validate trigger; AbortController lifecycle
│       ├── auto-correct.js         # pluggable rule list (subject-trim, title-case, date-infer)
│       └── smart-surface.js        # error rendering policy (which errors where, when)
├── components/
│   ├── rls-shell.js                # <rls-shell>
│   ├── app-header.js               # <app-header>
│   ├── step-bar.js                 # <step-bar>
│   ├── intake-panel.js             # <intake-panel>
│   ├── form-panel.js               # <form-panel>
│   ├── status-panel.js             # <status-panel>
│   ├── cure-path-panel.js          # <cure-path-panel>
│   ├── submit-panel.js             # <submit-panel>  (disabled-stub in v0.2.0b)
│   ├── copilot-feed.js             # <copilot-feed>
│   └── cao-view.js                 # <cao-view>
├── tests/
│   ├── unit/                       # Vitest + happy-dom + @lit-labs/testing
│   ├── e2e/                        # Playwright (one happy-path per role)
│   └── visual/                     # Servo screenshots, baselines committed
├── package.json                    # devDeps only: vitest, happy-dom, @lit-labs/testing, playwright
└── main.js                         # entry: registerComponents, hydrate from localStorage, mount <rls-shell>
```

### 3.3 Bootstrap

`index.html` body:

```html
<script type="importmap">
{ "imports": { "lit": "/lib/lit-3.2.1.min.js" } }
</script>
<script type="module" src="/main.js"></script>
<rls-shell></rls-shell>
```

Components write `import { LitElement, html, css } from 'lit'`. The import map is the single resolution point — moving the vendored file requires only an `index.html` change.

`main.js` registers all custom elements then mounts `<rls-shell>`. `<rls-shell>` `connectedCallback` calls `persist.hydrate()` (loads localStorage into `store.draft`), starts the breaker poller, attaches the router, and renders the current step.

---

## 4. State + data flow

### 4.1 Store shape (4 slices)

```js
store = {
  // Persisted (localStorage). Serialized on debounced 250ms after change.
  draft: {
    schemaVersion: 1,
    rlsId: "rls-<uuid-v4>",                  // generated at intake
    rlsPayload: {                            // wire shape per apps/gateway/db/models.py
      type: null,
      title: "",
      department: "",
      legalQuestion: "",
      factualBackground: "",
      // ... other fields per Pydantic model
    },
    classification: { type: null, confidence: null },
    cureSteps: [],
    blocking: [],
    warnings: [],
    lastValidated: null,                     // timestamp
  },

  // In-memory; not persisted
  session: {
    currentStep: "intake",                   // intake | form | status | cure | submit
    eventLog: [],                            // capped at 200 (Risk #6)
    role: "requester",                       // requester | cao
    upn: null,                               // from /api/me; namespaces localStorage
  },

  // Ephemeral UI state
  ui: {
    blurredFields: new Set(),
    autocorrectSuggestions: [],
    pendingValidation: false,
    validatorAbortController: null,
  },

  // Cleared on next success per area
  errorState: {
    breakerStatus: {},                       // polled from /api/health/breakers every 30s
    validatorFailures: {},                   // tool_name → {timestamp, message}
    lastApiError: null,
  },
}
```

### 4.2 Subscription map

| Component | Slice(s) consumed | Reason |
|---|---|---|
| `<intake-panel>` | `draft.rlsPayload`, `ui.pendingValidation` | initial input + "thinking..." indicator |
| `<form-panel>` | `draft.rlsPayload`, `ui.blurredFields`, `ui.autocorrectSuggestions`, `errorState.validatorFailures` | live editing + smart-surface |
| `<status-panel>` | `draft.blocking`, `draft.warnings`, `draft.lastValidated`, `errorState.validatorFailures` | render status + Re-validate button |
| `<cure-path-panel>` | `draft.cureSteps`, `draft.blocking` | render steps; mark-done is no-op stub |
| `<submit-panel>` | `draft.blocking`, `draft.cureSteps` | always-disabled in v0.2.0b; tooltip references blocking count |
| `<copilot-feed>` | `session.eventLog` | frontend-tracked log per ADR-003 |
| `<step-bar>` | `session.currentStep`, `draft.blocking.length` | step states (current, complete, blocked) |
| `<cao-view>` | `draft` (full) + canned brief from `/api/cao/brief` | role-gated separate route |
| `<app-header>` | `session.role`, `session.upn` | role dropdown + identity |

### 4.3 Hot-path data flow (user typing in a Form field)

```
1. user keypress in form-panel input
   → form-panel.onInput: store.draft.rlsPayload[field] = value
                         store.ui.autocorrectSuggestions = []  (clear stale)

2. persist.js subscriber (debounced 250ms):
   localStorage.setItem(`rls-apex.draft.v1.${store.session.upn}`, JSON.stringify(store.draft))

3. validator-runner subscriber (debounced 750ms, trailing):
   if store.ui.validatorAbortController: validatorAbortController.abort()
   store.ui.validatorAbortController = new AbortController()
   store.ui.pendingValidation = true
   POST /api/validate { rlsPayload }, signal=abortController.signal
     ✓ → store.draft.{blocking,warnings,cureSteps,lastValidated} = response
         store.session.eventLog.push({ts, kind:"tool_invocation", tool:"validate_rls_structure", summary})
         store.ui.pendingValidation = false
     ✗ AbortError → ignore (newer request in flight)
     ✗ network/4xx → store.errorState.lastApiError = err
                     store.errorState.validatorFailures.validate_rls_structure = {ts, message}

4. auto-correct subscriber (no debounce; pure function over rlsPayload):
   for each rule in [subject-trim, title-case, date-infer]:
     if rule matches: store.ui.autocorrectSuggestions.push({field, fix, ruleId})

5. smart-surface subscriber (no debounce; pure function over draft + blurredFields + errorState):
   computes "what to render where" — populates derived signals consumed by panels
```

### 4.4 User journeys

**Journey A — fresh draft, requester:**

1. User opens `/`. `<rls-shell>` hydrates → `draft` is empty (no prior localStorage). `session.upn` from `GET /api/me`.
2. Step 1 active: `<intake-panel>` renders. User types in textarea. Click "Draft RLS".
3. `POST /api/intake` fires. Response populates `draft.rlsPayload` + `draft.classification`. `eventLog` appends classify + extract.
4. Auto-advance to Step 2: `<form-panel>`. User edits fields. validator-runner fires after 750ms. `<status-panel>` data updates in background.
5. User clicks Step 3 in step-bar (or Next button). `<status-panel>` renders the latest validation result. Banner shows "Status: Needs fixes — 2 required items missing" (or "Ready for CAO review" if blocking is empty).
6. If NeedsFixes: `<cure-path-panel>` becomes available. User reviews steps; mark-done shows "Coming in v0.2.1" tooltip.
7. Step 5 `<submit-panel>` is disabled with tooltip "Submit goes live in v0.2.1 with update_rls_status".
8. Throughout: `<copilot-feed>` rail shows every API call as it happens.

**Journey B — paste-skip:**

1. User clicks "Skip — I have a draft already" toggle on `<intake-panel>`.
2. `<intake-panel>` swaps to a structured form (every `rlsPayload` field as input). User pastes / fills.
3. validator-runner trailing-debounce waits 750ms after the last field change before firing once.
4. Auto-advance to `<form-panel>` already populated.

**Journey C — CAO accept:**

1. CAO opens `/cao/RLS-25-067`. `<rls-shell>` detects path, mounts `<cao-view>` instead.
2. `<cao-view>` calls `GET /api/cao/brief?rlsId=RLS-25-067` (canned response in v0.2.0b).
3. CAO sees brief + risk + suggested next steps.
4. Buttons: Accept / Return / Reject. v0.2.0b stubs: clicking shows toast "Decision write goes live in v0.2.1".

---

## 5. LLM automation layer (3 modules)

### 5.1 `core/automation/validator-runner.js`

**Responsibility:** debounced `POST /api/validate` orchestration; AbortController lifecycle; `eventLog` append.

**Signature:** `init({ store, api, intervalMs = 750 })` — registers a subscriber on `store.draft.rlsPayload` and `store.session.currentStep`.

**Behavior:**

- Trailing debounce: 750ms after last `rlsPayload` change OR `currentStep === "form"` transition
- On fire: cancel previous AbortController if any; create new; `store.ui.pendingValidation = true`; POST
- On success: write `blocking`, `warnings`, `cureSteps`, `lastValidated`; append eventLog
- On AbortError: silent; new request in flight
- On network/4xx: write `errorState.lastApiError` + `errorState.validatorFailures.validate_rls_structure`
- Always: `store.ui.pendingValidation = false` in a finally block

**Test coverage:** debounce timing, abort behavior under rapid input, error path renders banner.

### 5.2 `core/automation/auto-correct.js`

**Responsibility:** pluggable rule list scanning `rlsPayload`; surfaces suggestions; never auto-applies.

**Signature:** `init({ store })` — registers a pure-function subscriber on `store.draft.rlsPayload`.

**Rules (v0.2.0b):**

| Rule | Trigger | Suggestion |
|---|---|---|
| `subject-trim` | `title.length > 50` | trim to 50 chars at last word boundary; preview: "...{trimmed}" |
| `title-case-fix` | any word in `title` is `>3 chars` and `===.toUpperCase()` | proposed Title-Case version |
| `date-infer` | `factualBackground.match(/yesterday|last week|today/i)` | suggest specific date based on `Date.now()` |

**Output shape (in `store.ui.autocorrectSuggestions`):**

```js
{ ruleId: "subject-trim", field: "title", currentValue: "...", proposedValue: "...", reason: "…" }
```

**UX:** rendered as a chip below the field with "Apply" + dismiss buttons. NEVER auto-applies. User clicks Apply → store update + suggestion cleared.

**Test coverage:** each rule fires on its trigger, doesn't fire otherwise; "Apply" updates rlsPayload.

### 5.3 `core/automation/smart-surface.js`

**Responsibility:** decides which errors render where, and when.

**Signature:** `init({ store })` — pure-function subscriber on `store.draft`, `store.ui.blurredFields`, `store.errorState`.

**Rules:**

| Where | What's rendered | When |
|---|---|---|
| `<form-panel>` per-field | inline lint note (red) | only for fields in `ui.blurredFields` |
| `<form-panel>` per-field | autocorrect chip (amber) | always when suggestion exists for the field |
| `<status-panel>` | full blocking + warnings list | always |
| `<status-panel>` banner | "Validator unavailable" red | when `errorState.validatorFailures[*].timestamp < now - 30s` is false (fresh failure < 30s) AND status would otherwise render Ready |
| toast (transient) | API errors | `errorState.lastApiError` set within last 4s |
| top-of-page banner | breaker open | any `errorState.breakerStatus[*] === "open"` |

**Test coverage:** each rule's surface visibility under each input combination.

---

## 6. Panel-by-panel

### 6.1 `<intake-panel>`

- **Default:** large textarea + "Draft RLS" button + "Skip — I have a draft" toggle
- **Skip mode:** structured form (every rlsPayload field as input), populates `draft.rlsPayload` directly; validator-runner fires once after 750ms stability
- **POST /api/intake** on Draft RLS click; advances to `form` step on success
- **Loading:** "thinking..." dots in the button while pending
- **Error:** toast on failure; user retries

### 6.2 `<form-panel>`

- Renders every `rlsPayload` field as a labelled input (textareas for long fields)
- onInput → store update; onBlur → `ui.blurredFields.add(field)`
- Per-field inline lint (smart-surface)
- Per-field autocorrect chip (auto-correct rule output)
- "Re-validate now" button (forces validator-runner fire bypassing debounce)
- "Next →" button advances to `status` step (no extra trigger; latest validation result is already in store)

### 6.3 `<status-panel>`

- Single-sentence narrative: "Status: Needs fixes before CAO review — N items remaining" or "Status: Ready for CAO review — all required checks passed"
- Below: blocking list (red) + warnings list (amber)
- "Re-validate" button (re-fires validator-runner)
- "Cure path →" button if `blocking.length > 0` advances to `cure` step
- "Submit →" button advances to `submit` step (where it's disabled-stub)
- Banner: "Validator unavailable" if `errorState.breakerStatus[*]` is open

### 6.4 `<cure-path-panel>`

- Renders `draft.cureSteps[]`. Each step:
  ```
  [ ] Step N — Title
      Instruction text
      References: [LDC §6.4 (2018)] [RLS-25-0067]
      [Mark Done] (disabled, tooltip: "Goes live in v0.2.1 with check_attachment_metadata")
  ```
- Section header "Cure path" + count
- Empty state ("No cure steps — status is ReadyForCAO") when `cureSteps.length === 0` and `blocking.length === 0`

### 6.5 `<submit-panel>`

- Header "Review and submit"
- Read-only summary of `draft.rlsPayload`
- Submit button: disabled
- Tooltip on hover: "Submit goes live in v0.2.1 with update_rls_status. For pilot: copy the JSON below and email to County Attorney."
- Below: pretty-printed `rlsPayload` JSON in a copy-on-click code block (pilot escape hatch)

### 6.6 `<cao-view>`

- Mounted at `/cao/:rlsId`. `<rls-shell>` detects path mismatch on hydrate, swaps the entire main panel.
- Header: "{rlsId} — Brief for CAO Review" + role indicator
- Calls `GET /api/cao/brief?rlsId=:rlsId` on connect; renders:
  - Summary (3-5 bullets)
  - Key facts
  - Risk section
  - Suggested next steps (clearly labelled "suggestions")
- Decision buttons: Accept / Return / Reject — all stubbed; click → toast "Decision write goes live in v0.2.1"

### 6.7 `<copilot-feed>`

- Right rail, fixed width 280px, scrollable
- Renders `session.eventLog` newest-first
- Each entry:
  ```
  14:03:21 · classify_matter (LLM)
  → permit_or_zoning (conf 0.82)
  ```
- Cap at 200 visible; "{N - 200} older events truncated" indicator at bottom
- Header: "Co-pilot Feed" + filter toggle (all events / errors only)

---

## 7. Backend wiring

### 7.1 Existing endpoints (unchanged from v0.2.0a)

| Endpoint | Used by |
|---|---|
| `GET /api/me` | `<rls-shell>` boot — populates `session.upn`, `session.role` |
| `POST /api/intake` | `<intake-panel>` submit |
| `POST /api/validate` | `validator-runner` |
| `GET /api/health/breakers` | breaker poller in `<rls-shell>` (every 30s) |

### 7.2 New endpoints for v0.2.0b

| Endpoint | Purpose | Effort |
|---|---|---|
| `GET /api/cao/brief?rlsId=<id>` | canned 3-bullet brief for `<cao-view>` (any rlsId returns the same canned object in v0.2.0b) | ~30 LOC FastAPI handler |

**Response shape:**

```python
{
    "rlsId": "...",
    "summary": ["bullet 1", "bullet 2", "bullet 3"],
    "keyFacts": ["fact 1", "fact 2"],
    "risk": "structural defects + substantive weaknesses prose",
    "suggestedNextSteps": ["step 1", "step 2"]
}
```

### 7.3 Routing change for HTML5 history

```python
# apps/gateway/main.py — add catch-all for /cao/* paths
@app.get("/cao/{rls_id}")
async def cao_view_passthrough(rls_id: str):
    """Serve index.html for any /cao/:rlsId so frontend router can take over."""
    return FileResponse("apps/web/static/index.html")
```

~10 lines. Required because StaticFiles doesn't serve index.html for arbitrary subpaths.

### 7.4 ROI emit additions

The new `GET /api/cao/brief` endpoint MUST emit a ROI event per Operating Rule #18:

```python
emit_roi({
    "event_kind": "tool_invocation",
    "workflow": "rls_apex.cao_brief",
    "tool": "rls_apex",
    "user_id": user.get("upn", "unknown"),
    "dept": user.get("dept", "DEV"),
    "role_band": user.get("role_band", "professional"),
    "task_type": "summarizing",
    "success": True,
    "extra": {"rls_id": rls_id},
})
```

---

## 8. Persistence + error handling

### 8.1 localStorage contract

- **Key:** `rls-apex.draft.v1.<upn>` (Risk #4 — namespaced per user)
- **Value:** `JSON.stringify(store.draft)` — only the `draft` slice
- **Write:** debounced 250ms after any `draft` change
- **Read:** `<rls-shell>.connectedCallback` after `/api/me` resolves
- **Schema mismatch (Risk #3):** if `parsed.schemaVersion !== 1`: drop draft + render one-line toast "Your previous draft was discarded due to a schema update"
- **Discard explicit:** "Discard draft" button in `<app-header>` clears the key + reloads
- **On Submit success (v0.2.1):** clear the key

### 8.2 Error UX (3 tiers)

| Tier | Surface | When | Example |
|---|---|---|---|
| Toast | snackbar bottom-right, 4s auto-dismiss, dismissible | transient API failure | "Couldn't save draft — retrying" |
| Banner | top of current panel, persistent until cause resolves | sustained > 30s | "Validator unavailable" |
| Modal | NEVER in v0.2.0b | — | (we don't block users) |

### 8.3 Loading states

| Trigger | UX |
|---|---|
| `<rls-shell>` first hydrate from localStorage | skeleton blocks for 200ms, then render |
| `validator-runner` `pendingValidation === true` | spinner inline next to "Re-validate" button |
| `POST /api/intake` in flight | "thinking..." dots replacing "Draft RLS" button text |
| `GET /api/cao/brief` in flight | skeleton lines in `<cao-view>` |
| Co-pilot Feed events being appended | new events fade-in 200ms |

---

## 9. Testing strategy

### 9.1 Tooling

| Layer | Tool | Why |
|---|---|---|
| Unit (Lit components) | Vitest + happy-dom + `@lit-labs/testing` | Lit-native test utilities; fast |
| E2E browser | Playwright | one happy-path per role |
| Visual regression | Servo (existing CLAUDE.md mandate) | Lock #11 verification |
| Backend smoke | existing pytest suite (60 passing) | unchanged |

### 9.2 Scripts

`apps/web/package.json`:

```json
{
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest",
    "test:e2e": "playwright test",
    "test:visual": "bash tests/visual/run.sh"
  },
  "devDependencies": {
    "vitest": "^2.0.0",
    "happy-dom": "^15.0.0",
    "@lit-labs/testing": "^0.5.0",
    "@playwright/test": "^1.45.0"
  }
}
```

### 9.3 Coverage target

- 80% lines on `core/` modules (store, persist, api, validator-runner, auto-correct, smart-surface)
- One unit test per panel component covering: render, store-driven updates, primary user action
- Two E2E tests: requester full journey (Intake → Form → Status → Cure render → Submit-disabled), CAO accept stub
- One Servo screenshot per panel × 1 baseline (7 baselines committed)

### 9.4 Dev-mode auth

Tests run with `DEV_AUTH_BYPASS=1`. Backend tests already use this; frontend Playwright config sets the env in the local dev server it spawns.

---

## 10. Architectural Decision Records

### ADR-001 — Lit + ES modules over hand-rolled vanilla JS

**Status:** Accepted

**Context:** spec §10 requires "boring official surface from scratch" (Lock #11). User chose Lit (5kb library, Web Components, no build step) over hand-rolled vanilla because aggressive LLM automation needs reactive subscriptions across 9 components and 4 store slices.

**Decision:** Lit 3.2.1 vendored as `lib/lit-3.2.1.min.js`. Resolved via importmap in `index.html` so components write `import { LitElement } from 'lit'`. SHA256 of the vendored file documented at commit time for tampering protection.

**Alternatives considered:**

- **Hand-rolled ES modules + tiny observable** — strictest Lock #11 alignment, ~30% more boilerplate per component. Rejected because aggressive automation generates many subscription points; Lit's `@property` reactivity saves real code.
- **esbuild dev server** — better DX, but adds build step (county IT scrutiny) and ~1MB toolchain. Rejected for v0.2.0b; revisit at v1.0 if iteration speed becomes the bottleneck.

**Consequences:** ~5kb static dependency. Component templating via `html\`...\`` tagged literals. `@property` reactivity replaces manual subscription wiring. Custom Element registration is the new "global" — must be careful with name collisions.

**Trade-offs:** Lock #11 spirit slightly bent ("framework" vs "vanilla"). Mitigation: vendoring + import map keeps the dependency surface fully visible for county IT review.

---

### ADR-002 — localStorage auto-save over server-side persistence (v0.2.0b)

**Status:** Accepted

**Context:** 2-week pilot ship target. Track C (matter persistence + audit log endpoint with rlsId scoping + atomic update protocol per spec §15 W1) is real backend work that would push the timeline. Pilot users need draft safety on accidental browser close.

**Decision:** Single-key localStorage namespaced by upn (`rls-apex.draft.v1.<upn>`). Holds `store.draft` slice only. Debounced 250ms write after any draft change. Schema version field for forward-compat (Risk #3). Cleared on Submit success (when v0.2.1 wires Submit).

**Alternatives considered:**

- **Pure in-memory** — lightest scope. Rejected: any browser crash loses pilot user work and frustrates day-one.
- **Server-side (Track C)** — drafts follow user across machines and survive any client failure. Rejected for v0.2.0b: ~3-5 days extra backend work threatens 2-week target.

**Consequences:** Drafts don't follow user across machines (acceptable for internal pilot). localStorage size limit (~5MB per origin) is far from threatened by typical RLS payload (~10KB).

**Trade-offs:** Spec-text fidelity to "every state change writes audit row" (NFR §11) is partial — audit happens on validate (already in v0.2.0a) and on submit (v0.2.1). Drafts in flight are not audited. Acceptable for pilot scope; documented in §16 Open Questions.

---

### ADR-003 — Co-pilot Feed source: frontend event log (v0.2.0b)

**Status:** Accepted

**Context:** Spec §5.8 says Feed sources from "the gateway's per-action audit + ROI events." At v0.2.0b every MCP call is 1:1 with a frontend-issued endpoint call. No backend orchestration hides intermediate calls.

**Decision:** Frontend tracks `session.eventLog` populated as API calls return. `<copilot-feed>` subscribes to `store.session.eventLog`. Capped at 200 entries (Risk #6).

**Alternatives considered:**

- **Lightweight gateway ring-buffer endpoint** (`GET /api/audit/recent?limit=N`) reading in-memory event deque alongside `_roi_client`. ~40 LOC. Rejected because at v0.2.0b scope it adds zero information — frontend already sees every event.

**Consequences:** Feed at v0.2.0b shows only frontend-visible events. Internal backend retries on breaker open (e.g., for ROI emit) are not visible.

**Trade-offs:** Lower spec-text fidelity to "gateway's audit" but functionally equivalent at this scope. Migration cost at v0.2.1 (when parallel fan-out per §5.0 lands) is a local Feed component swap — store shape unchanged. Documented in `pending_work.md` as v0.2.1 follow-up.

---

### ADR-004 — HTML5 history router over hash router

**Status:** Accepted

**Context:** CAO view at `/cao/RLS-25-067` is shareable via email/Slack. Hash router would render this as `/#/cao/RLS-25-067` — works but reads as malformed.

**Decision:** HTML5 history API. Gateway serves the SPA shell from `/`. Add catch-all `GET /cao/{rls_id}` returning `index.html` so frontend router takes over (~10 LOC backend change).

**Alternatives considered:**

- **Hash router** — no backend change. Rejected for the URL aesthetics in shared links.
- **Multi-page app** — separate HTML files per panel. Rejected because rls-shell needs one persistent in-memory store across step transitions; multi-page would force serialize/restore per nav.

**Consequences:** Adds one backend route. Browser back/forward buttons "just work" with the stepper. URLs in pilot user emails read clean.

**Trade-offs:** Requires gateway change (small), but the change is mechanical and self-contained.

---

## 11. Risks + mitigations

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Validate response races user typing — stale response overwrites fresh state | High | AbortController per validate request, owned by validator-runner. Cancel previous on new fire. |
| R2 | localStorage schema bumps crash old drafts | Med | `schemaVersion` field; mismatch on hydrate → drop draft + toast. |
| R3 | Same browser, multiple roles → shared localStorage state | Med | Namespace key by upn. |
| R4 | eventLog unbounded growth in long sessions | Low | Cap at 200; drop oldest; show "older events truncated" indicator. |
| R5 | Validator burst on paste-skip (7 fields populated in 50ms) | Med | Trailing-edge debounce (lodash-style); only the last write in a 750ms window fires the call. |
| R6 | 17k-line legacy `index.html` reused inadvertently | Med | Move to `apps/web/static/_archive/` before any new frontend work; add lint rule preventing imports from `_archive/`. |
| R7 | Lit version drift over time creates upgrade pain | Low | Pin version in vendored filename (`lit-3.2.1.min.js`); document SHA256; bump only with explicit ADR. |
| R8 | County brand colors are placeholders, not real Manatee guide | Med | Annotate `_brand-overlay.css` clearly; flag for swap with county style guide before pilot ship. |
| R9 | `manatee-ai-roi` FastAPI not yet on `bcc-ap-llm01` → all ROI events drain to local JSONL forever | Med | Already tracked in `pending_work.md` as highest-leverage. ~30 min RDP. Schedule before v0.2.0b ship. |
| R10 | Aggressive LLM automation pushes p95 latency above NFR §11 target | Low | Trailing debounce + AbortController already minimize call volume. Validator path is rule-based (no LLM in critical path). Re-measure during pilot. |

---

## 12. Non-functional requirements

| NFR | Target | Notes |
|---|---|---|
| Time-to-interactive (cold load) | < 1.5s p95 | Lit + index.html + 9 components ≈ 50KB transferred |
| Validator round-trip (visible) | < 1s p95 | Backend already at this target (NFR §11 of reframe) |
| localStorage write | < 5ms p95 | Native API, debounced; not perf-critical |
| Memory footprint | < 50MB sustained | One 200-entry eventLog, one rlsPayload, no images |
| Concurrent users | 10 | Pilot scale; matches reframe NFR §11 |
| Zero external network egress | required | All assets local; no CDN; no analytics |
| Browser support | Edge 110+ / Chrome 110+ | County standard environment |

---

## 13. Out of scope for v0.2.0b

- Mobile / responsive layout (desktop only)
- Accessibility audit beyond keyboard tab order
- Real precedent corpus retrieval (v0.2.1)
- Real Entra OIDC role gating (v0.2.0a returns hardcoded role; v0.2.0b uses dropdown; v0.2.1 wires JWT)
- `update_rls_status` write tool (v0.2.1)
- Cure path mark-done re-validation (v0.2.1)
- Co-pilot Ask + Metrics tabs (v0.2.1)
- Server-side matter persistence (v0.2.0c)
- Audit log endpoint backed by Postgres (v0.2.0c)
- Internationalization
- Server-Sent Events for live Feed (frontend-tracked event log is sufficient at this scope)
- Service Worker / offline mode
- Multi-matter list view (single matter per browser session)

---

## 14. Deferred work — phase-tagged

### To `writing-plans` (v0.2.0b task breakdown)

| # | Concern | Acceptance criterion |
|---|---|---|
| W1 | Servo screenshot baseline harness | `bash tests/visual/run.sh` produces 7 baselines committed under `tests/visual/baseline/`; pre-commit script (optional) compares; `_brand-overlay.css` annotation flags placeholder colors |
| W2 | localStorage hydrate path with schema-version mismatch handling | Test cases: fresh user, valid v1 draft restored, v0 mismatch dropped + toast, malformed JSON dropped + toast |
| W3 | AbortController wiring in validator-runner | Test: rapid 5x input changes trigger 1 final POST; previous 4 ABORTED tracked via spy |
| W4 | `<cao-view>` route capture in `<rls-shell>` | Test: `window.location.pathname === '/cao/X'` mounts `<cao-view>` not stepper; clicking any decision button shows toast; back button returns to / |
| W5 | Stub `GET /api/cao/brief?rlsId=` endpoint with ROI emit | Test: returns canned brief shape; emit_roi captures workflow="rls_apex.cao_brief"; passes validate_event_for_persistence |
| W6 | Gateway catch-all `GET /cao/{rls_id}` returning index.html | Test: arbitrary rlsId path returns 200 + HTML content-type; static asset paths still resolve correctly |
| W7 | Auto-correct rules suite (subject-trim, title-case, date-infer) | Test per rule: positive trigger, negative trigger, "Apply" button mutates store.draft.rlsPayload, dismiss removes suggestion |

### To `executing-plans` (implementation phase, code-level acceptance)

| # | Concern | Acceptance criterion |
|---|---|---|
| E1 | Smart-surface — fields not in `blurredFields` MUST NOT show inline lint errors | Visual regression test: typing in untouched field shows nothing; click away shows lint |
| E2 | eventLog cap MUST drop oldest, not newest | Test: append 250 events, last 200 are present, first 50 are gone |
| E3 | localStorage namespace per upn — no leak across roles in same browser | Test: switch role in `<app-header>`, draft persists separately per upn key |

---

## 15. Open questions

**OQ-1 — County brand colors**

Manatee County style guide hex values are not in repo. Spec uses placeholders (`#003C71` blue, `#B8861B` gold). Action: confirm with Communications team before pilot ship; swap in `_brand-overlay.css`.

**OQ-2 — `<cao-view>` role gating in v0.2.0b**

Header dropdown sets `session.role` for demo. Real Entra group claim wiring is v0.2.1. For pilot: do we need the URL itself gated (e.g., redirect non-CAO upns away from `/cao/*`)? Current decision: no gating, rely on the dropdown. If pilot users include non-CAO staff, this could leak draft visibility. Action: confirm pilot user list before ship.

**OQ-3 — Auto-correct rule expansion in v0.2.1**

v0.2.0b ships 3 rules (subject-trim, title-case, date-infer). Spec §5.3 implies LLM-driven inline lint that's broader. v0.2.1 adds LLM-driven auto-correct against the policy snippets corpus. Action: design v0.2.1 auto-correct as an LLM call against `get_policy_snippets`.

**OQ-4 — Submit escape hatch (copy-JSON for pilot)**

`<submit-panel>` shows pretty-printed `rlsPayload` JSON with copy-to-clipboard. Pilot users email this to County Attorney as the actual submission. Is the JSON shape friendly enough for a non-technical CAO to read? Action: confirm with one pilot user before ship; consider a "Copy as plaintext form" option that renders fields as labeled paragraphs.

**OQ-5 — Servo on Apple Silicon vs county Windows machines**

Servo screenshots are produced on the dev machine (Apple Silicon Mac). Pilot users run Windows + Edge. Could rendering diverge? Action: spot-check one pilot machine's render against the Servo baseline before ship.

---

## 16. Spec self-review

**Placeholder scan:** No "TBD" or "TODO" outside of explicitly-flagged placeholders (county brand colors in §15 OQ-1). All decisions are made; OQs are honest open items, not deferral excuses.

**Internal consistency:**

- Component graph (§3.1) matches project layout (§3.2) — 9 components named consistently.
- Store shape (§4.1) matches subscriptions (§4.2) — every consumed slice exists.
- Hot-path data flow (§4.3) uses every store slice and module described in §3 + §5.
- Three modules in §5 match the file layout in §3.2 (`core/automation/*`).
- ADR-003 alignment: §6.7 `<copilot-feed>` consumes `store.session.eventLog` (frontend tracked) — consistent.
- ADR-004 alignment: §7.3 includes the gateway catch-all change — consistent.

**Scope check:** focused on 9 components + 4 core modules + 3 automation modules + 1 new endpoint. Single implementation plan can carry this. No further decomposition needed.

**Ambiguity check:** OQ-2 (CAO route gating) is the only requirement that could be interpreted two ways; flagged as open question. Action assigned (confirm pilot list).

---

## 17. Spec ownership

- **This spec** — closed for v0.2.0b architectural shape. Future edits to a new dated spec, not this file.
- **`writing-plans`** — owns W1-W7. Each becomes a v0.2.0b task with bite-sized TDD steps.
- **`executing-plans`** — owns E1-E3. Each becomes a code-level acceptance check during implementation.

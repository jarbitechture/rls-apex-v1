# ROI Emit Contract Hardening — Design Spec

**Date:** 2026-05-08
**Status:** Draft — design only, no implementation
**Branch:** `feat/v0.2.0a-backend` (read-only; do NOT edit production code from this doc)
**Author:** Elliot Jarbe (with Claude as scribe)
**Skills applied:** `superpowers:systematic-debugging`, `architecture-designer`, `circuit-breaker-design`

---

## 1. Phase 1 — Root Cause Findings

### 1.1 Bug 1 — MCP tool emit events are malformed and silently dropped

**Affected paths:** All three MCP tool servers under `mcp_tools/`.

#### 1.1.1 The broken code

`mcp_tools/_lib/roi_emit.py`, lines 42–49:

```python
full_event = {
    "event_kind": event_kind,   # valid: "tool_invocation"
    "tool": self.tool_name,     # INVALID: e.g. "classify_matter"
    "ts": time.time(),          # UNKNOWN FIELD: violates additionalProperties:false
    **payload,                  # missing: workflow, user_id, dept, role_band, task_type
}
```

`ToolRoiEmitter.emit()` builds a 3–5 key dict and POSTs it. No call to
`validate_event_for_persistence()` exists anywhere in this file.

#### 1.1.2 Why it fails schema validation

The Python pre-flight validator (`apps/gateway/sidecar/_client.py`, lines 125–146) requires
exactly these 8 keys:

```
{"event_kind", "workflow", "user_id", "dept", "role_band", "task_type", "tool", "success"}
```

Every tool emit is missing 5 of them: `workflow`, `user_id`, `dept`, `role_band`, `task_type`.

The `tool` field is also wrong. The JSON Schema `Tool` enum (`apps/gateway/sidecar/manatee_ai_roi.schema.json`, v1.2.0) accepts:

```
["copilot", "chatgpt_enterprise", "civic_ai", "cookbook", "rls_pilot", "rls_apex", "other"]
```

`"classify_matter"`, `"validate_rls_structure"`, and `"extract_fields"` are not in that enum.

The extra `ts` key would cause server-side rejection under `additionalProperties: false`, even if the other fields were correct.

#### 1.1.3 The silent drop path

`RoiClient._dispatch()` (`apps/gateway/sidecar/_client.py`, lines 307–323) calls
`validate_event_for_persistence()` before posting. On failure it logs at `DEBUG` level and
returns — no exception, no user-visible signal. The invalid events never reach the
manatee-ai-roi endpoint. They are also not written to the JSONL fallback because the
failure occurs in pre-flight, not in the HTTP call.

However, `ToolRoiEmitter._post()` (in `mcp_tools/_lib/roi_emit.py`) does NOT call
`validate_event_for_persistence()`. It calls `_post()` which POSTs to the ROI endpoint
directly. If the server returns non-2xx (because the payload fails server-side schema
validation), `ToolRoiEmitter` catches the exception and falls back to JSONL — writing the
malformed event to disk. The JSONL drain will later try to POST the same malformed event,
which will be rejected again. This creates an unbounded accumulation of undrainable events
in the fallback queue.

#### 1.1.4 Call-site evidence (all three tools)

**`mcp_tools/classify_matter/server.py`, lines 59–63:**

```python
await roi.emit("tool_invocation", {
    "actor_id": actor.actor_id,
    "success": True,
    "type": result["type"],
})
```

**`mcp_tools/validate_rls_structure/server.py`, lines 95–100:**

```python
await roi.emit("tool_invocation", {
    "actor_id": actor.actor_id,
    "success": True,
    "blocking_count": len(result.blocking),
    "warnings_count": len(result.warnings),
})
```

**`mcp_tools/extract_fields/server.py`, lines 42–45:**

```python
await roi.emit("tool_invocation", {
    "actor_id": actor.actor_id,
    "success": True,
})
```

None of the three call sites supply `workflow`, `user_id`, `dept`, `role_band`, or
`task_type`. All three use an invalid `tool` value via `self.tool_name`.

#### 1.1.5 Why existing tests did not catch this

`tests/test_roi_emit_schema_compliance.py` monkeypatches `apps.gateway.main.emit_roi` and
tests only `/api/intake` and `/api/validate`. The MCP tool `roi.emit()` calls run in
separate processes and are not covered by any test. The test file's module-level docstring
even says "They fail RED against the current call sites" — meaning they were written as TDD
specs for the gateway layer only, not the MCP tool layer.

---

### 1.2 Bug 2 — `/api/query` DEV_MODE path emits no ROI event

**File:** `apps/gateway/main.py`, lines 327–330 and 534–596.

The `/api/query` endpoint has a DEV_MODE branch (lines 327–330):

```python
if settings.DEV_MODE:
    return StreamingResponse(
        _mock_query_stream(question),
        media_type="text/event-stream",
    )
```

`_mock_query_stream()` (lines 534–596) is an async generator that yields SSE frames. It
does yield `prompt_tokens` and `completion_tokens` inside the `done` event frame, but
these are sent to the client only. No `emit_roi()` call exists anywhere in the function.

The production path (lines 330 onward) is gated behind the DEV_MODE flag. In DEV_MODE,
every `/api/query` call is invisible to the ROI sidecar. This violates Operating Rule #18:
every user-facing action must emit a ROI event.

The non-DEV_MODE path was not read in full in Phase 1, but it is outside the scope of this
bug — the spec defers the production LLM query path to v0.2.1+ (LLM integration).
DEV_MODE is what ships in v0.2.0a.

---

### 1.3 ADR-001 pre-finding — `dept` and `role_band` are not in JWT claims

`mcp_tools/_lib/jwt_verify.py`, lines 22–26:

```python
@dataclass
class JwtClaims:
    actor_id: str
    actor_role: str
    tenant: str
    rls_id: str | None = None
```

`dept` and `role_band` are not in the JWT. The gateway user dict (from `current_user()`,
lines 155–190 of `apps/gateway/main.py`) does carry both:

```python
# DEV_MODE: {"sub": "dev-user", "dept": "DEV", "role_band": "professional", ...}
```

MCP tools receive a signed JWT. They can parse `actor_role` but cannot derive `dept` or
`role_band` from the claim set as it stands.

This is the central design decision for Bug 1 remediation. It is addressed in ADR-001
(§2.2 below).

---

### 1.4 Breaker pre-finding — per-process per-tool breaker already exists

`mcp_tools/_lib/roi_emit.py`, lines 31–36:

```python
self._breaker = CircuitBreaker(
    name=f"roi_emit_{tool_name}",
    failure_threshold=5,
    window_seconds=30.0,
    open_duration_seconds=30.0,
)
```

The `/health` endpoint on each tool server (`mcp_tools/_lib/server.py`, lines 67–69)
already surfaces `roi.breaker_status()`. The breaker infrastructure is in place. Phase 2
(§2.4) confirms thresholds and hardens the test surface — it does not redesign the breaker.

---

## 2. Phase 2 — Architecture

### 2.1 Emit topology: current vs. proposed

#### Current (broken)

```mermaid
flowchart TD
    subgraph MCP tools [MCP tool processes]
        CM[classify_matter\nserver.py]
        VR[validate_rls_structure\nserver.py]
        EF[extract_fields\nserver.py]
    end

    subgraph lib [mcp_tools/_lib]
        TRE[ToolRoiEmitter.emit]
    end

    subgraph gateway [apps/gateway]
        GW[/api/intake · /api/validate · /api/query/]
        SC[RoiClient._dispatch]
    end

    ROI[manatee-ai-roi\nFastAPI]
    JSONL[fallback.jsonl]

    CM -->|roi.emit()| TRE
    VR -->|roi.emit()| TRE
    EF -->|roi.emit()| TRE

    TRE -->|POST malformed event\ntool=classify_matter\nmissing 5 fields| ROI
    ROI -->|422 / 400| TRE
    TRE -->|fallback| JSONL

    GW -->|emit_roi()| SC
    SC -->|validate_event_for_persistence\ndrop silently on fail| ROI

    style TRE fill:#f88,stroke:#c00
    style JSONL fill:#f88,stroke:#c00
```

**Problems:**

- `ToolRoiEmitter.emit()` sets `tool=<tool_name>` (not in schema enum)
- `tool=<tool_name>` is rejected server-side; fallback accumulates undrainable JSONL
- No `workflow`, `user_id`, `dept`, `role_band`, `task_type` in any MCP tool emit
- No pre-flight validation in `ToolRoiEmitter`
- `/api/query` DEV_MODE emits nothing
- Extra `ts` field violates `additionalProperties: false`

#### Proposed

```mermaid
flowchart TD
    subgraph MCP tools [MCP tool processes]
        CM[classify_matter\nserver.py]
        VR[validate_rls_structure\nserver.py]
        EF[extract_fields\nserver.py]
    end

    subgraph lib [mcp_tools/_lib]
        TRE[ToolRoiEmitter.emit\n+ validate_event_for_persistence\n+ correct field set]
        EM[ToolEmitConfig\nper-tool defaults]
    end

    subgraph gateway [apps/gateway]
        GW_Q[/api/query DEV_MODE\n+ emit_roi call]
        SC[RoiClient._dispatch\nalready correct]
    end

    ROI[manatee-ai-roi\nFastAPI]
    JSONL[fallback.jsonl\nonly valid events]

    CM -->|roi.emit with full fields| TRE
    VR -->|roi.emit with full fields| TRE
    EF -->|roi.emit with full fields| TRE

    TRE -->|validate_event_for_persistence\npre-flight PASS| ROI
    TRE -->|FAIL pre-flight → raise,\ndon't write to JSONL| CM

    TRE -->|network failure after\nvalid pre-flight| JSONL
    JSONL -->|drain| ROI

    GW_Q -->|emit_roi| SC
    SC --> ROI

    style TRE fill:#8f8,stroke:#060
    style JSONL fill:#8f8,stroke:#060
    style GW_Q fill:#8f8,stroke:#060
```

**Key changes:**

1. `ToolRoiEmitter.emit()` gains a `validate_event_for_persistence()` pre-flight call.
   Invalid events raise immediately (log + re-raise) rather than writing undrainable JSONL.
2. Each tool provides a `ToolEmitConfig` (or call-site kwarg) supplying the missing fields:
   `workflow`, `user_id`, `dept`, `role_band`, `task_type`, `tool="rls_apex"`.
3. `/api/query` DEV_MODE adds an `emit_roi()` call wrapping `_mock_query_stream()`.
4. The extra `ts` field is removed from `full_event`.

---

### 2.2 ADR-001 — Where do `dept` and `role_band` come from in MCP tool context?

**Decision record date:** 2026-05-08
**Status:** Proposed

#### Problem

`validate_event_for_persistence()` requires `dept` and `role_band`. MCP tools receive a
signed JWT whose `JwtClaims` struct has only `actor_id`, `actor_role`, `tenant`, and
`rls_id`. There is no `dept` or `role_band` in the current JWT claim set.

#### Options

| # | Approach | Pros | Cons |
|---|---|---|---|
| A | **Static defaults in ToolRoiEmitter** — hardcode `dept="DEV"`, `role_band="professional"` as constants per tool server | Zero JWT changes, instant fix, matches DEV_MODE reality | Wrong in prod (dept varies by user); fails KPI accuracy at renewal; tech debt in production |
| B | **Extend JWT claim set** — gateway adds `dept` and `role_band` to the RS256 tokens it mints for MCP tools | Accurate per-user; no extra I/O in the tool | Requires JWT issuer change (gateway); MCP tools must parse two new claims; breaking change to `JwtClaims` struct |
| C | **Call-site explicit kwargs** — each tool's `roi.emit()` call passes `dept` and `role_band` from a config dict baked into that tool process at startup | No JWT change; allows per-tool defaults (e.g., all RLS Apex tools = `dept="DEV"`, `role_band="professional"`) | Still not per-user accurate; same limitations as A but structured |
| D | **Pass via MCP invocation context** — gateway embeds dept/role_band in a structured header or MCP call metadata; tool reads from context | Per-user accurate without JWT change | FastMCP 2.3.0 has no middleware; no standard MCP header for this; complex |

#### Decision

**Option C for v0.2.0b, with Option B targeted for v0.2.1.**

Reasoning:

- v0.2.0a and v0.2.0b operate in DEV_MODE exclusively. `dept="DEV"` and
  `role_band="professional"` are factually correct for the development population.
- Option A is identical in practice to C for v0.2.0b but is unstructured and harder to
  replace. Option C structures the defaults so the call-site kwargs are a named constant
  that a later PR can swap for JWT-derived values.
- Option B is the production-correct answer. It should be designed in v0.2.1 when the
  gateway's JWT minting code is touched for MSAL OIDC integration (Lock #5).
- Option D is blocked by FastMCP 2.3.0 constraints (no middleware, no standardized MCP
  header for auth metadata).

#### Implementation contract for C

Each MCP tool server defines:

```python
# At module top, alongside build_tool_app()
_EMIT_DEFAULTS = {
    "tool": "rls_apex",
    "dept": "DEV",          # replaced by JWT claim in v0.2.1
    "role_band": "professional",  # replaced by JWT claim in v0.2.1
}
```

Each `roi.emit()` call passes `user_id=actor.actor_id` from the JWT, plus
`workflow`, `task_type` from the call site, plus `**_EMIT_DEFAULTS`.

#### Migration note for v0.2.1

When JWT minting is extended (Option B), `JwtClaims` gains two fields:

```python
dept: str
role_band: str
```

The `_EMIT_DEFAULTS` dict is removed from each tool server. `ToolRoiEmitter.emit()` reads
`dept` and `role_band` directly from the parsed JWT claims. The call-site kwargs become
optional overrides.

---

### 2.3 ADR-002 — Contract enforcement: how to make schema compliance cheap and reliable

**Decision record date:** 2026-05-08
**Status:** Proposed

#### Problem

Bug 1 persisted undetected through cleanup #17 because:

1. `ToolRoiEmitter.emit()` had no pre-flight validation.
2. The per-task code reviewers saw gateway diffs but never diffed MCP tool emit call sites.
3. No test exercised MCP tool emit paths.

The fix needs to be self-enforcing — new tools must not be able to ship an invalid emit.

#### Options

| # | Approach | Catches at | Cost |
|---|---|---|---|
| A | **Pydantic model at emit()** — `ToolRoiEmitter.emit()` accepts a typed `RoiEvent` Pydantic model; call sites build the model | Construction time (tool process startup) | Medium — all call sites must instantiate the model |
| B | **`validate_event_for_persistence()` pre-flight in emit()** — add the existing validator call before POST | Emit time | Low — one line in `ToolRoiEmitter.emit()` |
| C | **pytest invariant test for each tool** — parametrized test that mocks POST, calls each tool's endpoint, captures the event dict, runs `validate_event_for_persistence()` | CI | Low per tool; must add test per new tool |
| D | **B + C** — pre-flight validation in emit() AND parametrized pytest coverage | Emit time + CI | B + C combined |

#### Decision

**Option D (B + C).**

Reasoning:

- Option B alone catches runtime failures but allows bad events to reach the pre-flight gate
  only at emit time, with no signal at dev time.
- Option C alone means a broken emit is only caught when someone runs the test that covers
  that specific tool — new tools can slip through if the test isn't added.
- Option A (Pydantic model) is a heavier refactor than the v0.2.0b timeline allows. The
  Pydantic model approach should be re-evaluated in v0.3.0 when the full event schema is
  stabilized and shared across gateway + tools via a common package.
- Option D is the minimum viable enforcement: pre-flight catch at runtime (prevents
  undrainable JSONL accumulation) + CI catch (prevents regression on future edits).

#### Pre-flight guard (B) — implementation contract

In `mcp_tools/_lib/roi_emit.py`, `ToolRoiEmitter.emit()`, before building `full_event`:

```python
# Remove ts from full_event construction.
full_event = {
    "event_kind": event_kind,
    "tool": self.tool_name,   # <-- this line is replaced; see ADR-003
    **payload,
}
# Pre-flight validation: raises ValueError on schema violation.
# Invalid events must not enter the fallback queue.
try:
    validate_event_for_persistence(full_event)
except ValueError as exc:
    logger.error("roi_emit pre-flight failed for tool=%s: %s", self.tool_name, exc)
    raise   # let the call site handle; do NOT write to JSONL
```

The `validate_event_for_persistence` import comes from
`apps.gateway.sidecar._client`. Since MCP tools already import from `apps.gateway` (see
`mcp_tools/validate_rls_structure/server.py` line 14), this import is in scope.

**Cross-process import coupling — Option C accepted for v0.2.0b.**

The three options were:

- **(a) Move to shared module** — e.g., `shared/roi_validation.py` imported by both
  `apps.gateway.sidecar._client` and `mcp_tools/_lib/roi_emit.py`. Clean boundary, but
  requires a new package and a refactor of the existing `_client` import chain.
- **(b) Vendor copy** — duplicate `validate_event_for_persistence` into
  `mcp_tools/_lib/`. Risk: two copies diverge silently.
- **(c) Accept the coupling** — `mcp_tools/_lib/roi_emit.py` imports directly from
  `apps.gateway.sidecar._client`. Acceptable because MCP tools already cross this
  boundary (see `validate_rls_structure/server.py:14`). Introduces a layer-boundary
  dependency that should not proliferate.

**Decision: (c) for v0.2.0b.** The coupling is explicit and localized to one import in
`roi_emit.py`. Flag for extraction: in v0.2.1, when the common package structure is
revisited, move `validate_event_for_persistence` (and the `_REQUIRED_KEYS` constant) to
`shared/roi_schema.py` and update both consumers. Add a `# TODO(v0.2.1): move to shared/roi_schema.py` comment on the import line.

#### Parametrized pytest (C) — implementation contract

New test file: `tests/test_mcp_tool_roi_emit_compliance.py`

```python
@pytest.mark.parametrize("tool_module,endpoint,payload", [
    ("mcp_tools.classify_matter.server", "/classify_matter", {"draft_text": "permit denial"}),
    ("mcp_tools.validate_rls_structure.server", "/validate_rls_structure", {"rls_payload": {...}}),
    ("mcp_tools.extract_fields.server", "/extract_fields", {"draft_text": "permit denial"}),
])
async def test_mcp_tool_emit_valid(tool_module, endpoint, payload, monkeypatch):
    calls = []
    import importlib
    mod = importlib.import_module(tool_module)
    monkeypatch.setattr(mod.roi, "_post", lambda e: calls.append(e))
    # POST to tool's FastMCP app directly via httpx.AsyncClient
    # assert calls[0] passes validate_event_for_persistence
    validate_event_for_persistence(calls[0])
```

Exact fixture wiring follows the existing pattern in
`tests/test_roi_emit_schema_compliance.py`. One new test per tool is sufficient.

---

### 2.4 ADR-003 — `tool` field semantics: what does `tool="rls_apex"` mean across MCP tool calls?

**Decision record date:** 2026-05-08
**Status:** Proposed

#### Problem

The JSON Schema `Tool` enum names products, not software components. `"rls_apex"` is the
correct value for every event produced by the RLS Apex v1 application — whether the event
originates from the gateway or from a MCP tool. The MCP tool name (e.g.,
`"classify_matter"`) is not a `Tool` enum value and must not go in the `tool` field.

But the MCP tool name is useful telemetry. Without it, KPI queries cannot distinguish
"intake text was classified by classify_matter" from "a field was extracted by
extract_fields."

#### Decision

`tool="rls_apex"` for all events from all parts of RLS Apex v1.

The MCP tool name goes in `workflow`. `workflow` is an arbitrary string with no enum
constraint. The convention is `<tool_product>.<operation>`, e.g.:

| MCP tool | workflow value | task_type |
|---|---|---|
| classify_matter | `rls_apex.classify_matter` | `data_analysis` |
| validate_rls_structure | `rls_apex.validate_rls_structure` | `validation` |
| extract_fields | `rls_apex.extract_fields` | `data_analysis` |
| /api/intake | `rls_apex.intake` | `data_analysis` |
| /api/validate | `rls_apex.validate` | `validation` |
| /api/query DEV_MODE | `rls_apex.query` | `data_analysis` |

Tool-specific sub-fields (e.g., `blocking_count`, `warnings_count`, `type`) go in `extra`:

```python
await roi.emit("tool_invocation", {
    "workflow": "rls_apex.validate_rls_structure",
    "user_id": actor.actor_id,
    "task_type": "validation",
    **_EMIT_DEFAULTS,               # tool, dept, role_band
    "extra": {
        "blocking_count": len(result.blocking),
        "warnings_count": len(result.warnings),
    },
})
```

This satisfies `additionalProperties: false` at the top level because `extra` is a defined
schema property (confirmed in `manatee_ai_roi.schema.json`).

#### Rationale

The `blocking_count` placement finding from `tests/test_roi_emit_schema_compliance.py`
(lines 93–100) already established this pattern for the gateway:

> "blocking_count must NOT be a top-level key (additionalProperties: false) ... must be
> present under extra."

The same rule applies to all MCP tool sub-fields.

---

### 2.5 Circuit breaker spec — confirm and harden

#### Current state (confirmed from Phase 1 static analysis)

| Property | Value | Source |
|---|---|---|
| Breaker per process | Yes — each tool process has its own `ToolRoiEmitter` | `mcp_tools/_lib/roi_emit.py:31-36` |
| Breaker per tool | Yes — named `roi_emit_<tool_name>` | `mcp_tools/_lib/roi_emit.py:34` |
| `failure_threshold` | 5 | `mcp_tools/_lib/roi_emit.py:35` |
| `window_seconds` | 30.0 | `mcp_tools/_lib/roi_emit.py:35` |
| `open_duration_seconds` | 30.0 | `mcp_tools/_lib/roi_emit.py:36` |
| Single-probe enforcement | Yes — `_probe_in_flight` flag | `apps/gateway/circuit/breaker.py:100-103` |
| `/health` surface | Yes — `roi.breaker_status()` | `mcp_tools/_lib/server.py:67-69` |
| Gateway sidecar breaker | `roi_sidecar`, same thresholds | `apps/gateway/sidecar/_client.py` |

The thresholds match Operating Rule #19 and the spec §12.3 contract. No changes to
thresholds are required.

#### Gap: breaker does not protect from pre-flight failures

With the proposed pre-flight guard (ADR-002 Option B), `validate_event_for_persistence()`
runs before the breaker's `call()` wrapper. A malformed event will raise `ValueError` at
pre-flight, which is correctly caught and re-raised — but the breaker is not tripped
(because no HTTP call was attempted).

This is the correct behavior: the breaker counts network/service failures, not schema
errors. Schema errors are programming mistakes; network failures are operational events.
The two failure modes must not share a counter.

#### Gap: no test covers half-open probe enforcement for tool breakers

`tests/test_sidecar_uses_shared_breaker.py` covers the gateway's `roi_sidecar` breaker.
No test covers the `roi_emit_<tool_name>` breaker in the tool process. The parametrized
test introduced in ADR-002 Option C should include a case that:

1. Forces the breaker open (5 simulated HTTP failures).
2. Verifies a subsequent call raises `BreakerOpenError`.
3. Waits for `open_duration_seconds` (mock monotonic).
4. Verifies the half-open probe is allowed through.

This is a medium-effort test addition (tag: L in §3 table below).

#### `/health` surface — no changes required

`mcp_tools/_lib/server.py` already exposes:

```python
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "roi_breaker": roi.breaker_status()}
```

`CircuitBreaker.status()` returns `name`, `state`, `consecutive_failures`,
`last_failure_ts`, `last_success_ts`. This matches spec §12.4. The gateway's
`/api/health/breakers` endpoint should be extended in v0.2.1 to aggregate tool `/health`
responses — the design for that aggregation is out of scope for this spec.

---

## 3. Phase 3 — Deferred Work Table

| # | Work item | Tag | Effort | Acceptance criteria |
|---|---|---|---|---|
| W1 | Fix `ToolRoiEmitter.emit()`: remove `ts`, add pre-flight guard, enforce field contract | `executing-plans` | S | `validate_event_for_persistence(full_event)` passes for all three tool call sites; no `ts` key in emitted event |
| W2 | Fix all three MCP tool emit call sites: add `workflow`, `user_id`, `dept`, `role_band`, `task_type`, `tool="rls_apex"`, move sub-fields to `extra` | `executing-plans` | S | Each tool emit passes pre-flight; `blocking_count`/`warnings_count` are under `extra`, not top-level |
| W3 | Add `_EMIT_DEFAULTS` constant to each tool server (ADR-001 Option C) | `executing-plans` | S | Constant defined at module level; call sites use it; `dept="DEV"`, `role_band="professional"` |
| W4 | Fix `/api/query` DEV_MODE: add `emit_roi()` call in `_mock_query_stream` path | `executing-plans` | S | A test POST to `/api/query` in DEV_MODE captures exactly one `emit_roi` call that passes `validate_event_for_persistence` |
| W5 | Add `tests/test_mcp_tool_roi_emit_compliance.py`: parametrized emit compliance tests for all three tools (ADR-002 Option C) | `writing-plans` | M | 3 passing tests; each captures the event dict and calls `validate_event_for_persistence(event)` |
| W6 | Extend breaker tests to cover `roi_emit_<tool_name>` breaker: open → half-open probe → closed (§2.5) | `writing-plans` | L | Test uses mocked monotonic clock; verifies `BreakerOpenError` in OPEN state; verifies probe allowed in HALF_OPEN; verifies CLOSED on probe success |
| W7 | Extend JWT claim set with `dept` and `role_band` (ADR-001 Option B target for v0.2.1) | `writing-plans` | M | `JwtClaims` gains two fields; gateway mints them; MCP tools parse them; `_EMIT_DEFAULTS` removed |
| W8 | Aggregate tool `/health` responses in gateway `/api/health/breakers` (§2.5) | `writing-plans` | M | Gateway health response includes per-tool breaker states; all three tool servers are polled |
| W9 | Wrap each MCP tool body in try/except; emit `success=False` before re-raising on unhandled exception (see OQ-4) | `executing-plans` | S | Each `@app.tool` function catches unhandled exceptions, fires `roi.emit("tool_invocation", {..., "success": False})`, then re-raises; parametrized compliance test (W5) asserts a `success=False` event on injected failure |
| W10 | Implement dead-letter JSONL in fallback drain: 4xx responses are permanent failures (see OQ-1) | `writing-plans` | M | Drain loop distinguishes 4xx (schema/auth error — not retriable) from 5xx/network (retriable); permanent failures are written to `dead_letter.jsonl` adjacent to `fallback.jsonl`; retried records are never written to dead-letter |

---

## 4. Open Questions

**OQ-1 — JSONL drain behavior for pre-existing malformed events** *(resolved → W10)*

The fallback JSONL queue may already contain malformed events from `ToolRoiEmitter` calls
that ran before W1/W2 are deployed. The drain loop will attempt to POST these events and
receive 4xx responses from the manatee-ai-roi server. What should the drain do on
permanent failure (4xx as opposed to 5xx/network)?

**Resolved:** treat 4xx as undrainable (schema error is not retriable); log at WARN; move
the record to `dead_letter.jsonl` rather than retrying indefinitely. Implementation tracked
as W10.

**OQ-2 — task_type value for `/api/query`**

The proposed workflow for the query path is `rls_apex.query`. The task_type candidates are
`data_analysis`, `llm_call`, or `validation`. In DEV_MODE, `_mock_query_stream` returns
canned text — it is not an LLM call. `data_analysis` is the closest fit. When the
production LLM path is implemented in v0.2.1, `task_type` should become `llm_call` and
`prompt_tokens`/`output_tokens` should be emitted from the streaming response `done` event.

**OQ-3 — actor_id trust in MCP tool context**

ADR-001 chose to take `user_id` from `actor.actor_id` (the JWT `actor_id` claim). The
JWT is signed by the gateway (RS256). `require_actor()` verifies the signature. This is
correct per spec §D1. However, if the gateway ever allows anonymous/DEV_MODE calls without
a JWT, `require_actor()` will raise before the emit is attempted. The emit will never fire
for unauthenticated tool calls. This is the correct behavior — an unauthenticated tool
call should not be counted in ROI telemetry as attributed to a real user.

**OQ-4 — `success=False` path** *(resolved → W9)*

All three tool emit call sites hardcode `success=True`. If the tool function raises before
the emit, no `success=False` event is emitted. The current pattern from the gateway
endpoints handles this with try/except and a separate emit on the error path. The MCP tool
servers have no equivalent.

**Resolved:** W9 adds a `try/except` wrapper around the tool body in each `@app.tool`
function; on unhandled exception a `success=False` emit fires before re-raising. W5's
parametrized compliance test is extended to assert this behavior.

---

## 5. Summary

Two confirmed bugs, one design gap, no runtime proof needed:

| Item | File(s) | Fix scope |
|---|---|---|
| Bug 1 — malformed MCP tool events | `mcp_tools/_lib/roi_emit.py`, all three tool servers | W1, W2, W3, W5 |
| Bug 2 — no emit in `/api/query` DEV_MODE | `apps/gateway/main.py:327-330`, `_mock_query_stream` | W4 |
| ADR-001 — dept/role_band not in JWT | `mcp_tools/_lib/jwt_verify.py` | W3 (v0.2.0b), W7 (v0.2.1) |

All W1–W4 items are `S` effort. No architectural changes are required to the gateway, the
breaker library, or the manatee-ai-roi schema. The fixes are localized to
`mcp_tools/_lib/roi_emit.py`, the three tool server files, and one gateway endpoint
function.

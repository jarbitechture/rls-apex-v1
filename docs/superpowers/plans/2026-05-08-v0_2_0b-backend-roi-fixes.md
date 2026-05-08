# v0.2.0b Backend — ROI Emit Contract Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Operating Rule #18 compliance gap in the three MCP tool emitters (`classify_matter`, `validate_rls_structure`, `extract_fields`) and the gateway's `/api/query` DEV_MODE path, by enforcing the schema contract at every emit boundary.

**Architecture:** Two-layer fix. Layer 1: `ToolRoiEmitter.emit()` gains a pre-flight `validate_event_for_persistence` guard and stops adding the non-schema `ts` field. Layer 2: each tool server defines an `_EMIT_DEFAULTS` constant (per ADR-001 Option C from the contract hardening design), updates its emit call site to provide all 8 required fields with `tool="rls_apex"` and `workflow="rls_apex.mcp.<tool_name>"`, moves sub-fields under `extra`, and wraps the tool body in `try/except` so a `success=False` event fires before a re-raise on unhandled exceptions. A parametrized compliance test enforces the contract across all three tools. `/api/query` DEV_MODE adds an emit modeled on `/api/agent/{kind}`.

**Tech Stack:** Python 3.12, pytest 8.3, FastAPI 0.115, Pydantic 2.9, fastmcp 2.3 (no DB schema changes in this plan).

**Out of scope (separate plans):**
- Track A — vanilla-JS frontend panels (separate plan: `2026-05-08-v0_2_0b-frontend.md`)
- Track C — matter persistence + audit log endpoint (deferred to v0.2.0c; needs §15 W1 atomic-write design)
- v0.2.1 W7 — extend JWT claims with `dept`/`role_band` (removes `_EMIT_DEFAULTS` placeholders; phase after this plan)

**Reference docs:**
- `docs/superpowers/specs/2026-05-08-rls-apex-mcp-reframe-design.md` (canonical spec)
- `docs/superpowers/specs/2026-05-08-roi-emit-contract-hardening-design.md` (Phase 1 root cause + ADRs + breaker spec)

**Baseline:** branch `feat/v0.2.0a-backend` at HEAD `6e5c583`. 51 tests pass under `.venv/bin/python -m pytest`. After this plan: 7 new tests added, 58 total passing.

---

## File Structure

| Path | Action | Responsibility |
|---|---|---|
| `mcp_tools/_lib/roi_emit.py` | Modify | Add pre-flight `validate_event_for_persistence` guard; remove non-schema `ts` field. |
| `mcp_tools/classify_matter/server.py` | Modify | Define `_EMIT_DEFAULTS`; update emit call site; wrap tool body in try/except. |
| `mcp_tools/validate_rls_structure/server.py` | Modify | Same pattern (W2 + W3 + W9). |
| `mcp_tools/extract_fields/server.py` | Modify | Same pattern (W2 + W3 + W9). |
| `apps/gateway/main.py` | Modify | `/api/query` DEV_MODE path adds emit_roi after stream completion (W4). |
| `tests/test_tool_roi_emitter_preflight.py` | Create | Unit tests for `ToolRoiEmitter` — guard rejects malformed event; no `ts` set. |
| `tests/test_mcp_tool_roi_emit_compliance.py` | Create | Parametrized over 3 tools — happy-path emit passes `validate_event_for_persistence`; injected exception emits `success=False`. |
| `tests/test_query_dev_mode_emit.py` | Create | POST `/api/query` in DEV_MODE captures one emit with `workflow="rls_apex.query"`. |

---

## Task 1: ToolRoiEmitter pre-flight guard + remove `ts` (W1)

**Files:**
- Modify: `mcp_tools/_lib/roi_emit.py`
- Create: `tests/test_tool_roi_emitter_preflight.py`

- [ ] **Step 1: Read current emitter**

```bash
cat mcp_tools/_lib/roi_emit.py
```

Confirm `emit()` builds `full_event` with `event_kind`, `tool=self.tool_name`, `ts=time.time()`, then merges `**payload`. Confirm there is no `validate_event_for_persistence` call. The `ts` field violates `additionalProperties: false`.

- [ ] **Step 2: Write the failing test**

Create `tests/test_tool_roi_emitter_preflight.py`:

```python
"""W1 — ToolRoiEmitter must validate events pre-flight and stop adding non-schema fields."""
from __future__ import annotations

import pytest

from mcp_tools._lib.roi_emit import ToolRoiEmitter


@pytest.mark.asyncio
async def test_emitter_rejects_event_missing_required_fields():
    """Pre-flight guard raises ValueError when emitting an event lacking required schema fields."""
    emitter = ToolRoiEmitter(tool_name="classify_matter")
    # Payload is missing workflow, user_id, dept, role_band, task_type, success.
    incomplete_payload = {"actor_id": "test@manatee.local"}
    with pytest.raises(ValueError, match="missing required fields"):
        await emitter.emit("tool_invocation", incomplete_payload)


@pytest.mark.asyncio
async def test_emitter_does_not_add_ts_field(monkeypatch):
    """Schema additionalProperties: false rejects 'ts'; emitter must not add it."""
    captured: list[dict] = []

    async def _fake_post(self, event):
        captured.append(event)

    monkeypatch.setattr(ToolRoiEmitter, "_post", _fake_post)
    emitter = ToolRoiEmitter(tool_name="classify_matter")
    full_payload = {
        "workflow": "rls_apex.mcp.classify_matter",
        "user_id": "test@manatee.local",
        "dept": "DEV",
        "role_band": "professional",
        "task_type": "data_analysis",
        "tool": "rls_apex",
        "success": True,
    }
    await emitter.emit("tool_invocation", full_payload)
    assert captured, "emit() did not call _post"
    assert "ts" not in captured[0], f"emitter still adds 'ts': {captured[0]!r}"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_tool_roi_emitter_preflight.py -v
```

Expected: 2 FAILED.
- `test_emitter_rejects_event_missing_required_fields` fails because `emit()` does not call any validator and swallows the missing fields.
- `test_emitter_does_not_add_ts_field` fails because `full_event` still contains `ts`.

- [ ] **Step 4: Patch `mcp_tools/_lib/roi_emit.py`**

Add the import at the top of the file (after the existing `from apps.gateway.circuit import ...`):

```python
from apps.gateway.sidecar._client import validate_event_for_persistence
```

Replace the `emit` method's `full_event` construction and pre-call block. The new `emit` body:

```python
    async def emit(self, event_kind: str, payload: dict[str, Any]) -> None:
        """Fire-and-forget — never raises on dispatch failure, but raises ValueError pre-flight
        if the event would not satisfy validate_event_for_persistence."""
        full_event = {
            "event_kind": event_kind,
            "tool": self.tool_name,
            **payload,  # call site overrides 'tool' with "rls_apex" per ADR-003
        }
        validate_event_for_persistence(full_event)
        try:
            await self._breaker.call(lambda: self._post(full_event))
        except BreakerOpenError:
            self._fallback(full_event)
        except Exception:
            self._fallback(full_event)
```

Note: the `ts` line is removed entirely. The `tool` line is retained for backward compatibility — call sites supply `"tool": "rls_apex"` in their payload, which overrides via the `**payload` spread (Python dict literal evaluation order).

- [ ] **Step 5: Run test to verify it passes**

```bash
.venv/bin/python -m pytest tests/test_tool_roi_emitter_preflight.py -v
```

Expected: 2 PASSED.

- [ ] **Step 6: Run full suite — no regressions**

```bash
.venv/bin/python -m pytest -q
```

Expected: `53 passed` (51 baseline + 2 new). If ANY existing test now fails (e.g., a test that was relying on `ts` being present), STOP and report — that's a downstream consumer of the deprecated field.

- [ ] **Step 7: Commit**

```bash
git add tests/test_tool_roi_emitter_preflight.py mcp_tools/_lib/roi_emit.py
git commit -m "feat(roi): pre-flight validate guard + drop unschema'd ts field in ToolRoiEmitter (W1)"
```

---

## Task 2: Parametrized compliance test scaffold (W5, RED-only)

This task creates the test that will RED for all three tools. Tasks 3-5 each turn one parametrization GREEN.

**Files:**
- Create: `tests/test_mcp_tool_roi_emit_compliance.py`

- [ ] **Step 1: Write the parametrized compliance test**

Create `tests/test_mcp_tool_roi_emit_compliance.py`:

```python
"""W5 — every MCP tool emit passes validate_event_for_persistence (happy + failure paths).

Parametrized over the three v0.2.0a tools. Tasks 3-5 turn each parametrization green
by adding _EMIT_DEFAULTS + updating the emit call site + wrapping body in try/except.
"""
from __future__ import annotations

import pytest

from apps.gateway.sidecar._client import validate_event_for_persistence
from mcp_tools._lib.roi_emit import ToolRoiEmitter


@pytest.fixture
def capture_emitter(monkeypatch):
    """Replace ToolRoiEmitter._post with a list collector. Returns the list."""
    captured: list[dict] = []

    async def _fake_post(self, event):
        captured.append(event)

    monkeypatch.setattr(ToolRoiEmitter, "_post", _fake_post)
    return captured


# Each tuple: (tool_module_path, helper_name, tool_name, sample_input, expected_workflow)
# - helper_name: pure function used by the tool's @app.tool body (target of monkeypatch in failure-path test)
# - tool_name:   the @app.tool-decorated function name (called directly in both tests)
_TOOL_CASES = [
    (
        "mcp_tools.classify_matter.server",
        "classify_text",
        "classify_matter",
        "Need legal review on a permit denial",
        "rls_apex.mcp.classify_matter",
    ),
    (
        "mcp_tools.validate_rls_structure.server",
        "validate_dict",
        "validate_rls_structure",
        {"type": "Advisory", "title": "Test", "department": "County Attorney"},
        "rls_apex.mcp.validate_rls_structure",
    ),
    (
        "mcp_tools.extract_fields.server",
        "extract_text",
        "extract_fields",
        "Need legal review on parcel 12345",
        "rls_apex.mcp.extract_fields",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module_path,helper_name,tool_name,sample_input,expected_workflow", _TOOL_CASES
)
async def test_tool_emit_satisfies_schema(
    module_path, helper_name, tool_name, sample_input, expected_workflow,
    capture_emitter, monkeypatch
):
    """Calling the MCP tool under DEV_MODE emits one event that passes validate_event_for_persistence."""
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")

    import importlib
    mod = importlib.import_module(module_path)

    # Each tool exposes both an internal helper (e.g., classify_text) and an @app.tool decorated
    # function (e.g., classify_matter). We invoke the @app.tool wrapper because the emit lives there.
    tool_fn = getattr(mod, tool_name)

    if isinstance(sample_input, dict):
        await tool_fn(sample_input)
    else:
        await tool_fn(sample_input)

    assert capture_emitter, f"no emit captured for {module_path}"
    event = capture_emitter[0]
    validate_event_for_persistence(event)
    assert event["workflow"] == expected_workflow
    assert event["tool"] == "rls_apex"
    assert event["dept"] == "DEV"
    assert event["role_band"] == "professional"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module_path,helper_name,tool_name,sample_input,expected_workflow", _TOOL_CASES
)
async def test_tool_emit_fires_success_false_on_unhandled_exception(
    module_path, helper_name, tool_name, sample_input, expected_workflow,
    capture_emitter, monkeypatch
):
    """W9 — tool body try/except: unhandled exception in tool body emits success=False before re-raising."""
    monkeypatch.setenv("DEV_AUTH_BYPASS", "1")

    import importlib
    mod = importlib.import_module(module_path)

    # Force the tool's underlying helper to raise.
    monkeypatch.setattr(mod, helper_name, lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom")))

    tool_fn = getattr(mod, tool_name)

    with pytest.raises(RuntimeError, match="boom"):
        if isinstance(sample_input, dict):
            await tool_fn(sample_input)
        else:
            await tool_fn(sample_input)

    assert capture_emitter, "no emit captured on exception path"
    event = capture_emitter[-1]
    assert event["success"] is False, f"expected success=False on exception, got {event!r}"
    validate_event_for_persistence(event)
```

- [ ] **Step 2: Run the test — confirm RED for all three parametrizations on both happy + exception paths**

```bash
.venv/bin/python -m pytest tests/test_mcp_tool_roi_emit_compliance.py -v
```

Expected: 6 FAILED (3 tools × 2 paths each). Failure mode is `ValueError: missing required fields` for the happy-path test on each tool, and either the same OR an `AttributeError`/`AssertionError` on the exception-path test depending on tool wiring.

If you see something OTHER than missing-field failures (e.g., import errors, fixture errors), STOP — the test scaffold is broken; fix scaffold before continuing.

- [ ] **Step 3: Commit the failing test (RED commit)**

```bash
git add tests/test_mcp_tool_roi_emit_compliance.py
git commit -m "test(roi): parametrized MCP tool emit compliance (W5, RED)"
```

This commit lands a failing test on purpose. Tasks 3-5 turn it green parametrization-by-parametrization.

---

## Task 3: classify_matter — _EMIT_DEFAULTS + call site + try/except (W3 + W2 + W9 for one tool)

**Files:**
- Modify: `mcp_tools/classify_matter/server.py`

- [ ] **Step 1: Read current emit call site**

```bash
sed -n '50,70p' mcp_tools/classify_matter/server.py
```

Current shape:

```python
@app.tool()
async def classify_matter(text: str) -> dict:
    actor = require_actor()
    result = classify_text(text)
    await roi.emit("tool_invocation", {
        "actor_id": actor.actor_id,
        "success": True,
        "type": result["type"],
    })
    return result
```

Issues: payload missing 5 required fields; `actor_id` should be `user_id`; `type` is non-schema (additionalProperties: false) — must move under `extra`. Tool field defaults to `tool_name="classify_matter"` (not in enum).

- [ ] **Step 2: Confirm parametrized test fails on classify_matter case**

```bash
.venv/bin/python -m pytest "tests/test_mcp_tool_roi_emit_compliance.py::test_tool_emit_satisfies_schema[mcp_tools.classify_matter.server-classify_text-Need legal review on a permit denial-rls_apex.mcp.classify_matter]" -v
```

Expected: FAIL with `ValueError: missing required fields: ['dept', 'role_band', 'task_type', 'workflow']`.

- [ ] **Step 3: Define `_EMIT_DEFAULTS` and update the emit call site + wrap in try/except**

Edit `mcp_tools/classify_matter/server.py`. Add after the existing `app, roi, require_actor = build_tool_app("classify_matter")` line (around line 14):

```python
_EMIT_DEFAULTS = {
    "workflow": "rls_apex.mcp.classify_matter",
    "tool": "rls_apex",
    "task_type": "data_analysis",
    # Placeholder values until JWT claims carry dept + role_band (v0.2.1 W7).
    "dept": "DEV",
    "role_band": "professional",
}
```

Replace the `@app.tool()` body (around lines 55-65) with:

```python
@app.tool()
async def classify_matter(text: str) -> dict:
    actor = require_actor()  # D1 contract: every tool calls require_actor() at top
    try:
        result = classify_text(text)
    except Exception:
        await roi.emit("tool_invocation", {
            **_EMIT_DEFAULTS,
            "user_id": actor.actor_id,
            "success": False,
        })
        raise
    await roi.emit("tool_invocation", {
        **_EMIT_DEFAULTS,
        "user_id": actor.actor_id,
        "success": True,
        "extra": {"type": result["type"]},
    })
    return result
```

Key changes: `_EMIT_DEFAULTS` spread provides workflow/tool/task_type/dept/role_band. `actor_id` becomes `user_id`. `type` moves under `extra`. The tool body is wrapped in try/except so an unhandled exception in `classify_text` fires a `success=False` event before re-raising.

- [ ] **Step 4: Run the parametrized test for classify_matter — confirm GREEN on both paths**

```bash
.venv/bin/python -m pytest "tests/test_mcp_tool_roi_emit_compliance.py::test_tool_emit_satisfies_schema[mcp_tools.classify_matter.server-classify_text-Need legal review on a permit denial-rls_apex.mcp.classify_matter]" -v
.venv/bin/python -m pytest "tests/test_mcp_tool_roi_emit_compliance.py::test_tool_emit_fires_success_false_on_unhandled_exception[mcp_tools.classify_matter.server-classify_text-Need legal review on a permit denial-rls_apex.mcp.classify_matter]" -v
```

Expected: both PASS. The other two tools' parametrizations remain RED — that is correct.

- [ ] **Step 5: Run the full suite — confirm no regressions**

```bash
.venv/bin/python -m pytest -q
```

Expected: 4 of the 6 parametrized cases still fail (validate_rls_structure × 2 + extract_fields × 2). All other 53 tests pass.

- [ ] **Step 6: Commit**

```bash
git add mcp_tools/classify_matter/server.py
git commit -m "feat(roi): classify_matter emit contract — _EMIT_DEFAULTS + success=False on raise (W2/W3/W9)"
```

---

## Task 4: validate_rls_structure — same pattern

**Files:**
- Modify: `mcp_tools/validate_rls_structure/server.py`

- [ ] **Step 1: Read current emit call site**

```bash
sed -n '85,105p' mcp_tools/validate_rls_structure/server.py
```

Current shape:

```python
@app.tool()
async def validate_rls_structure(rls_payload: dict) -> dict:
    actor = require_actor()
    result = validate_dict(rls_payload)
    await roi.emit("tool_invocation", {
        "actor_id": actor.actor_id,
        "success": True,
        "blocking_count": len(result.blocking),
        "warnings_count": len(result.warnings),
    })
    return result.model_dump()
```

- [ ] **Step 2: Confirm parametrized test fails on validate_rls_structure case**

```bash
.venv/bin/python -m pytest tests/test_mcp_tool_roi_emit_compliance.py -v -k validate_rls_structure
```

Expected: 2 FAILED.

- [ ] **Step 3: Define `_EMIT_DEFAULTS` + update emit call site + try/except**

Edit `mcp_tools/validate_rls_structure/server.py`. Add after `app, roi, require_actor = build_tool_app("validate_rls_structure")` (around line 23):

```python
_EMIT_DEFAULTS = {
    "workflow": "rls_apex.mcp.validate_rls_structure",
    "tool": "rls_apex",
    "task_type": "validation",
    # Placeholder values until JWT claims carry dept + role_band (v0.2.1 W7).
    "dept": "DEV",
    "role_band": "professional",
}
```

Replace the `@app.tool()` body:

```python
@app.tool()
async def validate_rls_structure(rls_payload: dict) -> dict:
    actor = require_actor()
    try:
        result = validate_dict(rls_payload)
    except Exception:
        await roi.emit("tool_invocation", {
            **_EMIT_DEFAULTS,
            "user_id": actor.actor_id,
            "success": False,
        })
        raise
    await roi.emit("tool_invocation", {
        **_EMIT_DEFAULTS,
        "user_id": actor.actor_id,
        "success": True,
        "extra": {
            "blocking_count": len(result.blocking),
            "warnings_count": len(result.warnings),
        },
    })
    return result.model_dump()
```

- [ ] **Step 4: Run the parametrized test for this tool — confirm GREEN**

```bash
.venv/bin/python -m pytest tests/test_mcp_tool_roi_emit_compliance.py -v -k validate_rls_structure
```

Expected: 2 PASSED.

- [ ] **Step 5: Run full suite — confirm only extract_fields parametrizations remain red**

```bash
.venv/bin/python -m pytest -q
```

Expected: 2 failures remain (extract_fields × 2 paths). Other 55 tests pass.

- [ ] **Step 6: Commit**

```bash
git add mcp_tools/validate_rls_structure/server.py
git commit -m "feat(roi): validate_rls_structure emit contract — _EMIT_DEFAULTS + success=False on raise (W2/W3/W9)"
```

---

## Task 5: extract_fields — same pattern

**Files:**
- Modify: `mcp_tools/extract_fields/server.py`

- [ ] **Step 1: Read current emit call site**

```bash
sed -n '35,50p' mcp_tools/extract_fields/server.py
```

Current shape (inferred from grep):

```python
@app.tool()
async def extract_fields(text: str) -> dict:
    actor = require_actor()
    result = extract_text(text)
    await roi.emit("tool_invocation", {
        "actor_id": actor.actor_id,
        "success": True,
        ...
    })
    return result
```

If the actual file diverges, follow the same shape adjustment as Tasks 3 and 4.

- [ ] **Step 2: Confirm test fails for extract_fields**

```bash
.venv/bin/python -m pytest tests/test_mcp_tool_roi_emit_compliance.py -v -k extract_fields
```

Expected: 2 FAILED.

- [ ] **Step 3: Define `_EMIT_DEFAULTS` + update call site + try/except**

Edit `mcp_tools/extract_fields/server.py`. Add after `app, roi, require_actor = build_tool_app("extract_fields")` (around line 17):

```python
_EMIT_DEFAULTS = {
    "workflow": "rls_apex.mcp.extract_fields",
    "tool": "rls_apex",
    "task_type": "data_analysis",
    # Placeholder values until JWT claims carry dept + role_band (v0.2.1 W7).
    "dept": "DEV",
    "role_band": "professional",
}
```

Replace the `@app.tool()` body:

```python
@app.tool()
async def extract_fields(text: str) -> dict:
    actor = require_actor()
    try:
        result = extract_text(text)
    except Exception:
        await roi.emit("tool_invocation", {
            **_EMIT_DEFAULTS,
            "user_id": actor.actor_id,
            "success": False,
        })
        raise
    await roi.emit("tool_invocation", {
        **_EMIT_DEFAULTS,
        "user_id": actor.actor_id,
        "success": True,
        "extra": {
            # Whatever sub-fields the tool's old emit had — move them here, not top-level.
            # Adjust this dict to match the tool's actual result keys.
        },
    })
    return result
```

If the original emit had no extra sub-fields beyond `actor_id`/`success`, the `"extra"` key can be omitted entirely. The schema permits `extra` to be absent.

- [ ] **Step 4: Run extract_fields parametrization — confirm GREEN**

```bash
.venv/bin/python -m pytest tests/test_mcp_tool_roi_emit_compliance.py -v -k extract_fields
```

Expected: 2 PASSED.

- [ ] **Step 5: Run full suite — entire compliance test now green**

```bash
.venv/bin/python -m pytest -q
```

Expected: `57 passed` (53 baseline + 6 from Task 2 + already-tracked count adjustments). All 6 parametrized compliance cases pass.

- [ ] **Step 6: Commit**

```bash
git add mcp_tools/extract_fields/server.py
git commit -m "feat(roi): extract_fields emit contract — _EMIT_DEFAULTS + success=False on raise (W2/W3/W9)"
```

---

## Task 6: `/api/query` DEV_MODE emit_roi (W4)

**Files:**
- Modify: `apps/gateway/main.py`
- Create: `tests/test_query_dev_mode_emit.py`

- [ ] **Step 1: Read the current `/api/query` DEV_MODE branch + `_mock_query_stream`**

```bash
sed -n '312,335p' apps/gateway/main.py
sed -n '534,580p' apps/gateway/main.py
```

Confirm the current handler returns `StreamingResponse(_mock_query_stream(...))` without an `emit_roi` call. The mock stream itself emits SSE `done` events with `prompt_tokens`/`output_tokens` but never calls `emit_roi`.

- [ ] **Step 2: Write the failing test**

Create `tests/test_query_dev_mode_emit.py`:

```python
"""W4 — /api/query in DEV_MODE must emit one ROI event after the stream completes."""
from __future__ import annotations

import pytest

from apps.gateway.sidecar._client import validate_event_for_persistence


@pytest.fixture
def capture_emit_roi(monkeypatch):
    """Replace apps.gateway.main.emit_roi with a list collector."""
    captured: list[dict] = []

    def _fake_emit(event: dict) -> None:
        captured.append(event)

    import apps.gateway.main as gw_main
    monkeypatch.setattr(gw_main, "emit_roi", _fake_emit)
    return captured


@pytest.mark.asyncio
async def test_query_dev_mode_emits_roi_event(client, capture_emit_roi):
    """POST /api/query (DEV_MODE) emits exactly one persistable ROI event with workflow=rls_apex.query."""
    async with client.stream("POST", "/api/query", json={"q": "permit denial"}) as resp:
        assert resp.status_code == 200
        async for _ in resp.aiter_bytes():
            pass  # drain stream

    assert len(capture_emit_roi) == 1, (
        f"expected exactly 1 emit_roi call, got {len(capture_emit_roi)}: {capture_emit_roi!r}"
    )
    event = capture_emit_roi[0]
    validate_event_for_persistence(event)
    assert event["workflow"] == "rls_apex.query"
    assert event["tool"] == "rls_apex"
```

- [ ] **Step 3: Run test — confirm RED**

```bash
.venv/bin/python -m pytest tests/test_query_dev_mode_emit.py -v
```

Expected: FAIL with `expected exactly 1 emit_roi call, got 0`.

- [ ] **Step 4: Add the emit to `/api/query` DEV_MODE path**

Edit `apps/gateway/main.py`. Locate the `/api/query` handler (around line 312). Replace the DEV_MODE branch:

```python
    if DEV_MODE:
        body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        question = (body.get("q") or "").strip() or "general procurement question"

        async def _wrapped_stream():
            t0 = time.perf_counter()
            prompt_tokens = 0
            output_tokens = 0
            try:
                async for chunk in _mock_query_stream(question):
                    yield chunk
                    # Look for the SSE `done` event to capture token counts; tolerate parse failure.
                    if b'event: done' in chunk:
                        try:
                            data_line = next(
                                l for l in chunk.split(b"\n") if l.startswith(b"data: ")
                            )
                            done_payload = json.loads(data_line[len(b"data: "):])
                            prompt_tokens = int(done_payload.get("prompt_tokens", 0))
                            output_tokens = int(done_payload.get("output_tokens", 0))
                        except (StopIteration, ValueError, KeyError, json.JSONDecodeError):
                            pass
            finally:
                duration_s = round(time.perf_counter() - t0, 3)
                emit_roi({
                    "event_kind": "llm_call",
                    "workflow": "rls_apex.query",
                    "tool": "rls_apex",
                    "user_id": user.get("upn", "unknown"),
                    "dept": user.get("dept", "DEV"),
                    "role_band": user.get("role_band", "professional"),
                    "task_type": "data_analysis",
                    "prompt_tokens": prompt_tokens,
                    "output_tokens": output_tokens,
                    "duration_s": duration_s,
                    "success": True,
                })

        return StreamingResponse(_wrapped_stream(), media_type="text/event-stream")
```

The wrapper streams from `_mock_query_stream` unchanged, captures token counts from the SSE `done` event, and emits a single ROI event in `finally` (so a client disconnect mid-stream still records the action). `task_type="data_analysis"` is a placeholder; v0.2.1 swaps to `llm_call`-task-type when the real LLM path lands (per OQ-2 in the contract hardening design).

- [ ] **Step 5: Run test — confirm GREEN**

```bash
.venv/bin/python -m pytest tests/test_query_dev_mode_emit.py -v
```

Expected: PASS.

- [ ] **Step 6: Run full suite — confirm 58 passed**

```bash
.venv/bin/python -m pytest -q
```

Expected: `58 passed` (57 from Task 5 + 1 new). If any existing `/api/query`-touching test fails (e.g., a test that assumed exactly N SSE events), STOP and inspect — the wrapper should be transparent to clients but does add one outer try/finally.

- [ ] **Step 7: Commit**

```bash
git add tests/test_query_dev_mode_emit.py apps/gateway/main.py
git commit -m "feat(roi): /api/query DEV_MODE emits ROI event with token capture (W4)"
```

---

## Task 7: Final regression sweep + clean-install verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full suite once more from a clean state**

```bash
.venv/bin/python -m pytest -q
```

Expected: `58 passed`.

- [ ] **Step 2: Re-run clean-install verification (mirrors cleanup #17 Task 3)**

```bash
python3.12 -m venv .venv2
.venv2/bin/pip install --upgrade pip
.venv2/bin/pip install -r apps/gateway/requirements.txt
.venv2/bin/python -m pytest -q
rm -rf .venv2
```

Expected: `58 passed` from a fresh venv. If install fails on a missing package, add the package to `apps/gateway/requirements.txt` with the version `.venv` reports via `.venv/bin/pip show <pkg>`, commit separately, and re-run.

- [ ] **Step 3: Confirm git log shape**

```bash
git log --oneline -10
```

Expected (newest first): six commits since `6e5c583`:
- `feat(roi): /api/query DEV_MODE emits ROI event with token capture (W4)`
- `feat(roi): extract_fields emit contract …`
- `feat(roi): validate_rls_structure emit contract …`
- `feat(roi): classify_matter emit contract …`
- `test(roi): parametrized MCP tool emit compliance (W5, RED)`
- `feat(roi): pre-flight validate guard + drop unschema'd ts field …`

- [ ] **Step 4: Push to GitHub origin**

```bash
git push origin feat/v0.2.0a-backend
```

- [ ] **Step 5: Update `pending_work.md`**

Edit `~/.claude/projects/-Users-ejarbe/memory/pending_work.md`. Under "RLS Apex v1 — Rule #18 schema gaps deferred from cleanup #17", strike through W1-W4 + W9 (now closed). Add a one-line note: "Closed in v0.2.0b-backend plan, commits land on `feat/v0.2.0a-backend` <date>".

- [ ] **Step 6: Mark done**

This plan ships when steps 1-5 are clean. Task 8 in the contract hardening design (W6 breaker tests + W8 health endpoint aggregation + W10 dead-letter) is `writing-plans` work for v0.2.0c, not this plan.

---

## Self-Review

**Spec coverage check:**
- W1 (ToolRoiEmitter pre-flight + drop ts) → Task 1 ✓
- W2 (3 tool emit call sites with full field set + tool=rls_apex + extra) → Tasks 3, 4, 5 ✓
- W3 (`_EMIT_DEFAULTS` per tool) → Tasks 3, 4, 5 ✓
- W4 (`/api/query` DEV_MODE emit) → Task 6 ✓
- W5 (parametrized compliance test) → Task 2 ✓
- W9 (try/except wrapper, success=False on raise) → Tasks 3, 4, 5 ✓
- W6, W7, W8, W10 — explicitly out of scope (deferred to v0.2.0c per contract hardening design Phase 3 table)

**Placeholder scan:** No "TODO/TBD/implement later" outside of in-code TODO comments that point at v0.2.1 W7 (the real OIDC dept/role_band wiring). All TDD steps include actual test code and actual implementation code.

**Type consistency check:**
- `_EMIT_DEFAULTS` is the same name in all three tool servers ✓
- `workflow` values: `rls_apex.mcp.classify_matter` / `rls_apex.mcp.validate_rls_structure` / `rls_apex.mcp.extract_fields` / `rls_apex.query` — consistent dotted form ✓
- `tool="rls_apex"` everywhere ✓
- `task_type`: classify=`data_analysis`, validate=`validation`, extract=`data_analysis`, query=`data_analysis` — matches schema TaskType enum ✓
- `user_id` (not `actor_id`) at the emit-event level ✓ (the JWT claim remains `actor_id`; we map at emit time)

**Risk acknowledgment:**
- Task 5's reference to `extract_fields` emit is partially inferred from grep — the implementer must read the actual file in Step 1 and adjust the `extra` dict to match real result keys. Flagged in the step text.
- Task 6's stream-wrapper approach assumes `_mock_query_stream` yields complete SSE chunks (each `event: ... \n data: ... \n\n` in one yield). Confirmed by reading the helper — it uses a single `sse()` formatter. Safe.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-08-v0_2_0b-backend-roi-fixes.md`.**

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, two-stage review between tasks (spec compliance + code quality), fast iteration. Same discipline that closed cleanup #17 cleanly.
2. **Inline Execution** — Execute tasks in this session via `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?

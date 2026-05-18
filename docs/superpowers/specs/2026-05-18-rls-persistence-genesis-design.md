# RLS Persistence + Lineage Genesis (P1) — Design Spec

**Date:** 2026-05-18
**Repo / branch:** `rls-apex-v1` / `feat/v0.2.0a-backend`
**Status:** Design — awaiting user review, then `writing-plans`.
**Standing lenses:** microservices-architect (persistent for this repo), architecture-designer, think.

---

## 1. Context & problem

The CAO decision-write loop (deferred from v0.2.1a, Lock #19 legal-liability) was
brainstormed and found to sit on a persistence subsystem **that does not exist**:

- `/api/intake` and `/api/validate` are stateless (classify/extract, emit ROI,
  return JSON). No `rls` row, no `lineage_head`, no DB write.
- `apps/gateway/db/` contains only `models.py` (Pydantic) + `pool.py` (pool).
  There is **no repository/persistence layer**.
- No application code writes `rls`, `lineage_event`, or `audit_event` rows.
  The `001_baseline` migration created those tables; nothing has ever used
  them. The only "RLS records" are DEV in-memory `_mock.SUBMISSIONS`.

So `update_rls_status` cannot `UPDATE rls SET status…` (no real row) and cannot
append `lineage_event` seq N+1 (no genesis seq 1). The work decomposes:

- **P1 (this spec):** RLS persistence + lineage genesis — the foundation.
- **P2 (separate spec, after P1):** CAO decision-write. ~80% pre-decided this
  session; carried forward in §11.

## 2. Scope

**In scope (P1):** a persistence layer behind one interface; a real Submit
that creates an `rls` row + genesis `lineage_event` + `audit_event` in one tx;
read-path migration off direct `_mock`; DEV in-memory parity; the shared
lineage hash module; the per-year ID counter; tests.

**Out of scope:** the CAO decision transition (P2); re-enabling the cao-view
decision buttons (P2); real authentication (pilot-gated bypass stands —
[[session_2026_05_18_plan_d_closed_rc2]]).

**P1's only UI delta:** the currently-disabled submit-panel ("Submit goes live
in v0.2.1") is enabled — it is the genesis trigger.

## 3. Decided inputs

| # | Decision | Resolution |
|---|---|---|
| Genesis point | When does a durable `rls` row exist? | At explicit **Submit/promote** (after validate, `blocking==0`). Drafts stay client-side; abandoned intakes never persist (Lock #19 hygiene). |
| Submit safety | Duplicate-submit protection + id allocation | DB-allocated `rls_id` + shared **idempotency key** (`audit_event.UNIQUE(idempotency_key)` is the primitive). |
| Backend topology | Persistence shape | **Approach 1**: one `repository.py` interface; env-gated backend; `get_repo` resolves **per-request**. |
| Official-ID contiguity | Sequence vs counter | **Per-year counter row** via atomic `INSERT … ON CONFLICT (year) DO UPDATE … RETURNING` inside the genesis tx → contiguous, transactional, no gaps. Contention is a non-issue at human submission volume. |
| Canonicalization | Hash determinism | **Strict string-only profile**, self-specified algorithm (§5.1 rules 1–6, *not* JCS), `chain_version` in payload, no new runtime dependency. |
| Tx model | Write topology | Approach-A (reused from P2): one PG tx; post-commit fire-and-forget ROI; tool→PG breaker **fail-loud** (Lock #18). |

## 4. Architecture — repository + env-gated backend

One new module `apps/gateway/db/repository.py` is the bounded-context boundary
for RLS persistence — nothing else touches `_mock` or raw SQL.

```python
async def create_rls(payload, *, actor, idempotency_key) -> RlsRecord   # genesis tx (§6)
async def get_rls(rls_id) -> RlsRecord | None
async def list_for_cao(*, status=RlsStatus.READY_FOR_CAO) -> list[RlsRecord]
async def get_brief(rls_id) -> CaoBrief | None
async def get_lineage(rls_id) -> list[LineageEvent]                      # audit read (§8)
```

**Backend selection — per request**, inside the `get_repo` FastAPI dependency
(NOT at module import: the DB pool is created in the lifespan, which runs after
import — a module-load check would always see no pool and always pick the mock,
even in prod):

```
DEV_AUTH_BYPASS=="1"  OR  request.app.state.db_pool is None  →  _MockRepo
otherwise                                                     →  PgRepo
```

May be memoized after the first request (pool guaranteed up by then).
Injected via `Depends(get_repo)`; tests use `dependency_overrides`.

**Documented limitation:** `DEV_AUTH_BYPASS` now also selects the persistence
backend (auth-bypass and store-choice fused on one pilot flag). No
real-auth+mock-DB or bypass-auth+real-DB combination is possible. Acceptable
for the pilot; recorded so it is a deliberate decision, not an accident.

## 5. Shared pure lineage module

`apps/gateway/db/lineage.py` — no I/O, no DB. **Both** `PgRepo` and `_MockRepo`
call these, so the DEV click-through exercises the real chain math:

```python
def canonical_bytes(payload: dict) -> bytes
def compute_link(prev_hash: str | None, sequence: int, payload: dict) -> str  # 64-hex
def verify_chain(events: list[LineageEvent]) -> bool
```

### 5.1 Canonical profile (chain_version "1") — verbatim, auditor-reimplementable

The hashed `payload` MUST satisfy:

1. Every value is a JSON string. Enums → their string value. Integers/ids →
   decimal string. **No floats, no booleans, no nulls, no nested objects or
   arrays.** Absence is expressed by omitting the key (never a null value).
2. Timestamps are ISO-8601 UTC with a trailing `Z`, second precision:
   `YYYY-MM-DDTHH:MM:SSZ`.
3. String values are Unicode NFC-normalized. (Stability: the Unicode
   Normalization Stability policy guarantees NFC is invariant for
   already-assigned characters across Unicode versions, so an auditor
   recomputing years later gets identical output for any character that
   existed when the event was written.)
4. `payload` always includes `chain_version: "1"`.
5. Object keys are sorted ascending by Unicode code point (Python
   `str` ordering). All keys in this profile are ASCII, so this is
   unambiguous.
6. String escaping is exactly Python `json.dumps(..., ensure_ascii=False)`:
   `"` → `\"`, `\` → `\\`, U+0008 → `\b`, U+0009 → `\t`, U+000A → `\n`,
   U+000C → `\f`, U+000D → `\r`, all other control chars U+0000–U+001F →
   `\u00XX` (lowercase hex), every other character (incl. all non-ASCII)
   emitted literally as UTF-8. `/` is NOT escaped.

Canonical bytes =
`json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
encoded UTF-8, over a payload meeting (1)–(6).

**This is THE canonical algorithm — rules (1)–(6) are the normative
definition.** It is *not* RFC 8785 (JCS) and a JCS library MUST NOT be
assumed to reproduce it (JCS mandates UTF-16 code-unit key ordering and a
distinct escaping table). An auditor reimplements tamper-evidence from
rules (1)–(6) and §5.2 alone — not from any external standard.

### 5.2 Link function

```
compute_link(prev_hash, sequence, payload) = sha256_hexdigest(
      (prev_hash or "GENESIS").encode("ascii")   # 64-hex or literal GENESIS
    + b"\x1f"                                     # single 0x1F byte
    + str(sequence).encode("ascii")               # ASCII decimal digits
    + b"\x1f"                                      # single 0x1F byte
    + canonical_bytes(payload)                     # §5.1 — already bytes
)
```

The hash input is **bytes**, constructed exactly as above: the string
operands are ASCII-encoded, each delimiter is the single byte `0x1F`,
`canonical_bytes` is appended as-is, and the SHA-256 is rendered as
lowercase 64-char hex. This byte construction is normative — an auditor
reproduces it from this paragraph alone.

`\x1f` (ASCII Unit Separator) is the field delimiter, and the concatenation
is unambiguous because **no field can contain a raw 0x1F byte**: `prev_hash`
is 64-hex (or the literal `GENESIS`), `str(sequence)` is ASCII digits, and
`canonical_bytes` cannot contain raw 0x1F because §5.1 rule (6) escapes every
control char U+0000–U+001F (incl. U+001F itself, even if a user typed one)
to its 6-character backslash-u escape (the characters backslash, `u`, `0`, `0`, `1`, `f`) — so no raw 0x1F byte survives into `canonical_bytes`. Genesis: `prev_hash=None`, `sequence=1` →
literal `"GENESIS"` sentinel.

### 5.3 verify_chain

Given the ordered events for one `rls_id`: sequences are `1..N` contiguous and
strictly increasing; `events[0].prev_hash is None`; for each `i`,
`events[i].prev_hash == events[i-1].this_hash`; and
`compute_link(prev, seq, payload) == this_hash` for every event. Any failure →
`False`. This lets an auditor (or a test) prove tamper-evidence **without
trusting the application** and without our source — only this spec.

## 6. Genesis transaction (`PgRepo.create_rls`)

Precondition (server-side): payload validates with `blocking == 0`.

**`ts` is captured exactly once** — UTC at request receipt, formatted per
§5.1 rule 2 — and the *same* value is reused in both the step-2 `audit_event`
envelope and the step-3 hashed `payload₁`. It is never re-read from the clock
(request-time ≠ commit-time; two captures could diverge and would make the
audit envelope inconsistent with the anchored hash).

One PG transaction, **ordered so the idempotency-replay path works**:

1. **Mint `rls_id` first.** `:yr` = the **calendar year** (UTC) of submission;
   `:yy` = its last two digits. Allocate with a single **atomic
   upsert-returning** (do NOT use `INSERT … ON CONFLICT DO NOTHING` then
   `SELECT … FOR UPDATE` — under a concurrent first-of-year insert the
   conflicting row is uncommitted/invisible and the SELECT can return zero
   rows):
   `INSERT INTO id_counter (year, next_seq) VALUES (:yr, 2)
   ON CONFLICT (year) DO UPDATE SET next_seq = id_counter.next_seq + 1
   RETURNING next_seq - 1 AS seq;`
   → `rls_id = f"RLS-{yy}-{seq:04d}"`. One statement: the first-ever submit of
   a year inserts the row (claiming seq 1, leaving `next_seq=2`); every later
   submit atomically bumps and returns. The row write is inside this tx, so a
   rollback consumes no number (contiguous official IDs); the row lock taken
   by `DO UPDATE` serializes concurrent submits for the year.
2. `INSERT INTO audit_event (rls_id, actor_id, actor_role, action,
   payload, idempotency_key) VALUES (…, 'rls.create', …, :key);`
   `audit_event.payload` here is the **request envelope** (raw submitted
   `rlsPayload` + actor + `ts` + `idempotency_key`) — distinct from the
   lineage `payload₁` of step 3; it is the "what was requested" record, not
   the canonical hashed snapshot. The `UNIQUE(idempotency_key)` constraint
   is the dedup gate. A unique-violation **aborts the entire PG transaction**
   (Postgres rejects all further statements in it). So the replay path MUST:
   catch the violation → roll back this tx → open a **separate** tx →
   `SELECT rls_id FROM audit_event WHERE idempotency_key=:key` →
   `get_rls(rls_id)` → return the existing record (HTTP 200, no second
   privileged row). `audit_event.rls_id` was populated by the *original*
   winning tx (its step 1 ran first), which is why the lookup resolves.
   Same-key races are serialized by the row lock step 1's
   `ON CONFLICT … DO UPDATE` takes on the per-year counter row, so the
   idempotency outcome is deterministic: the second submitter blocks until
   the first **commits or aborts**. If the first committed, the second hits
   the unique-violation replay path (returns the existing record). If the
   first aborted (validation, breaker fail-loud), the second proceeds as the
   legitimate winner.
3. Build `payload₁` (canonical profile §5.1 — every value a string):
   `{chain_version:"1", rls_id, type, subject, department, contact_name,
   contact_extension, classification, actor_id, authn:"pilot_bypass", ts}`,
   where `type` and `classification` are the **string value** of their
   respective enums (`MatterClassification` is flattened to its
   classification string — §5.1 forbids nested objects). The `authn`
   provenance is in the hashed payload — the chain itself proves identity was
   self-asserted, not authenticated (Lock #19 choice, cryptographically
   anchored). **Under `DEV_AUTH_BYPASS`, `actor_id` MUST be the single
   configured pilot principal (server-side constant), NOT request-controlled
   free text** — otherwise one pilot user could author a tamper-evident
   genesis attributed to another named individual. (When real authn lands,
   `actor_id` comes from the verified token and `authn` flips off
   `pilot_bypass`.)
4. `this_hash = compute_link(None, 1, payload₁)`.
5. `INSERT INTO rls (rls_id, …, status='ReadyForCAO',
   lineage_head=:this_hash)` +
   `INSERT INTO lineage_event (rls_id, sequence=1, prev_hash=NULL,
   this_hash, payload=payload₁)`.
6. Commit. Tool→PG breaker **fail-loud** (Lock #18 / DECISION_LOG): if the tx
   cannot commit, the caller gets **503**, nothing partial is written.
7. **Post-commit only** (W1 ordering): fire-and-forget ROI `tool_invocation`
   via `RoiClient` (breaker + JSONL fallback never blocks the user action,
   Rule #18).

The chain integrity guarantee is precisely: *a tamper-evident record of the
**asserted** (not authenticated) actor and the submitted content.* Chain
integrity ≠ identity assurance — stated so no one later conflates them.

## 7. Idempotency

`audit_event.UNIQUE(idempotency_key)` is the single mechanism, shared with P2's
decision idempotency (one operator mental model). First submit writes the row;
a replayed key (double-click, dropped-response retry) hits the UNIQUE
violation → the original `rls_id` + record is returned, 200, **no second row,
no consumed counter number**. A genuinely different submission uses a
different key.

**Key stability is load-bearing for Lock #19** — the whole no-duplicate-
privileged-row guarantee rests on the same logical submission carrying the
same key across a retry. A freshly-random key minted per click would defeat
dedup: a dropped-response retry after a refresh would create a *second*
genesis (new `rls_id`, new official number) for one matter. Therefore the
key MUST be stable across retries of the same submission, by one of:
(a) server-minted on draft-open and echoed back on Submit (preferred — the
client cannot get it wrong), or (b) a deterministic digest of the canonical
draft content. It MUST NOT be `uuid4()` generated at click time. P1 owns the
submit-panel, so P1 implements (a). Required test: *same draft, new browser
session/refresh, Submit twice* → exactly one `rls` row.

## 8. DEV parity & read-path migration

**`_MockRepo` is a normalizing adapter, not a passthrough.** `_mock.SUBMISSIONS`
are loose dicts (free-string status — the legacy DEV path even emitted
`"Submitted"`, not an enum member; no `lineage_head`, no `created_at`).
`_MockRepo` returns strict `RlsRecord`/`LineageEvent`, synthesizing/​coercing
the missing fields. That normalization has **its own tests** — if it drifts,
DEV and prod diverge on the exact shape P1 exists to pin. `_MockRepo` uses an
in-memory per-year counter + an in-memory `{idempotency_key → rls_id}` map and
the **same `lineage.py`** functions, so DEV genesis is real chain math.

**Read-path migration.** Routes that read `_mock` directly (CAO brief, status,
list) are repointed at `get_brief / get_rls / list_for_cao`. `get_lineage` is
new — it gives `verify_chain` a real consumer and backs a future audit-read
endpoint. Behavior is identical under `_MockRepo`, so this is a UI-invisible
refactor that removes the direct `_mock` coupling.

## 9. Schema / migration

`rls`, `lineage_event`, `audit_event` already exist (`001_baseline`,
incl. `audit_event.UNIQUE(idempotency_key)` and the `this_hash`/`prev_hash`
regex CHECKs). **One new migration** adds:

```sql
CREATE TABLE id_counter (
    year     integer PRIMARY KEY,
    next_seq integer NOT NULL CHECK (next_seq >= 1)
);
```

No change to the existing three tables.

## 10. Testing strategy (strict-TDD)

**Test-parity boundary (honest):** only `lineage.py` is genuinely shared
code. The shape/contract suite is parametrized across `_MockRepo` and
`PgRepo`. **Transaction-isolation and concurrency properties cannot be
reproduced by an in-process map** — `ON CONFLICT … DO UPDATE` row-lock
serialization, abort-on-unique-violation, separate-tx replay — so
those tests run against a **real Postgres only** (testcontainers/ephemeral
DB), NOT `_MockRepo`. Claiming mock/PG parity for isolation would give false
confidence.

Parametrized across both backends (shape/contract):

- **`lineage.py` (pure):** canonical-profile determinism (key order, NFC, ts
  format); `compute_link` known-answer vectors (incl. the exact §5.2 byte
  construction); `verify_chain` detects reorder / tamper / broken link /
  missing genesis; `chain_version` present; a non-conforming payload
  (float/None/nested) is rejected before hashing.
- **Genesis happy-path shape:** create → `rls` + `lineage_event` seq 1
  (`prev_hash`=NULL, `lineage_head == this_hash`), correct `rls_id` format.
- **Mock-adapter normalization:** loose `_mock` dict → schema-valid strict
  record (coerces status enum, synthesizes `lineage_head`/`created_at`).
- **Read-path:** `get_brief`/`get_rls`/`list_for_cao`/`get_lineage` shapes
  unchanged under `_MockRepo` (CAO brief consumer sees no difference).

**PgRepo only — real Postgres (testcontainers); isolation/concurrency,
NOT reproducible on the mock:**

- **Atomic rollback:** forced failure mid-genesis rolls back leaving
  **no `rls`, no `lineage_event`, and no `id_counter` gap**.
- **Idempotency replay:** replayed key → same `rls_id`, no second row,
  counter unchanged; distinct key → new contiguous id; **same draft +
  fresh session/refresh, Submit twice → exactly one `rls` row** (§7
  key-stability — the Lock #19 guard).
- **ID contiguity under concurrency:** N concurrent submits → N contiguous
  per-year ids, no gap, no dup; first-of-year initializes the row atomically
  (the `ON CONFLICT DO UPDATE` path, §6 step 1).
- **Breaker fail-loud:** PG breaker open → 503, no partial write.
- **ROI ordering:** post-commit `tool_invocation` only on success (W1);
  emit failure does not fail the request; crash between commit and emit is
  the accepted at-most-once gap (§13), asserted as documented behavior.

## 11. P2 carry-forward (decided this session, feeds the P2 spec)

- Pilot-gated authz: `DEV_AUTH_BYPASS` + `role_band=='cao'` gate +
  `authn=pilot_bypass` provenance in the lineage payload.
- Re-decision: state-guarded (precondition `status==READY_FOR_CAO`) +
  idempotency key; replay → original result; new decision on a
  non-`READY_FOR_CAO` record → 409 with the existing decision.
- Approach A (atomic PG tx + post-commit fire-and-forget ROI); transactional
  outbox = documented upgrade path if decision-ROI is ever ruled audit-grade.
- `update_rls_status` is an in-process library (ADR-006). One real breaker
  (tool→PG, fail-loud); gateway→tool is exception propagation, not a breaker
  (Lock #18 Layer-1 is N/A under in-process topology).
- Decision endpoint contract = backward-compatible **superset** of the DEV
  mock (adds `idempotency_key` request field + a lineage receipt
  `{sequence, this_hash}` response field).
- Status map: `accept→ACKNOWLEDGED`, `reject→REJECTED`,
  `return→NEEDS_REVISION` (the DEV mock's `"Submitted"` is not an enum member
  and is wrong).
- Naming: use `update_rls_status` (DECISION_LOG line 193's `decision_writer`
  was an earlier TODO label; reconcile to `update_rls_status`, the Lock-level
  name).
- P2 appends `lineage_event` seq N+1 onto P1's genesis chain; re-enabling the
  cao-view decision buttons is P2's final step.

## 12. Uncertainties / open questions

- **Year-rollover semantics for `id_counter`:** RESOLVED — **calendar year
  (UTC)**, decided 2026-05-18. First submit of a new calendar year initializes
  a fresh row at `next_seq=1` (§6 step 1). Not fiscal-year.
- **`get_lineage` exposure:** this spec adds the repo method + reserves a
  read endpoint, but the auditor-facing UI/endpoint surface is left to P2 or a
  later audit-UX pass (not required for P1 correctness; `verify_chain` is
  exercised by tests regardless).
- **Existing DEV read consumers off-enum status:** the legacy DEV path used
  status strings outside `RlsStatus`. `_MockRepo` normalization coerces them;
  any consumer depending on the old free strings must be caught by the
  read-path tests (called out, not yet enumerated — first implementation task
  should grep consumers).

## 13. Non-functional / microservices notes

- **Bounded context:** RLS persistence has exactly one owner
  (`repository.py`), one interface, a swappable backing store, and is
  independently testable — the boundary the microservices lens requires.
- **Resilience:** the only cross-process hop in the write path is the
  post-commit ROI emit, deliberately fire-and-forget with breaker + JSONL
  fallback. The PG write is one ACID tx with a fail-loud breaker. No
  distributed saga — there is nothing to compensate. **Named gap:** if the
  process dies in the window between tx-commit and the post-commit emit
  reaching the breaker/JSONL, that genesis has a committed legal record but
  *no* ROI `tool_invocation` (at-most-once ROI). This is accepted — ROI
  never blocks the user action (Rule #18) and the renewal/Power-BI use case
  tolerates it. The transactional-outbox option (§11) is the documented
  upgrade if decision/genesis ROI is ever ruled audit-grade.
- **Scaling assumption (stated, not hidden):** step 1's
  `INSERT … ON CONFLICT (year) DO UPDATE` takes a row lock on the per-year
  `id_counter` row, serializing **all** RLS submissions for the year on one
  lock. Sound at the design target
  (≈ ≤1 submit/sec sustained — human county-attorney intake). Above that
  (bulk import, large multi-department rollout) the row lock is the
  throughput ceiling; revisit with hi-lo/block allocation or a
  sequence-plus-gap-tolerance scheme. Not a P1 concern; a documented limit.
- **Audit:** tamper-evidence is a fully self-specified algorithm (§5.1
  rules 1–6 + §5.2), independently recomputable years later from this
  document alone — deliberately *not* delegated to an external standard.

## 14. Required ADRs (writing-plans MUST produce these)

This is a legal-liability subsystem; the irreversible-ish decisions must be
recorded in the repo's decision-record convention — `DECISION_LOG.md`
**`## Lock #N`** entries (Decision / Implications / Rationale / Reversal
cost; there is no separate `ADR-###` file series) — so future maintainers
cannot silently "tidy" the anchor.

**Precondition decision — authored and accepted BEFORE `writing-plans`
(not a plan task): ✅ DONE — `DECISION_LOG.md` Lock #20.**

- **Lock #20 — Lineage canonicalization + link algorithm.** The
  §5.1(1–6) + §5.2 byte construction is the normative, self-specified legal
  anchor; not JCS; changing it is a chain-breaking, `chain_version`-gated
  event. Because the entire P1 plan builds on this algorithm and it is
  effectively irreversible once a single real chain exists, it was recorded
  as part of *this design's acceptance*, not deferred into the plan.

**Plan-task ADRs — the P1 implementation plan MUST include explicit tasks to
author, at minimum:**

- **ADR — Genesis at explicit Submit** (not at intake): Lock #19 privileged-
  matter hygiene rationale + the abandoned-draft-never-persists consequence.
- **ADR — `DEV_AUTH_BYPASS` selects the persistence backend**: the
  deliberate auth-bypass/store-choice coupling and its accepted limitation
  (§4) — recorded so it is never mistaken for an accident.
- **ADR — Per-year `id_counter` row over a sequence**: contiguity/no-gap
  legal-numbering rationale vs. the single-lock scaling limit (§13).

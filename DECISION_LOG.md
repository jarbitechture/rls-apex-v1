# RLS Apex v1 — Decision Log

> Single source of truth for every locked decision. Every new decision appends a row.
> Reversing a locked decision requires a written rationale here, not a chat.

---

## v0.1.0 locks (session 2026‑05‑05)

| # | Decision | Choice | Rationale (compressed) |
|---|---|---|---|
| 1 | Telemetry stack | **No PostHog.** Phoenix + Power BI + promptfoo + Inspect AI + ROI sidecar. | Existing stack covers traces, exec dashboards, prompt regression, eval, per‑action telemetry. Only session replay + feature flags would be net‑new, and session replay on privileged matters is a public‑records risk. Re‑evaluate at week 6. |
| 2 | GitHub repo | `jarbitechture/rls-apex-v1` (planned target). | Independent of cookbook repo. ADO‑first commit pattern carries over. |
| 3 | RunPod | **Out of scope for v0.1.0.** | Inference stays on `bcc-ap-infer01`. RunPod re‑evaluated only when on‑prem GPU saturates. |
| 4 | Inference runtime | SGLang + Qwen2.5‑FP8 on `bcc-ap-infer01`. | Track B lock. Structured output + radix cache fit MCP tool calls. |
| 5 | Auth | Entra ID OIDC at FastAPI gateway via MSAL. New hostname `rls.mymanatee.org`. | Independent of cookbook's IIS/NTLM chain. ITS request for hostname + cert is day‑1 critical path. |
| 6 | State | `bcc-db-llm01`: AGE on existing Postgres + MinIO systemd unit. | Track B residency rule binds. No Azure managed PG (AGE not in managed extension list). No new VM (avoid Chris/ops lead time). |
| 7 | MCP boundary | FastMCP 2.0, separate processes, RS256 JWT (gateway keypair, `aud=tool.<name>`, 60s TTL), loopback `127.0.0.1:30100‑30105`, per‑tool Key Vault secrets, two‑layer circuit breakers, `mcp-tool@.service` template. | Rule #19 (circuit breaker) needs the process boundary. Per‑tool least privilege impossible in‑process. Becomes template for Permit / HR / Budget pilots. |
| 8 | DSPy / GEPA | Day‑1 DSPy signatures + chain + `smoke_eval_DO_NOT_OPTIMIZE_AGAINST.jsonl`. First GEPA compile weeks 5–6, gated on attorney redlines. | Smoke eval is plumbing only — never a quality signal. GEPA without attorney redlines optimizes against synthetic proxy = wrong target. |
| 9 | First slice | 2‑week PrecedentRetriever end‑to‑end. Internal click‑through end of week 1 (you + Drew only). | Regresses to plain 2‑week if any external stakeholder pressure appears. |
| 10 | Skills surface | **Templates‑only in v0.1.0.** Matter‑draft route reserved at `/matters/<id>/drafts/*` returning `501` with `Retry-After` semantics. Visually similar / structurally distinguishable. | M depends on Reviser (weeks 5–6). M's governance is genuinely harder. Templates compound; matter drafts don't. |
| 11 | Branding | Prototype design system stays. `_base.css` + empty `_brand-overlay.css`. Components consume CSS variables only. | Brand kit overlay is one PR when it lands. |
| 12 | Worksheet abstraction | Polymorphic `Worksheet` with `kind: BIE` from day one. | Locked stack lists Permit / HR / Budget as future pilots. Refactoring polymorphism in later is more expensive than building it now. |
| 13 | Domain entities (v0.1.0) | `Matter`, `Worksheet` (kind=BIE), `Statute`, `Opinion`, `Skill` (kind=template only), `LineageEvent`, `ROIEvent`, `Citation`, `Redline`, `MatterClassification`. | Citation = provenance is load‑bearing. Redline = GEPA training set schema. MatterClassification = ACL / corpus / public‑records driver. |

---

## Open items (none gating scaffold)

- County brand kit acquisition (deferred per Lock #11)
- ITS request for `rls.mymanatee.org` hostname + cert (day‑1 parallel task, off the scaffold critical path)

---

## Reversal log

*(empty — append rationale + date when reversing any lock above)*

# RLS Apex v1 — Decision Log

Distilled from session leading up to scaffold creation. Locks bind v0.1.0 unless explicitly re-opened.

| # | Decision | Choice | Rationale (one line) |
|---|---|---|---|
| 1 | Telemetry | **No PostHog.** Phoenix + Power BI + promptfoo + Inspect AI + ROI sidecar. | Existing stack covers it; PostHog adds 8 services and only adds session replay (which has its own legal issues). Re-evaluate week 6. |
| 2 | GitHub repo | `jarbitechture/rls-apex-v1` (planned, no push from scaffold). | Fresh, independent of cookbook repo. |
| 3 | RunPod | Out of scope for v0.1.0. | Track-B residency lock + already own GPU on `bcc-ap-infer01`. |
| 4 | Inference runtime | SGLang + Qwen2.5-FP8 on `bcc-ap-infer01`. | Structured-output + radix cache beat vLLM for tool calling. |
| 5 | Auth | Entra ID OIDC via MSAL at FastAPI gateway. New hostname `rls.mymanatee.org`. | Cookbook's IIS/NTLM chain is cookbook's; new project, new edge. |
| 6 | State host | `bcc-db-llm01` — install AGE + pgvector + MinIO. | Residency rule (#2/#10) + zero ITS lead time + AGE not available on managed PG. |
| 7 | MCP boundary | Separate processes, FastMCP 2.0, RS256 JWT, loopback only, per-tool KV secrets, two-layer circuit breakers. | Rule #19 needs the boundary; per-tool least privilege; pattern propagates to N pilots. |
| 8 | DSPy/GEPA | Day-1 DSPy signatures + chain + smoke eval; first GEPA compile week 5–6. | Optimizer needs attorney redlines as ground truth; scaffold the framework now, defer optimization. |
| 9 | First slice | 2-week PrecedentRetriever end-to-end. **Internal** click-through end of week 1 (you + Drew only). | Mock-data demo to stakeholders triggers anchoring + verifiability failure. |
| 10 | Skills | **Templates-only in v0.1.0.** `/matters/<id>/drafts/*` reserved → 501. Visually similar / structurally distinguishable. | Matter-drafts depend on Reviser (week 5–6); building infra for non-existent workflow = wrong problem. |
| 11 | Branding | Prototype tokens as foundation. `_brand-overlay.css` empty file reserved. | Brand kit lands as one PR when ready. |
| 12 | Worksheet polymorphism | `Worksheet` is the entity; `BIE` is a `kind`. | Confirmed by uploaded BIE PDF (§125.66(3)(c)). RLS Pilot templates Permit pre-screen / HR Q&A — polymorphism cheap now, expensive later. |
| 13 | New entities accepted | `Citation`, `Redline`, `MatterClassification`. | Provenance is load-bearing; GEPA needs typed redlines; classification drives ACLs across four prior decisions. |
| 14 | Smoke eval naming | `smoke_eval_DO_NOT_OPTIMIZE_AGAINST.jsonl` with README warning. | Plumbing-only signal; never read as quality. |
| 15 | Skills UI governance | UI edit → service-account git commit → PR → senior-counsel review → merge → hot-reload. Audit row in Postgres. Frontmatter `governance: { reviewer_required, owners }` per skill. | Lower-friction than git-only authoring; preserves audit + review for high-risk content. |

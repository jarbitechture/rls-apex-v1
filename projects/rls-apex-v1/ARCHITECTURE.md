# RLS Apex v1 — Architecture

> Manatee County Legal Services AI pilot.
> v0.1.0 target: PrecedentRetriever end-to-end in 2 weeks.
> All decisions in [DECISION_LOG.md](./DECISION_LOG.md).

---

## Five rings

```
┌────────────────────────────────────────────────────────────────┐
│  Surface     React UI · Entra ID OIDC · Static Web App         │
│  Harness     Claude Agent SDK pattern · DSPy modules · Skills  │
│  Tools       FastMCP 2.0 servers (one per capability)          │
│  Inference   SGLang + Qwen2.5-FP8 on bcc-ap-infer01            │
│  State       bcc-db-llm01: Postgres + AGE + pgvector + MinIO   │
└────────────────────────────────────────────────────────────────┘
```

---

## Hosts

| Host | OS | Role | Notes |
|---|---|---|---|
| `bcc-ap-llm01` | Win 2025 | IIS edge + ARR + ADO agent | Cookbook continues to live here. RLS shares only the box, not the IIS site. |
| `bcc-db-llm01` | Linux | Postgres 16 + AGE + pgvector + MinIO + Redis | RLS state. Co-tenants Dify Postgres carefully; separate $PGDATA volume. |
| `bcc-ap-infer01` | RHEL 10 | SGLang + Qwen2.5-FP8 (L4 24GB) | Inference plane. RunPod off the table for v0.1.0. |

Hostname for the new app: **`rls.mymanatee.org`** (ITS request day 1, parallel to scaffold work).

---

## Auth

- Entra ID OIDC via MSAL at the **FastAPI gateway** (NOT inherited from cookbook IIS/NTLM).
- AD group → role mapping at gateway: `attorney`, `paralegal`, `general-counsel`, `admin`.
- `/staticwebapp.config.json` keeps `allowedRoles: ["anonymous"]` for the SWA edge — gateway is the trust boundary, not SWA.
- Gateway re-signs into HMAC-JWT for downstream MCP tools (RS256, gateway keypair, `aud=tool.<name>`, 60s TTL).
- Service-to-service to AD-protected resources: gMSA where possible; KV-stored secret otherwise.

See `infra/azure/entra-app-registration.md` for app reg steps.

---

## State (`bcc-db-llm01`)

| Store | What lives here | Notes |
|---|---|---|
| Postgres 16 | Matters, Worksheets, Skills (templates only in v0.1.0), Citations, Redlines, LineageEvent, ROIEvent | Schema generated from `domain.yaml`. Alembic migrations in `infra/alembic/`. |
| AGE | Policy graph: Statute / Opinion / Worksheet / Matter / Citation nodes; `cites`, `preempts`, `implements`, `revises` edges | Same Postgres database, `age` extension, `civic` graph. |
| pgvector | Chunk embeddings: statutes, opinions, county code, worksheets | One namespace per source kind (qualified by `MatterClassification`). |
| MinIO | Source PDFs, drafts, exports, retrieval artefacts | Per-matter bucket prefix; envelope-encrypted via Key Vault DEKs. |

Privileged matters never enter the corpus index without passing the `manatee-civic-ai` redaction pipeline.

---

## MCP boundary (separate processes, s2s auth)

```
gateway (FastAPI :8080)
   ├──► retrieve         127.0.0.1:30100   (BM25 + LightRAG + Contextual)
   ├──► policy-graph     127.0.0.1:30101   (AGE Cypher)
   ├──► ontology         127.0.0.1:30102   (domain.yaml validation)
   ├──► lineage          127.0.0.1:30103   (hash-chain audit)
   ├──► docs             127.0.0.1:30104   (MinIO read/write w/ ACL)
   └──► report-roi       127.0.0.1:30105   (manatee_ai_roi sidecar)
```

Each MCP tool:
- Runs as `mcp-tool@<name>.service` (systemd template).
- Pulls its own KV secret at boot (`tool-<name>-secret`).
- Verifies RS256 JWT from gateway; `aud` must equal `tool.<name>`; TTL 60s.
- Wraps every backend call with a circuit breaker (Rule #19).
- Loopback only — never bound to a routable interface.

Gateway-side breakers add a second layer (defense in depth).

---

## Agent runtime

- **DSPy signatures + chain** day 1 — uncompiled. Smoke eval (`smoke_eval_DO_NOT_OPTIMIZE_AGAINST.jsonl`) proves plumbing.
- **GEPA compile** weeks 5–6, gated on attorney redlines (`Redline` entity, see `domain.yaml`).
- **Agents** (in priority order):
  1. `PrecedentRetriever` (v0.1.0)
  2. `PolicyMatcher` (week 3–4)
  3. `ComplianceGrader` (week 3–4)
  4. `Reviser` (week 5–6, unblocks Matter-draft surface)
- **Guardrails** wrap every output: no-legal-advice classifier, citation-required, lineage stamped.

---

## Skills

v0.1.0 ships **Templates only**:

```
skills/templates/
├── draft-bie-preamble.md
├── score-compliance.md
├── find-precedents.md
└── ...
```

Frontmatter governance per skill (reviewers, owners, classification).
UI edit → service-account commit → PR → senior-counsel approve → merge → hot-reload.

`/matters/<id>/drafts/*` URL space is reserved; gateway returns **501 Not Implemented** with `Retry-After: <weeks 5–6 release semantics>`.

---

## Observability

| Concern | Tool |
|---|---|
| Per-LLM-call traces | Phoenix (Arize) |
| Per-action telemetry | `manatee_ai_roi` sidecar → JSONL → Power BI Gateway pull |
| Prompt regression in CI | promptfoo |
| Correctness/safety eval | Inspect AI |
| Exec narrative | Power BI dashboard |

PostHog deferred. Re-evaluate at week 6 only if a specific gap (session replay, in-product flags, experiments) surfaces.

---

## Deploy

- GitHub repo: `jarbitechture/rls-apex-v1` (private).
- Pipeline: GitHub Actions → ADO commit (per cookbook pattern) → deploy.
- Static Web App: `apps/web/` → SWA `rls.mymanatee.org`.
- Gateway + MCP tools: containerless, systemd on `bcc-ap-llm01` Linux WSL or a fresh small RHEL VM (TBD by Drew).

---

## Out of scope for v0.1.0

- RunPod (any usage)
- PostHog
- Matter-draft skill surface
- GEPA optimizer compile
- PolicyMatcher / ComplianceGrader / Reviser agents
- Permit pre-screen / HR Q&A pilots (downstream templates)

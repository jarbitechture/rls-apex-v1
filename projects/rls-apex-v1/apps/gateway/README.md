# Gateway — FastAPI

Single front door for RLS Apex v1.

## Responsibilities

| Concern | Mechanism |
|---|---|
| AuthN | Entra ID OIDC via MSAL; verifies Bearer JWT on every request |
| AuthZ | AD `groups` claim → role mapping → route policy |
| Rate limit | Per-user, per-route, sliding window in Redis |
| Tracing | Phoenix instrumentation on every request + every MCP call |
| MCP host | Issues RS256 JWTs (gateway keypair, `aud=tool.<name>`, 60s TTL) for each call |
| ROI sidecar | After every user-facing action, emit one `manatee_ai_roi` event |
| Circuit breakers | Per-MCP-tool; opens at 5 failures in 30s |
| Skills hot-reload | Subscribes to `skills/templates/` changes via inotify; re-parses frontmatter |

## Endpoints (v0.1.0)

| Method | Path | Notes |
|---|---|---|
| GET  | `/healthz` | unauth — for probes |
| GET  | `/readyz` | full backend check |
| POST | `/auth/callback` | OIDC redirect_uri |
| GET  | `/auth/me` | current user + roles + groups |
| POST | `/agents/precedent-retriever/run` | SSE stream of DSPy chain |
| GET  | `/matters/{id}` | needs role+classification ACL |
| GET  | `/matters/{id}/drafts/*` | **501** — reserved (Decision #10) |
| GET  | `/skills/templates` | list |
| POST | `/skills/templates/{name}/edit` | service-account commit + PR |
| GET  | `/admin/breakers` | open/closed state |

## Layout

```
apps/gateway/
├── gateway/
│   ├── main.py                 FastAPI app
│   ├── auth/                   MSAL OIDC verify + role mapping
│   ├── mcp/                    JWT signer + per-tool clients
│   ├── routes/                 endpoints split by domain
│   ├── breakers/               circuit breaker registry
│   ├── roi/                    manatee_ai_roi sidecar emitter
│   ├── phoenix/                tracer setup
│   └── types/                  Pydantic, generated from domain.yaml
├── tests/
└── pyproject.toml
```

## Env (`/etc/rls-apex/gateway.env`)

```ini
# OIDC
AZURE_TENANT_ID=<tenant-guid>
AZURE_CLIENT_ID=<app-reg-guid>
AZURE_CLIENT_SECRET=<from-keyvault>
OIDC_AUTHORITY=https://login.microsoftonline.com/<tenant-guid>/v2.0
OIDC_REDIRECT_URI=https://rls.mymanatee.org/auth/callback

# MCP signing
MCP_SIGNING_KEY_PEM_PATH=/etc/rls-apex/mcp-sign.pem
MCP_TOOL_AUDIENCE_PREFIX=tool.

# State
DATABASE_URL=postgresql+asyncpg://rls:***@bcc-db-llm01:5433/rls_apex
MINIO_ENDPOINT=https://bcc-db-llm01:9000
MINIO_ACCESS_KEY=***
MINIO_SECRET_KEY=***

# Inference
SGLANG_BASE_URL=http://bcc-ap-infer01:8000
SGLANG_MODEL=qwen2.5-14b-fp8

# Telemetry
PHOENIX_COLLECTOR_ENDPOINT=http://bcc-db-llm01:6006
ROI_EVENT_SINK_PATH=/var/lib/rls-apex/roi/events.jsonl

# Guardrails
GUARDRAIL_LEGAL_ADVICE_MODEL=qwen2.5-7b-fp8
```

## Local dev

```bash
cd apps/gateway
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env             # fill in dev values
uvicorn gateway.main:app --reload --port 8080
```

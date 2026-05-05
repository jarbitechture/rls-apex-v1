# Local development

Mock-mode click-through for the v0.1.0 internal review (Lock #9, week 1). Runs on a laptop today; the same command runs on `bcc-ap-llm01` once a venv is set up there.

## Run on your laptop

```bash
cd rls-apex-v1
bin/dev
```

First boot bootstraps `.venv` and installs `apps/gateway/requirements.txt`. Subsequent runs reuse the venv.

Open <http://127.0.0.1:8080/>.

Type a draft RLS question, hit **Ask**. The gateway streams a canned answer + three mock citations via Server-Sent Events on `/api/query`. **Accept** / **Reject** buttons are wired to no-op (per Lock #9).

## What the mock skips

- OIDC validation — `current_user` returns a synthetic `dev@local` user when `DEV_AUTH_BYPASS=1`
- Retrieval — `/api/query` returns three hardcoded `Citation` rows from `_MOCK_CITATIONS` in `apps/gateway/main.py`
- LLM call — answer text is canned; no SGLang, no DSPy chain, no MCP dispatch
- Telemetry — no Phoenix span, no ROI sidecar emit
- Static mount — only enabled when `DEV_AUTH_BYPASS=1`; production serves the React build via IIS/nginx

## Run on `bcc-ap-llm01`

```bash
# from a build host with the repo cloned
rsync -av --exclude .venv --exclude __pycache__ rls-apex-v1/ \
  user@bcc-ap-llm01:/srv/rls-apex-v1/

# on bcc-ap-llm01
cd /srv/rls-apex-v1
bin/dev          # binds 127.0.0.1:8080 by default
HOST=0.0.0.0 PORT=8080 bin/dev   # if exposed directly (not recommended — use IIS ARR)
```

The eventual production path: IIS ARR on `bcc-ap-llm01` reverse-proxies `rls.mymanatee.org` → `127.0.0.1:8080`. Same uvicorn command, no DEV_AUTH_BYPASS, real OIDC enforced.

## Switching the mock off

Drop the `DEV_AUTH_BYPASS` env var. The gateway then enforces real OIDC (still 501 until MSAL is wired) and `/api/query` falls back to the existing 501. The static mount also disappears — production serves the React build externally.

## Endpoints in mock mode

| Path | Method | Status |
|---|---|---|
| `/` | GET | Click-through HTML |
| `/api/query` | POST | Mock SSE — token + citation + done events |
| `/healthz` | GET | `{"ok": true, "version": "0.1.0"}` (unchanged from prod) |
| `/readyz` | GET | Always returns `not yet wired` (unchanged) |
| `/internal/docs` | GET | FastAPI Swagger (no auth in mock) |

## Common issues

- **Port 8080 in use** — `PORT=8090 bin/dev`
- **`uvicorn: command not found` after editing requirements.txt** — `rm -rf .venv && bin/dev`
- **Browser shows the 1.6MB Pages prototype instead of the click-through** — you opened the repo-root `index.html` (Pages site) instead of `http://127.0.0.1:8080/` (mock click-through served from `apps/web/static/`)

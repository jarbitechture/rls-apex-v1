# v0.2.1a Stream D — Deployment Notes

**Stream D closes the v0.2.1a release:** L1 + L2 deterministic validators, L14 policy-lint LLM
endpoint, W8 aggregated health poller, and the gateway/library smoke test (Plan C Task 10).

---

## 1. What ships with Stream D

Two new standalone MCP tool units, two new gateway endpoints, and one frontend rule:

| Component | Port / Location | Description |
|-----------|-----------------|-------------|
| `mcp_tools/check_code_enforcement_litigation/` | :30105 | L1 — deterministic litigation check against DB |
| `mcp_tools/check_urgency_rules/` | :30106 | L2 — working-days urgency validator |
| `POST /api/lint/policy` | gateway | L14 — LLM-backed policy-lint endpoint (OpenAI-compat) |
| `GET /api/health/aggregated` | gateway | W8 — 30s-cached health snapshot for 6 HTTP services |
| `apps/web/src/js/auto-correct.js` | frontend | `policy-lint-llm` rule wired to `/api/lint/policy` |

**In-process tools (NOT separately deployed):** `validate_rls_structure`, `classify_matter`,
and `extract_fields` are Python imports inside the gateway process. They do NOT have their own
systemd units and are NOT included in the `/api/health/aggregated` poll. Their health is
reflected by the gateway's own `/healthz` and `/readyz` endpoints. If any of these three tools
is ever promoted to a standalone service, add its `/health` URL to `TOOL_HEALTH_ENDPOINTS` in
`apps/gateway/health_aggregator.py`.

No new Alembic migration ships with Stream D — the schema from Stream C (`corpus_hits` table +
pgvector index) is sufficient.

---

## 2. Preconditions

Before deploying Stream D:

- Streams A, B, and C are fully deployed and healthy on `bcc-ap-llm01`.
- Stream C's three systemd units are running:
  - `rls-apex-embedding.service` (port 30201)
  - `rls-apex-list-rls-precedents.service` (port 30103)
  - `rls-apex-get-policy-snippets.service` (port 30104)
- An OpenAI-compatible LLM inference endpoint is reachable from the gateway
  (`OPENAI_API_BASE` env var, defaults to `http://127.0.0.1:11434/v1` for Ollama).
- The `rls-apex` system user exists on `bcc-ap-llm01`.
- `/opt/rls-apex-v1` is checked out at HEAD `8906e64` or later.

---

## 3. Deploy steps

SSH to `bcc-ap-llm01` as a user with `sudo` access:

```bash
ssh deploy@bcc-ap-llm01
```

Pull latest code:

```bash
cd /opt/rls-apex-v1
git pull origin feat/v0.2.0a-backend
```

Activate the venv:

```bash
source .venv/bin/activate
```

No new Alembic migration — schema from Stream C is already at head. Verify:

```bash
alembic current
```

Copy the two new MCP unit files:

```bash
sudo cp mcp_tools/check_code_enforcement_litigation/systemd/check_code_enforcement_litigation.service \
    /etc/systemd/system/rls-apex-check-code-enforcement-litigation.service

sudo cp mcp_tools/check_urgency_rules/systemd/check_urgency_rules.service \
    /etc/systemd/system/rls-apex-check-urgency-rules.service
```

Set `DB_PASSWORD` in each unit before enabling:

```bash
sudo systemctl edit rls-apex-check-code-enforcement-litigation.service
# Add: Environment=DB_PASSWORD=<actual_password>

sudo systemctl edit rls-apex-check-urgency-rules.service
# Add: Environment=DB_PASSWORD=<actual_password>
```

Configure the gateway's LLM endpoint (if not already set):

```bash
sudo systemctl edit rls-apex-gateway.service
# Add: Environment=OPENAI_API_BASE=http://127.0.0.1:11434/v1
# Add: Environment=OPENAI_API_KEY=ollama
# Add: Environment=OPENAI_MODEL=phi4
```

Reload systemd and enable the two new units:

```bash
sudo systemctl daemon-reload

sudo systemctl enable --now rls-apex-check-code-enforcement-litigation.service
sudo systemctl enable --now rls-apex-check-urgency-rules.service
```

Restart the gateway so it picks up the new W8 lifespan task and `/api/lint/policy` route:

```bash
sudo systemctl restart rls-apex-gateway.service
```

---

## 4. Smoke test

### 4a. Individual service health

Verify all 6 independent HTTP services — these are the exact services that
`GET /api/health/aggregated` polls (W8). The three in-process tools
(`validate_rls_structure`, `classify_matter`, `extract_fields`) are NOT listed here;
check the gateway endpoints below for their health.

```bash
# Stream C services (must already be healthy)
curl -s http://127.0.0.1:30201/health | jq .   # embedding-service
curl -s http://127.0.0.1:30103/health | jq .   # list_rls_precedents (L3)
curl -s http://127.0.0.1:30104/health | jq .   # get_policy_snippets (L4)

# Stream D services (new)
curl -s http://127.0.0.1:30105/health | jq .   # check_code_enforcement_litigation (L1)
curl -s http://127.0.0.1:30106/health | jq .   # check_urgency_rules (L2)

# Scraper service (Stream A)
curl -s http://127.0.0.1:30200/health | jq .   # scraper-service
```

Expected for each: `{"status": "ok", ...}` or `{"status": "healthy", ...}`.

### 4b. W8 aggregated health endpoint

```bash
curl -s http://127.0.0.1:8000/api/health/aggregated | jq .
```

Expected shape:

```json
{
  "overall_status": "healthy",
  "checked_at": "2026-05-12T...",
  "tools": {
    "list_rls_precedents":               {"status": "ok"},
    "get_policy_snippets":               {"status": "ok"},
    "check_code_enforcement_litigation": {"status": "ok"},
    "check_urgency_rules":               {"status": "ok"},
    "scraper_service":                   {"status": "healthy"},
    "embedding_service":                 {"status": "healthy", "ollama_reachable": true}
  }
}
```

`checked_at` is `null` until the background poller completes its first 30s cycle. If
`overall_status` is `"degraded"`, consult the `tools` map to identify which service is
unreachable and fix it before proceeding.

### 4c. L14 policy-lint endpoint

```bash
curl -s -X POST http://127.0.0.1:8000/api/lint/policy \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "rlsPayload": {
      "factualBackground": "The applicant failed to disclose pending litigation.",
      "legalQuestion": "Does the zoning ordinance apply retroactively?"
    }
  }' | jq .
```

Expected: HTTP 200 with `{"suggestions": [...]}`. An empty list means the LLM found no
violation. A non-empty list means at least one `policy-lint-llm` suggestion with `ruleId`,
`field`, `citation`, `severity`, and `explanation`.

If the LLM endpoint is unreachable, the response is HTTP 503:
`{"detail": "policy lint llm unavailable: ..."}`.

### 4d. ROI sidecar drain

```bash
curl -s http://127.0.0.1:8000/health/sidecar | jq .
```

Expected: `{"status": "healthy", "breaker_state": "closed", ...}`.

### 4e. Gateway in-process tool health

```bash
curl -s http://127.0.0.1:8000/healthz | jq .
curl -s http://127.0.0.1:8000/readyz  | jq .
```

Both must return 200. A non-200 `/readyz` means one of the in-process tools
(`validate_rls_structure`, `classify_matter`, `extract_fields`) failed to import — check
the gateway logs.

---

## 5. Rollback

Stop the two new Stream D MCP units:

```bash
sudo systemctl stop rls-apex-check-code-enforcement-litigation.service \
    rls-apex-check-urgency-rules.service

sudo systemctl disable rls-apex-check-code-enforcement-litigation.service \
    rls-apex-check-urgency-rules.service
```

Remove the unit files:

```bash
sudo rm /etc/systemd/system/rls-apex-check-code-enforcement-litigation.service \
        /etc/systemd/system/rls-apex-check-urgency-rules.service
sudo systemctl daemon-reload
```

Revert the gateway to the Stream C HEAD:

```bash
cd /opt/rls-apex-v1
git revert HEAD --no-edit
git push origin feat/v0.2.0a-backend
sudo systemctl restart rls-apex-gateway.service
```

No schema downgrade is needed — Stream D adds no Alembic migration.

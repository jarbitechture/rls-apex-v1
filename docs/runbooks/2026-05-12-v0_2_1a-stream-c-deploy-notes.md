# v0.2.1a Stream C — Deployment Notes

**Note (2026-05-14):** Plan C Task 10 (gateway integration smoke test) was deferred. The gateway does
not yet route to MCP tools over HTTP — it invokes them as in-process Python imports. Gateway-to-MCP-tool
wiring lands with Plan D Task 5 (`/api/lint/policy` endpoint) or a future `mcp_router.py` design.
v0.2.1a Stream C deploys L3 + L4 as reachable services on their own ports; end-to-end gateway smoke
ships with Plan D.

---

## 1. What ships with Stream C

Three systemd units and one Alembic migration:

| Unit file | Port | Description |
|-----------|------|-------------|
| `services/embedding/systemd/embedding.service` | 30201 | Ollama mxbai-embed-large wrapper + circuit breaker |
| `mcp_tools/list_rls_precedents/systemd/list_rls_precedents.service` | 30103 | L3 MCP tool — BM25 + ANN retrieval |
| `mcp_tools/get_policy_snippets/systemd/get_policy_snippets.service` | 30104 | L4 MCP tool — policy snippet lookup |

Alembic migration: adds `corpus_hits` table with pgvector `embedding` column (1024-dim) and
`ts_vector` column for BM25; creates ANN index (`ivfflat`, 100 lists).

---

## 2. Preconditions

Before deploying Stream C:

- Plan A (web ingestion) is merged and all scraper systemd units are running on `bcc-ap-llm01`.
- Plan B (redaction pipeline) is merged and the redaction service is healthy.
- pgvector v0.8.2 is installed on the Postgres 16 server (built from source — `brew install pgvector`
  does not work with PG16; see Plan A deploy notes for build steps).
- Ollama is running on `bcc-ap-infer01:11434` with `mxbai-embed-large` pulled:
  ```bash
  ollama pull mxbai-embed-large
  ```
- The `rls-apex` system user exists on `bcc-ap-llm01`.
- `/opt/rls-apex-v1` is checked out at HEAD `be358af` or later.

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

Activate the venv and upgrade the schema:

```bash
source .venv/bin/activate
alembic upgrade head
```

Copy the three systemd unit files:

```bash
sudo cp services/embedding/systemd/embedding.service \
    /etc/systemd/system/rls-apex-embedding.service

sudo cp mcp_tools/list_rls_precedents/systemd/list_rls_precedents.service \
    /etc/systemd/system/rls-apex-list-rls-precedents.service

sudo cp mcp_tools/get_policy_snippets/systemd/get_policy_snippets.service \
    /etc/systemd/system/rls-apex-get-policy-snippets.service
```

Edit each unit's `DB_PASSWORD` placeholder before enabling:

```bash
sudo systemctl edit rls-apex-list-rls-precedents.service
# Add: Environment=DB_PASSWORD=<actual_password>

sudo systemctl edit rls-apex-get-policy-snippets.service
# Add: Environment=DB_PASSWORD=<actual_password>
```

Reload systemd and enable all three units:

```bash
sudo systemctl daemon-reload

sudo systemctl enable --now rls-apex-embedding.service
sudo systemctl enable --now rls-apex-list-rls-precedents.service
sudo systemctl enable --now rls-apex-get-policy-snippets.service
```

---

## 4. Smoke test

Verify each unit is healthy and ready to serve. Start with the embedding service — L3 and L4 fall
back to BM25-only when embedding is unavailable, so its health status explains any retrieval degradation.

```bash
# embedding-service
curl -s http://127.0.0.1:30201/health | jq .
# Expected: {"status": "healthy", "ollama_reachable": true, "breaker_state": "closed", "last_inference_ms": null}

# L3 — list_rls_precedents
curl -s http://127.0.0.1:30103/health | jq .
# Expected: {"status": "ok", ...}

# L4 — get_policy_snippets
curl -s http://127.0.0.1:30104/health | jq .
# Expected: {"status": "ok", ...}

# ROI sidecar drain
curl -s http://127.0.0.1:8000/health/sidecar | jq .
```

If `ollama_reachable` is false on the embedding-service health check, that is the root cause of any
L3/L4 BM25-fallback behaviour — fix Ollama connectivity on `bcc-ap-infer01` before investigating
retrieval quality.

**End-to-end retrieval through the gateway requires Plan D Task 5 (`/api/lint/policy`) or a
forthcoming `mcp_router.py` design. v0.2.1a deploys L3 + L4 as reachable services — gateway
integration ships in v0.2.1a only via Plan D.**

---

## 5. Rollback

Stop all three units:

```bash
sudo systemctl stop rls-apex-embedding.service \
    rls-apex-list-rls-precedents.service \
    rls-apex-get-policy-snippets.service

sudo systemctl disable rls-apex-embedding.service \
    rls-apex-list-rls-precedents.service \
    rls-apex-get-policy-snippets.service
```

Downgrade the schema one step:

```bash
cd /opt/rls-apex-v1
source .venv/bin/activate
alembic downgrade -1
```

Revert the commit:

```bash
git revert HEAD --no-edit
git push origin feat/v0.2.0a-backend
```

Remove the unit files:

```bash
sudo rm /etc/systemd/system/rls-apex-embedding.service \
    /etc/systemd/system/rls-apex-list-rls-precedents.service \
    /etc/systemd/system/rls-apex-get-policy-snippets.service
sudo systemctl daemon-reload
```

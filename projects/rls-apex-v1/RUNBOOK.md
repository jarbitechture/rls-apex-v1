# RLS Apex v1 — Runbook

Day-2 ops for v0.1.0. Updated as services land.

---

## Hosts & ports

| Host | Service | Port | Notes |
|---|---|---|---|
| `bcc-ap-llm01` | gateway (FastAPI) | 8080 | OIDC verifier, MCP host |
| `bcc-ap-llm01` | mcp-tool@retrieve | 30100 | loopback only |
| `bcc-ap-llm01` | mcp-tool@policy-graph | 30101 | loopback only |
| `bcc-ap-llm01` | mcp-tool@ontology | 30102 | loopback only |
| `bcc-ap-llm01` | mcp-tool@lineage | 30103 | loopback only |
| `bcc-ap-llm01` | mcp-tool@docs | 30104 | loopback only |
| `bcc-ap-llm01` | mcp-tool@report-roi | 30105 | loopback only |
| `bcc-db-llm01` | Postgres (RLS) | 5433 | separate cluster from Dify, OR same with separate DB |
| `bcc-db-llm01` | MinIO API | 9000 | firewalld restricted to llm01 |
| `bcc-db-llm01` | MinIO console | 9001 | firewalld restricted to admin subnet |
| `bcc-ap-infer01` | SGLang | 8000 | inbound from `bcc-ap-llm01` only |

---

## Boot sequence

```
1. bcc-db-llm01: Postgres → MinIO
2. bcc-ap-infer01: SGLang
3. bcc-ap-llm01: mcp-tool@*  (all 6 in any order)
4. bcc-ap-llm01: gateway
5. SWA at rls.mymanatee.org auto-routes
```

Health check: `curl https://rls.mymanatee.org/healthz` → `200 {"gateway":"ok","mcp":[...],"sglang":"ok","db":"ok","minio":"ok"}`.

---

## Common ops

### Restart one MCP tool
```
sudo systemctl restart mcp-tool@retrieve.service
journalctl -u mcp-tool@retrieve.service -f
```

### Gateway restart (no downtime drain)
```
sudo systemctl reload gateway.service     # SIGHUP - drain in-flight then restart
```

### Rotate gateway → MCP signing keypair
```
cd /opt/rls-apex-v1
./bin/rotate-mcp-keys.sh                  # writes new keys to KV, updates all 6 tools, then gateway
sudo systemctl restart 'mcp-tool@*' gateway
```

### Reindex corpus
```
cd /opt/rls-apex-v1/mcp-tools/retrieve
python -m reindex --since 2026-01-01 --classifications=Public,Internal
# Privileged matters require manatee-civic-ai redaction first
```

### Pull RLS dataset for evals
```
cd eval/datasets
./pull-rls-v1.sh                # pulls + redacts via manatee-civic-ai pipeline
```

---

## Backups

| Asset | Frequency | Target | RTO / RPO |
|---|---|---|---|
| Postgres | nightly pg_basebackup | Azure Blob (cold) | 4h / 24h |
| MinIO | nightly snapshot | Azure Blob (cold) | 4h / 24h |
| Skills git repo | continuous (GitHub) | GitHub | 0 / 0 |
| LineageEvent | replicated to Postgres standby on bcc-ap-llm01 | live | 5m / 1m |

---

## Incident playbook

**Gateway 5xx burst** → check SGLang health on `bcc-ap-infer01:8000`, then circuit-breaker state via `/admin/breakers`.
**MCP tool not responding** → `systemctl status mcp-tool@<name>`, then check JWT clock skew (60s TTL).
**Postgres connection storm** → confirm pgBouncer pool, check for runaway DSPy chain (lineage table will show repeated identical input_hash).
**OIDC failures** → KV secret rotated? `AZURE_CLIENT_SECRET` expiry on the app reg? Check Entra ID sign-in logs.
**Privileged-matter classification missed** → IMMEDIATE: pull row from corpus index via `mcp-tools/docs admin/exclude <matter_id>`. Then write incident report.

---

## On-call surface (v0.1.0)

| Layer | Owner | Escalation |
|---|---|---|
| UI / SWA | you | Drew |
| Gateway / MCP | you | Drew |
| State (`bcc-db-llm01`) | you | Matthew (DBA) |
| Inference (`bcc-ap-infer01`) | you | Matthew |
| Edge (DNS, cert, IIS) | Chris/ITS | Chris/ITS |
| Entra ID / KV | Identity team | — |

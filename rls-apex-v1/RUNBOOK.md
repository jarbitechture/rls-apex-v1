# Runbook

Operational procedures. Boot order, healthchecks, recovery, common failure modes. Keep terse.

## Boot order

```
1. bcc-db-llm01    Postgres → AGE extension loaded → MinIO unit up
2. bcc-ap-infer01  SGLang serving Qwen2.5-FP8 on :8000
3. bcc-ap-llm01    mcp-tool@retrieve, @policy-graph, @ontology, @lineage,
                   @docs, @report-roi (loopback)
4. bcc-ap-llm01    gateway (FastAPI :443 behind reverse proxy)
5. apps/web        Static Web App auto-deployed by GH Actions
```

## Healthchecks

| Component | Endpoint | Expect |
|---|---|---|
| Gateway | `https://rls.mymanatee.org/healthz` | `200 {"status":"ok","build":"<sha>"}` |
| Gateway deep | `https://rls.mymanatee.org/healthz/deep` | All MCP tools `OK`, SGLang reachable, Postgres reachable, MinIO reachable |
| Each MCP tool | `http://127.0.0.1:301XX/healthz` | `200 {"tool":"<name>","ok":true}` |
| SGLang | `http://bcc-ap-infer01:8000/health` | `200` |
| Postgres+AGE | `psql -c "SELECT * FROM ag_catalog.ag_graph LIMIT 1"` | rows or empty, never error |
| MinIO | `mc admin info bcc-db-llm01` | quorum OK |

## Common failures

### Circuit breaker tripped on retrieve
Symptom: gateway returns `503 retrieve_unavailable`, sidecar event has `success=false, tool="retrieve"`.
Action: `journalctl -u mcp-tool@retrieve -n 200`. Most common cause is pgvector index rebuilding mid-query — wait + retry. Persistent failure: `systemctl restart mcp-tool@retrieve`.

### SGLang OOM
Symptom: 500 from gateway, Phoenix span shows `inference.latency > 60s` then timeout.
Action: confirm prompt token count under model context. If genuine OOM, restart SGLang with reduced `--max-running-requests`. **Never** swap to a larger Qwen variant under load — fall back to OpenAI by setting `INFERENCE_FALLBACK=openai` in gateway env (requires the disabled-by-default egress allowlist to be enabled by ops).

### MinIO ACL denial on a privileged matter
Symptom: `mcp.docs` returns `403 classification_denied`.
Action: this is **working as intended** unless the requester is `general-counsel` or the matter classification is wrong. Check `matters.classification` in Postgres. Never grant blanket override.

### Lineage chain break
Symptom: nightly Inspect AI flags `lineage.parent_missing`.
Action: a `LineageEvent` row exists with a `parent_id` pointing to a row that does not. Investigate which agent emitted the orphan. Do not delete the orphan — it's evidence of a bug. File and fix.

## Recovery

### Postgres restore
- Daily `pg_basebackup` to `bcc-ap-llm01:/backup/postgres/`.
- WAL shipped continuously.
- RPO: 5 min. RTO: 30 min for full restore.
- Procedure: `infra/bcc-db-llm01/restore.sh <target-time>`.

### MinIO restore
- Hourly snapshot to `bcc-ap-llm01:/backup/minio/`.
- Per-bucket replication to the same backup host.
- RPO: 1 hr. RTO: 15 min.

### Skills git rollback
- All Templates merged via PR. To revert: `git revert <merge-sha>` on `main`, GH Actions auto-redeploys.
- Hot-load picks up the revert within 60s (skills service polls).

## Secrets

All secrets in Azure Key Vault (`kv-bcc-rls-prod`). Each component pulls its own scope at boot:
- `kv://gateway-oidc-client-secret`
- `kv://gateway-jwt-signing-key` (RS256 keypair for MCP s2s)
- `kv://tool-retrieve-pg-conn`
- `kv://tool-docs-minio-creds`
- ... etc per tool

Rotation: 90 days. gMSA where the service account is on a Windows host.

## On-call decision tree

```
Gateway 5xx?
├─ /healthz fails           → restart gateway, page if persists 5min
├─ /healthz/deep fails on   → restart that MCP tool
│  one tool                 
├─ /healthz/deep fails on   → SGLang on infer01, see above
│  inference                
└─ residency violation in   → IMMEDIATELY block egress, page general-
   logs (anything to        counsel + IT security, post-mortem
   external host other      required.
   than allowlist)          
```

#!/usr/bin/env bash
# scripts/smoke.sh — manual end-to-end smoke for v0.2.0a backend.
# Usage: ./scripts/smoke.sh [base_url=http://localhost:8080]
set -euo pipefail
BASE="${1:-http://localhost:8080}"

echo "==> /healthz"
curl -fsS "$BASE/healthz"; echo

echo "==> /api/intake (free text → rlsPayload)"
INTAKE=$(curl -fsS -X POST "$BASE/api/intake" -H "Content-Type: application/json" \
  -d '{"text":"Need legal review on a permit denial for parcel 12345"}')
echo "$INTAKE" | python -m json.tool

PAYLOAD=$(echo "$INTAKE" | python -c "import sys,json; print(json.dumps(json.load(sys.stdin)['rlsPayload']))")

echo "==> /api/validate"
curl -fsS -X POST "$BASE/api/validate" -H "Content-Type: application/json" \
  -d "{\"rlsPayload\":$PAYLOAD}" | python -m json.tool

echo "==> /api/health/breakers"
curl -fsS "$BASE/api/health/breakers" | python -m json.tool

echo "==> done"

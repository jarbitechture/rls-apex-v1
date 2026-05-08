#!/usr/bin/env bash
# Capture per-panel Servo screenshots. Usage: bash tests/visual/run.sh [--update]
# Compares against baseline/*.png unless --update flag is passed.
set -euo pipefail
cd "$(dirname "$0")"

SERVO="${SERVO:-$HOME/Projects/servo/target/release/servoshell}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8080}"
BASELINE_DIR="baseline"
CURRENT_DIR="current"
UPDATE=false

for arg in "$@"; do
  case "$arg" in
    --update) UPDATE=true ;;
  esac
done

mkdir -p "$BASELINE_DIR" "$CURRENT_DIR"

# (panel-name, hash-route, settle-ms)
panels=(
  "intake|#step=intake|600"
  "form|#step=form|800"
  "status|#step=status|800"
  "cure|#step=cure|800"
  "submit|#step=submit|600"
  "cao|/cao/RLS-25-067|1000"
  "feed|#step=form|800"  # feed is in the rail; capture alongside form
)

for entry in "${panels[@]}"; do
  IFS='|' read -r name route settle <<< "$entry"
  out="$CURRENT_DIR/${name}.png"
  url="${BASE_URL}/static/index.html${route}"
  if [[ "$route" == /* ]]; then
    url="${BASE_URL}${route}"
  fi
  echo "==> Capturing $name from $url"
  timeout 30 "$SERVO" -z -x --device-pixel-ratio 2.0 -o "$out" "$url" || {
    echo "✗ servo failed for $name"; exit 1
  }
  sleep "$(awk "BEGIN{print $settle/1000}")"
done

if $UPDATE; then
  cp "$CURRENT_DIR"/*.png "$BASELINE_DIR/"
  echo "✓ baselines updated"
else
  for entry in "${panels[@]}"; do
    IFS='|' read -r name _ _ <<< "$entry"
    if [[ -f "$BASELINE_DIR/$name.png" ]]; then
      if ! cmp -s "$BASELINE_DIR/$name.png" "$CURRENT_DIR/$name.png"; then
        echo "✗ visual drift on $name; diff: open $CURRENT_DIR/$name.png"
        exit 1
      fi
    else
      echo "⚠ no baseline for $name; run with --update to create"
    fi
  done
  echo "✓ all panels match baseline"
fi

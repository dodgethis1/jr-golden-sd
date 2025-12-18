#!/usr/bin/env bash
set -euo pipefail
URL="${1:-http://127.0.0.1:8025/api/health}"
TRIES="${2:-80}"
SLEEP="${3:-0.25}"

for i in $(seq 1 "$TRIES"); do
  if curl -fsS --max-time 1 "$URL" >/tmp/health.json 2>/dev/null; then
    exit 0
  fi
  sleep "$SLEEP"
done

echo "ERROR: health never came up: $URL" >&2
exit 1

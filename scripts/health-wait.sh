#!/usr/bin/env bash
set -u

URL="${1:-http://127.0.0.1:8025/api/health}"
TRIES="${2:-40}"     # 40 * 0.5s = ~20s
SLEEP="${3:-0.5}"

for ((i=1; i<=TRIES; i++)); do
  if out="$(curl -fsS --max-time 2 "$URL" 2>/dev/null)"; then
    if [[ -n "${out//[[:space:]]/}" ]]; then
      echo "$out"
      exit 0
    fi
  fi
  sleep "$SLEEP"
done

echo "FAILED: $URL never returned non-empty after ~$((TRIES))/2 seconds" >&2
exit 1

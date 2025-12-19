#!/usr/bin/env bash
set -euo pipefail
cd /opt/jr-pi-toolkit/golden-sd || exit 1

echo "[handoff-post] starting (waiting for /api/health)..."

ok=0
for i in $(seq 1 40); do
  if curl -fsS --max-time 1 http://127.0.0.1:8025/api/health >/dev/null 2>&1; then
    ok=1; break
  fi
  sleep 0.5
done

if [ "$ok" -ne 1 ]; then
  echo "[handoff-post] WARNING: /api/health not reachable after wait; still writing paste"
fi

HANDOFF_PHASE=post .venv/bin/python scripts/gen-handoff-paste.py || true
echo "[handoff-post] done"

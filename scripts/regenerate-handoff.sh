#!/usr/bin/env bash
set -euo pipefail

cd /opt/jr-pi-toolkit/golden-sd || exit 1

URL="http://127.0.0.1:8025/api/health"

# Wait briefly for backend to be reachable (handles restarts)
for i in $(seq 1 80); do
  if curl -fsS --max-time 1 "$URL" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

.venv/bin/python scripts/gen-handoff-paste.py

echo "OK: wrote docs/HANDOFF_PASTE.md"
ls -la docs/HANDOFF_PASTE.md
echo
sed -n '1,45p' docs/HANDOFF_PASTE.md

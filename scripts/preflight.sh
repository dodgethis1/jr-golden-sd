#!/usr/bin/env bash
set -euo pipefail
cd /opt/jr-pi-toolkit/golden-sd || exit 1

echo "=== python syntax ==="
python3 -m py_compile app/app.py
echo "OK: app/app.py compiles"

echo
echo "=== UI sanity ==="
if grep -nE '\+\s*/tail\?lines=' static/index.html; then
  echo "BAD: broken '+ /tail?lines=' pattern found in static/index.html" >&2
  exit 3
fi
echo "OK: UI tail concat looks sane"

echo
echo "=== restart service + wait for health ==="
sudo systemctl restart jr-golden-sd.service >/dev/null 2>&1 || true
./scripts/health-wait.sh http://127.0.0.1:8025/api/health 80 0.25
echo "OK: /api/health responds"
python3 -m json.tool </tmp/health.json || cat /tmp/health.json

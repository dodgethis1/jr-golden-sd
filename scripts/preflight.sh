#!/usr/bin/env bash
set -euo pipefail
cd /opt/jr-pi-toolkit/golden-sd || exit 1

echo "=== python syntax ==="
python3 -m py_compile app/app.py
echo "OK: app/app.py compiles"

echo
echo "=== UI sanity ==="
# Catch the exact bug you hit (unquoted /tail concatenation)
if grep -nE '\+\s*/tail\?lines=' static/index.html; then
  echo "BAD: broken '+ /tail?lines=' pattern found"
  exit 3
fi
echo "OK: UI tail concat looks sane"

echo
echo "=== service health ==="
sudo systemctl restart jr-golden-sd.service >/dev/null 2>&1 || true
for i in $(seq 1 80); do
  if curl -fsS --max-time 1 http://127.0.0.1:8025/api/health >/dev/null 2>&1; then
    echo "OK: /api/health responds"
    exit 0
  fi
  sleep 0.25
done

echo "BAD: /api/health did not respond after restart"
sudo systemctl status jr-golden-sd.service --no-pager -l || true
sudo journalctl -u jr-golden-sd.service -n 120 --no-pager || true
exit 4

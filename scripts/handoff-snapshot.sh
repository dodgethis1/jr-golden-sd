#!/usr/bin/env bash
set -euo pipefail
cd /opt/jr-pi-toolkit/golden-sd || exit 1

echo "=== repo ==="
echo "path: $(pwd)"
echo "branch: $(git branch --show-current)"
echo "commit: $(git rev-parse --short=12 HEAD)"
echo "describe: $(git describe --tags --dirty --always 2>/dev/null || true)"
echo

echo "=== systemd ==="
sudo systemctl status jr-golden-sd.service --no-pager -l || true
echo

echo "=== listening 8025 ==="
sudo ss -ltnp | grep -E ':8025\b' || echo "NOT LISTENING on 8025"
echo

echo "=== health ==="
curl -fsS http://127.0.0.1:8025/api/health | python3 -m json.tool || true
echo

echo "=== safety ==="
curl -fsS http://127.0.0.1:8025/api/safety | python3 -m json.tool || true
echo

echo "=== jobs dir ==="
ls -la cache/jobs 2>/dev/null | head -n 40 || echo "no cache/jobs yet"

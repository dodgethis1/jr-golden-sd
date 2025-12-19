#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8025}"

echo "=== listen ==="
sudo ss -ltnp | grep -E ':8025\b' || echo "NOT LISTENING on 8025"

echo
echo "=== systemd (top) ==="
sudo systemctl status jr-golden-sd.service --no-pager -l | sed -n '1,35p' || true

echo
echo "=== api quick ==="
for ep in health urls safety disks arm_status; do
  echo "--- $BASE_URL/api/$ep ---"
  curl -fsS --max-time 2 "$BASE_URL/api/$ep" | head -c 500; echo
done

echo
echo "=== ui html (first 25 lines) ==="
curl -fsS --max-time 2 "$BASE_URL/" | sed -n '1,25p'

echo
echo "OK: verify complete"

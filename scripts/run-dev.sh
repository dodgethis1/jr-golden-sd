#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1

PORT="${PORT:-8025}"
BIND="${BIND:-0.0.0.0:${PORT}}"
WORKERS="${WORKERS:-2}"

echo "=== JR Golden SD: dev server ==="
echo "repo:    $(pwd)"
echo "bind:    ${BIND}"
echo "workers: ${WORKERS}"
echo
echo "Stopping systemd service (so the port is free)..."
sudo systemctl stop jr-golden-sd.service || true

if [ ! -x ".venv/bin/gunicorn" ]; then
  echo "ERROR: .venv/bin/gunicorn not found. Run: ./scripts/bootstrap.sh" >&2
  exit 1
fi

echo
echo "Starting gunicorn with --reload (CTRL-C to stop)..."
exec .venv/bin/gunicorn \
  -w "${WORKERS}" \
  -b "${BIND}" \
  --reload \
  --access-logfile - \
  --error-logfile - \
  app.app:app

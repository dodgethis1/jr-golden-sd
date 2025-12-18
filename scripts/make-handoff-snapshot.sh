#!/usr/bin/env bash
set -euo pipefail
cd /opt/jr-pi-toolkit/golden-sd || exit 1

out="docs/STATE_SNAPSHOT.md"
mkdir -p docs

{
  echo "# Golden SD State Snapshot"
  echo
  echo "Generated: $(date -Is)"
  echo

  echo "## Git"
  echo '```'
  git status -sb || true
  git remote -v || true
  git log -1 --oneline || true
  echo '```'
  echo

  echo "## Service"
  echo '```'
  sudo systemctl status jr-golden-sd.service --no-pager -l || true
  echo '```'
  echo

  echo "## Listening (8025)"
  echo '```'
  sudo ss -ltnp | grep -E ':8025\b' || echo "NOT LISTENING on 8025"
  echo '```'
  echo

  echo "## Health + Safety"
  echo '```'
  curl -fsS http://127.0.0.1:8025/api/health || true
  echo
  curl -fsS http://127.0.0.1:8025/api/safety || true
  echo '```'
  echo

  echo "## UI files (static/)"
  echo '```'
  find static -maxdepth 4 -type f -print 2>/dev/null || echo "No static/ files found"
  echo '```'
  echo

  echo "## UI references to API routes"
  echo '```'
  grep -RIn --exclude='*.map' -E '/api/|download_os|plan_flash|arm_status|job/' static 2>/dev/null | head -n 400 || true
  echo '```'
  echo

  echo "## Flask route decorators (app/app.py)"
  echo '```'
  grep -nE '^\s*@app\.(get|post|route)\("' app/app.py | head -n 250 || true
  echo '```'
} > "$out"

echo "Wrote $out"

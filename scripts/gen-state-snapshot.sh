#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1

out="docs/STATE_SNAPSHOT.md"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

ts="$(date -Is)"
host="$(hostname)"
repo="$(pwd)"
git_commit="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
git_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"

json_block_file() {
  local f="$1"
  echo '```json'
  python3 -m json.tool <"$f"
  echo '```'
}

dump_flask_routes() {
  # Emit JSON list of Flask routes (rule, methods, endpoint).
  # Uses app.app:app (the same object gunicorn serves).
  if [ -x .venv/bin/python ]; then
    .venv/bin/python -c '
from app.app import app
import json
items=[]
for r in app.url_map.iter_rules():
    methods=sorted([m for m in r.methods if m not in ("HEAD","OPTIONS")])
    items.append({"rule": r.rule, "methods": methods, "endpoint": r.endpoint})
items=sorted(items, key=lambda d: d["rule"])
print(json.dumps({"routes": items}, indent=2))
' > "$tmpdir/routes.json" || true
  fi
}

mkdir -p docs

# Try to collect runtime API info (best-effort, don’t fail the script).
curl -fsS http://127.0.0.1:8025/api/urls   >"$tmpdir/urls.json"   2>/dev/null || true
curl -fsS http://127.0.0.1:8025/api/health >"$tmpdir/health.json" 2>/dev/null || true
curl -fsS http://127.0.0.1:8025/api/safety >"$tmpdir/safety.json" 2>/dev/null || true
dump_flask_routes

{
  echo "# STATE SNAPSHOT"
  echo
  echo "- Generated: ${ts}"
  echo "- Host: ${host}"
  echo "- Repo: ${repo}"
  echo "- Branch: ${git_branch}"
  echo "- Commit: ${git_commit}"
  echo

  echo "## Base URLs (from /api/urls if available)"
  if [ -s "$tmpdir/urls.json" ]; then
    json_block_file "$tmpdir/urls.json"
  else
    echo "- (Could not fetch /api/urls)"
  fi
  echo

  echo "## Flask routes (runtime url_map)"
  if [ -s "$tmpdir/routes.json" ]; then
    json_block_file "$tmpdir/routes.json"
  else
    echo "- (Could not dump routes; check venv + import path)"
  fi
  echo

  echo "## Frontend files (static/)"
  if [ -d static ]; then
    # Ignore backup copies and sourcemaps
    find static -maxdepth 3 -type f \
      ! -name '*.bak.*' \
      ! -name '*.map' \
      -print | sort | sed 's/^/- `/' | sed 's/$/`/'
  else
    echo "- (No static/ directory found)"
  fi
  echo

  echo "## Frontend references to API routes (best-effort)"
  if [ -d static ]; then
    grep -RIn \
      --exclude='*.bak.*' \
      --exclude='*.map' \
      -Eo '\/api\/[a-zA-Z0-9_\/\-\.\?\=\&]+' static 2>/dev/null \
      | awk -F: '{print $3}' \
      | python3 -c 'import sys,html; [print(html.unescape(l.rstrip("\n"))) for l in sys.stdin]' \
      | sort -u \
      | sed 's/^/- `/' | sed 's/$/`/' || true
  fi
  echo

  echo "## Health + safety (current)"
  if [ -s "$tmpdir/health.json" ]; then
    echo "### /api/health"
    json_block_file "$tmpdir/health.json"
    echo
  fi
  if [ -s "$tmpdir/safety.json" ]; then
    echo "### /api/safety"
    json_block_file "$tmpdir/safety.json"
  fi
} > "$out"

echo "Wrote $out"

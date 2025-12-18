#!/usr/bin/env bash
set -euo pipefail
cd /opt/jr-pi-toolkit/golden-sd || exit 1

TAG="${1:-v0.1.0}"

echo "=== require clean worktree ==="
if [ -n "$(git status --porcelain)" ]; then
  echo "ERROR: working tree not clean:" >&2
  git status --porcelain >&2
  exit 2
fi

./scripts/preflight.sh

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "ERROR: tag already exists: $TAG" >&2
  exit 3
fi

git tag -a "$TAG" -m "JR Golden SD $TAG"
git push origin main
git push origin "$TAG"
echo "OK: tagged + pushed $TAG"

#!/usr/bin/env bash
set -euo pipefail
msg="${1:-"update"}"

./scripts/gen_chat_handoff.sh

git add -A
git commit -m "$msg"

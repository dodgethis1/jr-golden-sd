#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$BASE_DIR"

VERSION="$(git describe --tags --always --dirty 2>/dev/null || echo "0.0.0-dev")"
NOW="$(date -Is)"

cat > docs/CHAT_HANDOFF.md <<EOF
# CHAT_HANDOFF (paste this into a new ChatGPT window)

Recipient: ChatGPT (the assistant)

Project: JR Golden SD (Pi 5 + Pi 4 compatible), headless-first provisioning SD with web UI.

As of: $NOW
Version: $VERSION

Read these files first:
- docs/SPEC.md
- docs/SAFETY_MODEL.md
- docs/ARCHITECTURE.md
- docs/HEADLESS_UX.md
- docs/OS_CATALOG.md
- docs/ADDONS.md
- docs/STACKS.md
- docs/FIRST_BOOT.md
- docs/UPDATES.md
- docs/TEST_MATRIX.md

Current state:
- Python/Flask backend: app/app.py
- Static web UI: static/index.html
- API: /api/health and /api/disks (read-only)

Runtime:
- Location on Pi: $BASE_DIR
- Start command: $BASE_DIR/.venv/bin/python $BASE_DIR/app/app.py
- Port: 8025 (env override JR_GOLDEN_SD_PORT)

Safety definition:
- "Safe" = read-only discovery + downloads to cache folder.
- Destructive actions (flash/wipe) MUST require: not-root target + typed confirm + explicit arming.
EOF

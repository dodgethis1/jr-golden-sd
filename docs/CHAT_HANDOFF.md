# CHAT_HANDOFF (paste this into a new ChatGPT window)

Recipient: ChatGPT (the assistant)

Project: JR Golden SD (Pi 5 + Pi 4 compatible), headless-first provisioning SD with web UI.

As of: 2025-12-18T10:06:21-06:00
Version: 5eb11fd-dirty

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
- Location on Pi: /opt/jr-pi-toolkit/golden-sd
- Start command: /opt/jr-pi-toolkit/golden-sd/.venv/bin/python /opt/jr-pi-toolkit/golden-sd/app/app.py
- Port: 8025 (env override JR_GOLDEN_SD_PORT)

Safety definition:
- "Safe" = read-only discovery + downloads to cache folder.
- Destructive actions (flash/wipe) MUST require: not-root target + typed confirm + explicit arming.

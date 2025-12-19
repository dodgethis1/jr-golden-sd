# Contributing / House Rules (JR Golden SD Web UI)

This project is built to be idiot-resistant and safe by default. Assume pasting can get mangled. Assume users can misclick. Design accordingly.

## Safety and scope (current stable expectations)
- Disk flashing is NOT enabled in stable unless explicitly gated.
- /api/plan_flash is DRY-RUN unless later enabled behind hard gates.
- /api/download_os is allowed only in Golden SD mode and writes only under cache/ (no block device writes).

## Paste reliability rules (Jason-proof)
- Keep paste blocks short and self-contained.
- One heredoc max per paste block. Avoid nested heredocs.
- Two-step workflow: write files, then verify (smoke).
- Prefer JSON parsing assertions, not grep on pretty output.
- Never paste Python decorators like @app.get(...) into bash.

## Repo layout
- app/app.py : Flask app + API routes + safety checks
- data/os-providers/ : provider source definitions
- cache/ : provider caches, downloads, job artifacts (ignored in git)
- static/index.html : UI + job monitor wiring
- docs/ : canonical docs and handoffs
- scripts/ : smoke tests + ops helpers

## Generated handoff
- Canonical handoff: docs/HANDOFF_CHATGPT.md (or docs/HANDOFF.md)
- Generated paste handoff: docs/HANDOFF_PASTE.md (should be gitignored)
- Generator: scripts/gen-handoff-paste.py
- If systemd runs generator via ExecStartPost, it must be non-fatal:
  ExecStartPost=-/opt/jr-pi-toolkit/golden-sd/.venv/bin/python /opt/jr-pi-toolkit/golden-sd/scripts/gen-handoff-paste.py

## Smoke tests
Run after changes to catalog, jobs, safety gates, or endpoints:

  cd /opt/jr-pi-toolkit/golden-sd || exit 1
  ./scripts/smoke-all.sh

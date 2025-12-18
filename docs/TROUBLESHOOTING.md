# Troubleshooting notes

## "Flashing is disabled (policy.flash_enabled=false)."
Expected until policy enables flashing. /api/flash should refuse with HTTP 403.

## JSONDecodeError loop
This happens when a script does json.load(...) on empty input.
Most common causes:
- curl failed (connection refused, timeout, etc) and wrote nothing
- service restarted mid-request and the client saved an empty file
Fix patterns:
- use: curl -fsS (fail on non-200 and no HTML junk)
- verify file non-empty before python parses:
  - test -s /tmp/file.json
- in python, catch JSONDecodeError and print body for debugging

## Service restarts
jr-golden-sd.service restarts show up as gunicorn workers receiving SIGTERM.
If this coincides with client polling loops, you can get empty responses.

## Preflight check (recommended before pushes/releases)
Run:
- `./scripts/preflight.sh`

It checks:
- Python syntax (`py_compile`)
- UI obvious breakage patterns
- Service restart + `/api/health` comes back

## SSH disconnect gotcha (interactive `set -e`)
If you run `set -e` in an interactive SSH shell, any failing command exits your shell and drops SSH.
Policy:
- Interactive: `set -u` (and optional `pipefail`), handle failures explicitly.
- Scripts: `set -euo pipefail`.

Use `./scripts/preflight.sh` and `./scripts/health-wait.sh` instead of one-shot curls after restarts.

## Restart window false-fails
Immediately curling after `systemctl restart` can fail even when the service is fine.
Use:
- `./scripts/health-wait.sh http://127.0.0.1:8025/api/health 80 0.25`

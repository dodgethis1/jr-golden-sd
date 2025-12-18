# JR Golden SD Web UI - Handoff (Recipient: ChatGPT)

## Project
- Repo path: `/opt/jr-pi-toolkit/golden-sd`
- GitHub: `git@github.com:dodgethis1/jr-golden-sd.git`
- Branch: `main`

## Runtime / Service
- systemd unit: `jr-golden-sd.service`
- App server: gunicorn (serving Flask `app.app:app`)
- Bind: `0.0.0.0:8025`
- Health: `GET http://127.0.0.1:8025/api/health`

## Quick snapshot for a new ChatGPT window

Run this on the Pi and paste the output into the new chat:

```bash
cd /opt/jr-pi-toolkit/golden-sd || exit 1
./scripts/handoff-snapshot.sh
```

## Current mode + safety model
- Intended safe mode: **SD**
- `/api/health` reports:
  - `mode: SD`
  - `root_source: /dev/mmcblk0p2`
  - `root_parent: mmcblk0`
- `/api/safety` reports (expected baseline):
  - `flash_enabled: false` (policy default safe)
  - `requires_sd_mode: true`
  - `root_disk_blocked: true`
  - `write_word: "ERASE"`
  - `arm_ttl_seconds: 600`
  - `eligible_targets`: includes NVMe `/dev/nvme0n1` (TEAM TM5FF3001T ~953.9G)

### Safe operations definition (this stage)
Allowed:
- list disks, OS catalog search, cache inspection, download OS to cache, dry-run planning, arm/disarm tokens
Not allowed (default):
- any real flash/write until `policy.flash_enabled=true` AND arm/confirm gates are satisfied

## Key API routes
- `GET /api/health`
- `GET /api/urls`
- `GET /api/safety`
- `GET /api/disks`
- `GET /api/os?q=...`
- `POST /api/plan_flash` (dry run only)
- `GET /api/arm_status`
- `POST /api/arm`
- `POST /api/disarm`
- `GET /api/job/<job_id>`
- `GET /api/job/<job_id>/tail?lines=...` (log tail)
- `GET /api/os_cache?os_id=...`
- `POST /api/download_os` (background job)
- `GET /api/qr`
- `POST /api/flash` exists but should return 403 when flashing disabled by policy

## Jobs system
- Stored under: `cache/jobs/`
  - `*.json` job state
  - `*.log` stdout/stderr
  - `*.rc` exit code
<!-- DOC_RC_WINS_NOTE -->
### Job status resolution
- The presence of `cache/jobs/<job_id>.rc` is **authoritative** for completion.
  - `rc == 0` → `status = success`
  - `rc != 0` → `status = failed`
- If the `.rc` file is **absent**, the job may be considered `running` only if the recorded `pid` still exists (e.g., `/proc/<pid>` exists).

  - `*.sh` generated script
- `start_job()` writes a bash script with `trap 'echo $? > rcfile' EXIT` and runs detached; logs to `*.log`.
- `job_refresh()` marks success/failed by reading rcfile if pid is gone.

## OS cache
- Stored under: `cache/os/` as `<key>.bin` with `<key>.meta.json`

## UI architecture (MISSING IN EARLIER HANDOFF, NOW TRACKED HERE)
- There are **no** Flask templates (`app/templates` missing).
- UI assets are in repo-root `static/` (served as static files).
- Any UI work (job polling/log tail) requires editing files under `static/`.
- The definitive UI file list + API call references should be captured in `docs/STATE_SNAPSHOT.md`.

## Known gotchas
- Restart timing: immediate curl after restart can fail (`curl: (7) ... after 0 ms`). Use a retry loop.
- `last` isn’t installed on this OS; use `who -b` and `journalctl --list-boots`.

## What we’re building next
- Web UI should poll:
  - `/api/job/<job_id>` for status
  - `/api/job/<job_id>/tail?lines=200` for live logs
- Goal: live job view without any disk-write capabilities.

## UI map (critical)
- Frontend is a single file: `static/index.html`
- Served by Flask:
  - `/` -> `static/index.html`
  - `/assets/<path>` -> static files

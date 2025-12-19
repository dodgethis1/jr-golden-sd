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

<!-- PASTE_SAFETY_RULES -->
## Paste-safe instructions rules (for ChatGPT + operator)

**Goal:** Prevent “mangled paste” failures during Windows PowerShell → SSH → bash workflows.

### What a heredoc is (plain English)
A *heredoc* is a shell feature that writes a multi-line block into a file, typically using `<<EOF` ... `EOF`.
If the closing terminator line (like `EOF`) gets corrupted or dropped mid-paste, the shell may keep consuming input and break the session.

### Rules for all copy/paste blocks we generate
1. **One heredoc maximum per paste block.**  
   If we need multiple files, split into multiple paste blocks.
2. **No nested heredocs.**  
   Avoid heredocs inside scripts that themselves contain heredocs.
3. **Two-step flow:**  
   - Step A: write file(s)  
   - Step B: run/verify  
   Never mix “write + execute” in the same paste when it’s large or delicate.
4. **Interactive safety mode by default:**  
   Use `set -u` for interactive/debug steps so one failure doesn’t nuke the SSH session.  
   Use `set -euo pipefail` only for short, final scripts where failing fast is desired.
5. **Delimiter hygiene:**  
   Heredoc terminators (`EOF`, `PY`, `SH`, etc.) must be **alone on a line**, with **no spaces** and no indentation.
6. **Whitespace-proof validation:**  
   Don’t grep JSON strings with exact spacing. Parse JSON (e.g., `python3 -m json.tool` or a small Python `json.loads`) to assert values.
7. **Minimize paste size:**  
   Prefer smaller, sequential paste blocks over one giant paste blob.

### Operator hint
If a paste gets mangled, the fix is usually: **overwrite the target file completely** with a clean paste block, then re-run the command.

## Regenerate HANDOFF_PASTE.md
- `docs/HANDOFF_PASTE.md` is generated automatically on service start.
- During startup/restart it may briefly show `service_active: activating` or `health_ok: false` due to timing.
- To refresh it after the backend is actually reachable, run:

```bash
cd /opt/jr-pi-toolkit/golden-sd || exit 1
./scripts/regenerate-handoff.sh
```

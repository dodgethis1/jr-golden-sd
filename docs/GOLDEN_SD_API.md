# Golden SD Web UI API (port 8025)

Repo path: /opt/jr-pi-toolkit/golden-sd
Service: jr-golden-sd.service
App: app/app.py (Flask), served by gunicorn
Health check: GET http://127.0.0.1:8025/api/health

## Safety model summary
- Root disk is blocked (always).
- Eligible targets come from /api/safety -> eligible_targets.
- Writes are only allowed when:
  - safety_state().can_flash_here == true (SD mode requirement)
  - policy.flash_enabled == true
  - Valid ARM token (short TTL) matches target + os_id

## Endpoints
GET  /api/health
  -> { ok, version, mode, root_source, root_parent }

GET  /api/safety
  -> policy (flash_enabled, write_word, ttl), armed state, eligible_targets, mode/root info

GET  /api/disks
  -> disk inventory + eligible targets (root disk excluded)

GET  /api/os?q=...
  -> OS catalog filtered by name/description

POST /api/plan_flash   (DRY-RUN ONLY)
  body: { target, os_id }
  -> plan + warnings + steps (no writes)

GET  /api/os_cache?os_id=...
  -> whether cached + paths + meta

POST /api/download_os
  body: { os_id }
  -> starts a background job that downloads to cache/os/<key>.bin

GET  /api/job/<job_id>
  -> job status + paths (logs are on disk)

POST /api/arm
  body: { target, os_id, word, confirm_target, serial_suffix? }
  -> stores short-lived token (no writes)

POST /api/disarm
  -> clears arm state

POST /api/flash   (DESTRUCTIVE)
  body: { target, os_id?, token, confirm_target?, serial_suffix? }
  -> only runs if policy.flash_enabled==true and ARM matches
  -> disarms immediately (one-shot) and starts a "flash" job that writes via dd

GET  /api/qr?u=...
  -> QR code PNG for URL

## GET /api/job/<job_id>/tail?lines=200
Read-only log tail for a job.

- Purpose: UI can show live logs without shell access.
- Params:
  - `lines` (optional, default 200, max 2000)
- Returns:
  - `lines`: array of strings (log lines)
  - `truncated`: bool (true if older content was dropped)
  - `mtime`: float (mtime epoch seconds)
- Errors:
  - 404 if log does not exist
  - 400 on invalid job_id

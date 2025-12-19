# systemd service notes (JR Golden SD)

This project runs as a systemd service:

- Unit: `/etc/systemd/system/jr-golden-sd.service`
- Drop-ins: `/etc/systemd/system/jr-golden-sd.service.d/*.conf`
- Repo: `/opt/jr-pi-toolkit/golden-sd`

## Why HANDOFF_PASTE can show “activating / start-post”
We generate `docs/HANDOFF_PASTE.md` from an `ExecStartPost=` hook (`scripts/handoff-post.sh`).

While `ExecStartPost` is running, systemd reports:

- `ActiveState=activating`
- `SubState=start-post`

That is expected. The important signals are:

- `Phase: post` in `docs/HANDOFF_PASTE.md`
- `health_ok: true`
- `/api/health` reachable

Once `ExecStartPost` exits, the service becomes `ActiveState=active` / `SubState=running`.

## Drop-in ordering gotcha
Drop-ins apply in lexicographic order. If a later drop-in clears `ExecStartPost`, it will override earlier ones.

We intentionally keep startup resilient (avoid restart loops) by allowing the base unit to start even if helper scripts are missing.
If you add an `ExecStartPost` hook, prefer an ignore-errors form in the drop-in:

- `ExecStartPost=-/opt/jr-pi-toolkit/golden-sd/scripts/handoff-post.sh`

## What is and isn’t in git
Repo scripts/docs are in git.
System configuration under `/etc/systemd/...` is not in git by default.

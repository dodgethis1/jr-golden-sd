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
Drop-ins apply in lexicographic order. If a later drop-in clears `ExecStartPost`, it overrides earlier ones.

If you want the post-start handoff, ensure the drop-in that sets it sorts *after* any drop-in that clears it.
Also consider making the post hook non-fatal to startup:

Example (recommended):
- `ExecStartPost=-/opt/jr-pi-toolkit/golden-sd/scripts/handoff-post.sh`

That way the web UI still starts even if the handoff script is missing/broken.

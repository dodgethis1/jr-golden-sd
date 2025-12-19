from __future__ import annotations

import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SERVICE = "jr-golden-sd.service"
BASE_URL = "http://127.0.0.1:8025"
HEALTH_URL = f"{BASE_URL}/api/health"

def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    p = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    return p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip()

def try_json(url: str, timeout: float = 2.0) -> dict:
    try:
        req = Request(url, headers={"User-Agent": "jr-golden-sd-handoff-gen"})
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}

def systemd_state() -> tuple[str, str]:
    # Prefer 'systemctl show' so we can report both ActiveState/SubState.
    try:
        p = subprocess.run(
            ["systemctl", "show", SERVICE, "-p", "ActiveState", "-p", "SubState"],
            text=True, capture_output=True, check=False
        )
        active = "unknown"
        sub = "unknown"
        for line in (p.stdout or "").splitlines():
            if line.startswith("ActiveState="):
                active = line.split("=", 1)[1].strip() or "unknown"
            elif line.startswith("SubState="):
                sub = line.split("=", 1)[1].strip() or "unknown"
        return active, sub
    except Exception:
        return "unknown", "unknown"

def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    docs = repo / "docs"
    docs.mkdir(parents=True, exist_ok=True)

    # Git facts (best effort)
    rc, git_commit, _ = run(["git", "rev-parse", "--short", "HEAD"], repo)
    if rc != 0:
        git_commit = "UNKNOWN"
    rc, git_describe, _ = run(["git", "describe", "--always", "--dirty"], repo)
    if rc != 0:
        git_describe = "UNKNOWN"
    rc, git_branch, _ = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo)
    if rc != 0:
        git_branch = "UNKNOWN"
    rc, porcelain, _ = run(["git", "status", "--porcelain=v1"], repo)
    git_dirty = bool(porcelain.strip())

    # Service facts (best effort)
    active_state, sub_state = systemd_state()
    rc, enabled, _ = run(["systemctl", "is-enabled", SERVICE], repo)
    if rc != 0:
        enabled = "unknown"

    # IMPORTANT: ALWAYS attempt health (even if systemd is "activating")
    health = try_json(HEALTH_URL, timeout=2.0)

    host = socket.gethostname()
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    phase = os.environ.get("HANDOFF_PHASE", "").strip() or "unknown"

    canonical = docs / "HANDOFF_CHATGPT.md"
    if not canonical.exists():
        canonical = docs / "HANDOFF.md"

    canonical_text = ""
    if canonical.exists():
        canonical_text = canonical.read_text(encoding="utf-8", errors="replace").rstrip()

    out: list[str] = []
    out.append("HANDOFF (recipient: ChatGPT)\n\n")
    out.append(f"Generated: {now}\n")
    out.append(f"Phase: {phase}\n\n")
    out.append("Project: JR Golden SD Web UI\n")
    out.append(f"Host: {host}\n")
    out.append(f"Repo path: {repo}\n")
    out.append(f"Service: {SERVICE} (gunicorn)\n")
    out.append(f"Base URL: {BASE_URL}\n\n")

    out.append("Runtime facts:\n")
    out.append(f"- git_commit: {git_commit}\n")
    out.append(f"- git_describe: {git_describe}\n")
    out.append(f"- git_branch: {git_branch}\n")
    out.append(f"- git_dirty: {str(git_dirty).lower()}\n")
    out.append(f"- service_active_state: {active_state}\n")
    out.append(f"- service_sub_state: {sub_state}\n")
    out.append(f"- service_enabled: {enabled}\n")

    ok = health.get("ok", None)
    if ok is True:
        out.append("- health_ok: true\n")
        if "mode" in health:
            out.append(f"- mode: {health.get('mode')}\n")
        if "version" in health:
            out.append(f"- version: {health.get('version')}\n")
    elif ok is False:
        out.append("- health_ok: false\n")
        if "error" in health:
            out.append(f"- health_error: {health.get('error')}\n")
    else:
        out.append("- health_ok: unknown\n")
    out.append("\n")

    out.append("Paste-safe rules:\n")
    out.append("- Keep paste blocks short (avoid huge multi-hundred-line pastes).\n")
    out.append("- One heredoc max per paste block; no nested heredocs.\n")
    out.append("- Two-step flow: write files first, then run/verify.\n")
    out.append("- Prefer JSON parsing for assertions (don’t grep whitespace-sensitive output).\n")
    out.append("- Avoid pasting anything that starts with '@app.' into bash (that’s Python code).\n\n")

    if canonical_text:
        out.append(f"=== Canonical handoff content ({canonical.name}) ===\n\n")
        out.append(canonical_text + "\n")
    else:
        out.append("NOTE: No canonical handoff doc found in docs/ (HANDOFF_CHATGPT.md or HANDOFF.md).\n")

    (docs / "HANDOFF_PASTE.md").write_text("".join(out), encoding="utf-8")
    print("OK: wrote docs/HANDOFF_PASTE.md")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

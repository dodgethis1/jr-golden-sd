from __future__ import annotations

import json
import socket
import subprocess
import time
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

def main() -> int:
    repo = Path(__file__).resolve().parents[1]
    docs = repo / "docs"
    docs.mkdir(parents=True, exist_ok=True)

    # Git facts (best effort)
    rc, git_commit, _ = run(["git","rev-parse","--short","HEAD"], repo)
    if rc != 0: git_commit = "UNKNOWN"
    rc, git_describe, _ = run(["git","describe","--always","--dirty"], repo)
    if rc != 0: git_describe = "UNKNOWN"
    rc, git_branch, _ = run(["git","rev-parse","--abbrev-ref","HEAD"], repo)
    if rc != 0: git_branch = "UNKNOWN"
    rc, porcelain, _ = run(["git","status","--porcelain=v1"], repo)
    git_dirty = bool(porcelain.strip())

    # Service facts (best effort)
    rc, active, _ = run(["systemctl","is-active",SERVICE], repo)
    rc, enabled, _ = run(["systemctl","is-enabled",SERVICE], repo)

    health = {}
    for _ in range(40):
        health = try_json(HEALTH_URL, timeout=1.5)
        if health.get("ok"):
            break
        time.sleep(0.25)

    host = socket.gethostname()
    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")

    canonical = docs / "HANDOFF_CHATGPT.md"
    if not canonical.exists():
        canonical = docs / "HANDOFF.md"

    canonical_text = ""
    if canonical.exists():
        canonical_text = canonical.read_text(encoding="utf-8", errors="replace").rstrip()

    out = []
    out.append("HANDOFF (recipient: ChatGPT)\n\n")
    out.append(f"Generated: {now}\n\n")
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
    out.append(f"- service_active: {active or 'unknown'}\n")
    out.append(f"- service_enabled: {enabled or 'unknown'}\n")
    out.append(f"- health_ok: {str(bool(health.get('ok'))).lower()}\n")
    if "mode" in health: out.append(f"- mode: {health.get('mode')}\n")
    if "version" in health: out.append(f"- version: {health.get('version')}\n")
    if health.get("ok") is False and "error" in health:
        out.append(f"- health_error: {health.get('error')}\n")
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

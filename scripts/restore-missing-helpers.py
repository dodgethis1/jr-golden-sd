from __future__ import annotations
import re, subprocess, sys
from pathlib import Path

TARGET = Path("app/app.py")

def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True)

def extract_block(text: str, name: str) -> str | None:
    # Find a TOP-LEVEL def (column 0). We want the real module-scope function.
    pat = re.compile(rf"^def {re.escape(name)}\s*\(", re.M)
    m = pat.search(text)
    if not m:
        return None
    start = m.start()
    lines = text[start:].splitlines(True)

    out = []
    out.append(lines[0])
    for line in lines[1:]:
        # stop when next top-level decorator/def/class begins
        if re.match(r"^(@|def|class)\b", line):
            break
        out.append(line)
    return "".join(out).rstrip() + "\n\n"

def find_in_history(names: list[str], max_commits: int = 60) -> tuple[str, dict[str, str]] | None:
    # Look back through commits that touched app/app.py
    revs = run(["git", "rev-list", f"-n{max_commits}", "HEAD", "--", str(TARGET)]).splitlines()
    for sha in revs:
        try:
            text = run(["git", "show", f"{sha}:{TARGET}"])
        except subprocess.CalledProcessError:
            continue
        got: dict[str, str] = {}
        ok = True
        for n in names:
            blk = extract_block(text, n)
            if not blk:
                ok = False
                break
            got[n] = blk
        if ok:
            return sha, got
    return None

def main():
    if not TARGET.exists():
        print(f"ERROR: missing {TARGET}", file=sys.stderr)
        return 2

    cur = TARGET.read_text(encoding="utf-8")
    need = ["detect_mode", "safety_state"]

    # If already present at top-level, don't duplicate.
    missing = []
    for n in need:
        if not re.search(rf"^def {re.escape(n)}\s*\(", cur, re.M):
            missing.append(n)

    if not missing:
        print("OK: helpers already present at module scope (nothing to do).")
        return 0

    found = find_in_history(missing)
    if not found:
        print(f"ERROR: could not find {missing} as top-level defs in last commits", file=sys.stderr)
        return 3

    sha, blocks = found
    print(f"OK: found {missing} in commit {sha}")

    # Insert before the /api/health route (so it's near where it's used).
    marker = re.search(r'^(?:@app\.(?:get|route)\(["\']/api/health|@app\.route\(["\']/api/health)', cur, re.M)
    if not marker:
        # fallback: insert before first /api/ occurrence
        marker = re.search(r'^@app\.(?:get|route)\(["\']/api/', cur, re.M)

    ins_at = marker.start() if marker else len(cur)

    insert = ""
    for n in missing:
        insert += blocks[n]

    new = cur[:ins_at] + "\n\n# === restored helper(s) from history ===\n" + insert + cur[ins_at:]

    # Backup
    bak = TARGET.with_suffix(".py.bak.restore")
    bak.write_text(cur, encoding="utf-8")
    TARGET.write_text(new, encoding="utf-8")
    print(f"OK: wrote {TARGET} (backup: {bak})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

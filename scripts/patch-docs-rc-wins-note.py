from pathlib import Path
from datetime import datetime
import re
import sys

marker = "<!-- DOC_RC_WINS_NOTE -->"
note = (
    f"{marker}\n"
    "### Job status resolution\n"
    "- The presence of `cache/jobs/<job_id>.rc` is **authoritative** for completion.\n"
    "  - `rc == 0` → `status = success`\n"
    "  - `rc != 0` → `status = failed`\n"
    "- If the `.rc` file is **absent**, the job may be considered `running` only if the recorded `pid` still exists (e.g., `/proc/<pid>` exists).\n"
    "\n"
)

def choose_target() -> Path:
    # Preferred: docs/JOB_SYSTEM.md (case-insensitive)
    docs = Path("docs")
    if docs.exists():
        for cand in [
            docs / "JOB_SYSTEM.md",
            docs / "job_system.md",
            docs / "Job_System.md",
        ]:
            if cand.exists():
                return cand

        # Otherwise: any markdown in docs that looks like the job system doc
        md_files = list(docs.rglob("*.md"))
        # prioritize ones containing "cache/jobs" or ".rc"
        scored = []
        for p in md_files:
            try:
                t = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            score = 0
            if "cache/jobs" in t: score += 5
            if re.search(r"\.rc\b", t): score += 3
            if "Job" in p.name or "job" in p.name: score += 1
            scored.append((score, p))
        scored.sort(key=lambda x: (-x[0], str(x[1])))
        if scored and scored[0][0] > 0:
            return scored[0][1]

    # Fallback: create docs/JOB_SYSTEM.md
    docs.mkdir(parents=True, exist_ok=True)
    return docs / "JOB_SYSTEM.md"

target = choose_target()

# Create minimal doc if it doesn't exist
if not target.exists():
    target.write_text(
        "# Job system\n\n"
        "This document describes the Golden SD Web UI job runner artifacts and status handling.\n\n",
        encoding="utf-8"
    )

text = target.read_text(encoding="utf-8", errors="ignore")
if marker in text:
    print(f"OK: note already present in {target}")
    sys.exit(0)

# Insert after first mention of ".rc" if present, otherwise append.
lines = text.splitlines(True)
insert_at = None
for i, l in enumerate(lines):
    if re.search(r"\.rc\b", l):
        insert_at = i + 1
        break
if insert_at is None:
    insert_at = len(lines)

new_text = "".join(lines[:insert_at]) + ("\n" if insert_at and not lines[insert_at-1].endswith("\n") else "") + note + "".join(lines[insert_at:])

bak = target.with_name(f"{target.name}.bak.{datetime.now().strftime('%Y%m%d-%H%M%S')}")
bak.write_text(text, encoding="utf-8")
target.write_text(new_text, encoding="utf-8")

print(f"OK: patched {target}")
print(f"OK: backup  {bak}")

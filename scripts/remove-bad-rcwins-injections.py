from pathlib import Path
import re
from datetime import datetime
import sys

APP = Path("app/app.py")
text = APP.read_text(encoding="utf-8")
lines = text.splitlines(True)

markers = [
    "JOB_STATUS_RC_WINS_V2",
    "JOB_STATUS_RC_WINS_V3",
]

def find_marker_idx(lines):
    for i, l in enumerate(lines):
        if any(m in l for m in markers):
            return i
    return None

def find_end_idx(lines, start):
    # remove from marker line through the next "return jsonify(resp)" line (inclusive)
    pat = re.compile(r"^\s*return\s+jsonify\s*\(\s*resp\s*\)\s*$")
    for j in range(start, len(lines)):
        if pat.match(lines[j]):
            return j
    return None

removed = 0
while True:
    i = find_marker_idx(lines)
    if i is None:
        break
    j = find_end_idx(lines, i)
    if j is None:
        print(f"ERROR: Found marker at line {i+1}, but could not find a following `return jsonify(resp)` to bound removal.")
        # show context to help debug without damaging file
        lo = max(0, i-15)
        hi = min(len(lines), i+60)
        for k in range(lo, hi):
            print(f"{k+1:6d}  {lines[k].rstrip()}")
        sys.exit(2)
    del lines[i:j+1]
    removed += 1

ts = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = APP.with_name(f"{APP.name}.bak.cleanup.{ts}")
backup.write_text(text, encoding="utf-8")
APP.write_text("".join(lines), encoding="utf-8")

print(f"OK: backup -> {backup}")
print(f"OK: removed {removed} injected block(s)")

from pathlib import Path
import re
import sys

path = Path("app/app.py")
text = path.read_text(encoding="utf-8")
lines = text.splitlines(True)

needle = re.compile(r'^(\s*)q = request\.args\.get\("q", ""\)\.strip\(\)\.lower\(\)\s*$')
already = re.compile(r'q\s+in\s+\("raspi",\s*"rpi"\)')

for i, line in enumerate(lines):
    m = needle.match(line.rstrip("\n"))
    if not m:
        continue
    indent = m.group(1)
    # avoid duplicate insert
    window = "".join(lines[i:i+6])
    if already.search(window):
        print("OK: alias already present; no change.")
        sys.exit(0)

    insert = (
        f'{indent}if q in ("raspi", "rpi"):\n'
        f'{indent}    q = "raspberry"\n'
    )
    lines.insert(i + 1, insert)
    path.write_text("".join(lines), encoding="utf-8")
    print("OK: inserted raspi/rpi alias after q= line.")
    sys.exit(0)

print("ERROR: could not find the q= request.args.get(...) line to patch.")
sys.exit(2)

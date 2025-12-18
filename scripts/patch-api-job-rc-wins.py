from pathlib import Path
import re
import sys
from datetime import datetime

APP = Path("app/app.py")
if not APP.exists():
    print(f"ERROR: missing {APP}")
    sys.exit(1)

text = APP.read_text(encoding="utf-8")
lines = text.splitlines(True)

deco = '@app.get("/api/job/<job_id>")'

# find decorator line
start = None
for i, l in enumerate(lines):
    if l.strip() == deco:
        start = i
        break
if start is None:
    print("ERROR: could not find /api/job/<job_id> decorator")
    sys.exit(2)

# find end of this function block (next top-level decorator)
end = None
for j in range(start + 1, len(lines)):
    if lines[j].startswith("@app."):
        end = j
        break
if end is None:
    end = len(lines)

block = lines[start:end]

marker = "JOB_STATUS_RC_WINS_API_JOB"
if any(marker in l for l in block):
    print("Patch already applied in api_job (marker found).")
    sys.exit(0)

# find insertion point: right after "job = job_refresh(job)"
ins = None
for k, l in enumerate(block):
    if re.match(r"^\s*job\s*=\s*job_refresh\s*\(\s*job\s*\)\s*$", l):
        ins = k + 1
        break
if ins is None:
    print("ERROR: could not find `job = job_refresh(job)` inside api_job block")
    sys.exit(3)

# detect indent (should be 4 spaces)
indent = re.match(r"^(\s*)", block[ins-1]).group(1)

insert = []
insert.append(f"{indent}# {marker}: rc file wins over stale 'running' state\n")
insert.append(f"{indent}try:\n")
insert.append(f"{indent}    from pathlib import Path\n")
insert.append(f"{indent}    rc_path = Path('cache/jobs') / f\"{{job_id}}.rc\"\n")
insert.append(f"{indent}    if rc_path.exists():\n")
insert.append(f"{indent}        rc_txt = rc_path.read_text(encoding='utf-8', errors='ignore').strip()\n")
insert.append(f"{indent}        try:\n")
insert.append(f"{indent}            rc_val = int(rc_txt)\n")
insert.append(f"{indent}        except Exception:\n")
insert.append(f"{indent}            rc_val = None\n")
insert.append(f"{indent}        job['exit_code'] = rc_val\n")
insert.append(f"{indent}        job['rc'] = rc_val\n")
insert.append(f"{indent}        job['status'] = 'success' if rc_val == 0 else 'failed'\n")
insert.append(f"{indent}        job['done'] = True\n")
insert.append(f"{indent}    else:\n")
insert.append(f"{indent}        pid = job.get('pid')\n")
insert.append(f"{indent}        if isinstance(pid, int) and Path(f\"/proc/{{pid}}\").exists():\n")
insert.append(f"{indent}            job['status'] = 'running'\n")
insert.append(f"{indent}        elif job.get('status') == 'running':\n")
insert.append(f"{indent}            job['status'] = 'stale'\n")
insert.append(f"{indent}except Exception as e:\n")
insert.append(f"{indent}    job.setdefault('status_note', f\"status_enrich_error: {{e}}\")\n")

new_block = block[:ins] + insert + block[ins:]
new_lines = lines[:start] + new_block + lines[end:]

ts = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = APP.with_name(f"{APP.name}.bak.{ts}")
backup.write_text(text, encoding="utf-8")

APP.write_text("".join(new_lines), encoding="utf-8")
print(f"OK: patched {APP}")
print(f"OK: backup  {backup}")

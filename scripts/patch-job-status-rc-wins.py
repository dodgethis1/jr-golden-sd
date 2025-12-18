from pathlib import Path
import re
import sys
from datetime import datetime

APP = Path("app/app.py")
if not APP.exists():
    print(f"ERROR: missing {APP}")
    sys.exit(1)

text = APP.read_text(encoding="utf-8")
if "Path(" in text and re.search(r"\bfrom\s+pathlib\s+import\s+Path\b", text) is None:
    print("ERROR: Path(...) is used but `from pathlib import Path` not found. Aborting to avoid breaking the file.")
    sys.exit(2)

marker = "JOB_STATUS_RC_WINS"
if marker in text:
    print("Patch already applied (marker found).")
    sys.exit(0)

lines = text.splitlines(True)

# Find the route decorator for /api/job/<job_id>
route_i = None
for i, l in enumerate(lines):
    if l.lstrip().startswith("@") and "/api/job/<" in l:
        route_i = i
        break
if route_i is None:
    print("ERROR: Could not find decorator for /api/job/<...> in app/app.py")
    sys.exit(3)

# Find the def line following the decorator
def_i = None
for j in range(route_i + 1, min(route_i + 40, len(lines))):
    if re.match(r"^\s*def\s+\w+\s*\(", lines[j]):
        def_i = j
        break
if def_i is None:
    print("ERROR: Could not find function definition after /api/job/<...> decorator")
    sys.exit(4)

base_indent = re.match(r"^(\s*)", lines[def_i]).group(1)

# Find end of function (first non-blank line with indent less than base_indent)
end = def_i + 1
while end < len(lines):
    l = lines[end]
    if l.strip() == "":
        end += 1
        continue
    ind = len(l) - len(l.lstrip())
    if ind < len(base_indent):
        break
    end += 1

block = lines[def_i:end]

# Find a return jsonify(...) in this function and capture the variable name inside
ret_k = None
var_expr = None
for k in range(len(block) - 1, -1, -1):
    if "return" in block[k] and "jsonify" in block[k]:
        m = re.search(r"\breturn\s+jsonify\s*\(\s*([^)]+?)\s*\)", block[k])
        if m:
            ret_k = k
            var_expr = m.group(1).strip()
            break

if ret_k is None or var_expr is None:
    print("ERROR: Could not find `return jsonify(...)` inside the /api/job/<...> handler.")
    sys.exit(5)

var = var_expr.split(",")[0].strip()
if not re.match(r"^[A-Za-z_]\w*$", var):
    print(f"ERROR: jsonify argument isn't a simple variable name: {var_expr!r}")
    sys.exit(6)

ret_indent = re.match(r"^(\s*)", block[ret_k]).group(1)

snippet = [
    f"{ret_indent}# {marker}: rc file wins over stale 'running' state\n",
    f"{ret_indent}try:\n",
    f"{ret_indent}    jobs_dir = Path('cache/jobs')\n",
    f"{ret_indent}    rc_path = jobs_dir / f\"{{job_id}}.rc\"\n",
    f"{ret_indent}    if rc_path.exists():\n",
    f"{ret_indent}        rc_txt = rc_path.read_text(encoding='utf-8', errors='ignore').strip()\n",
    f"{ret_indent}        try:\n",
    f"{ret_indent}            rc_val = int(rc_txt)\n",
    f"{ret_indent}        except Exception:\n",
    f"{ret_indent}            rc_val = None\n",
    f"{ret_indent}        if isinstance({var}, dict):\n",
    f"{ret_indent}            {var}['rc'] = rc_val\n",
    f"{ret_indent}            {var}['status'] = 'success' if rc_val == 0 else 'failed'\n",
    f"{ret_indent}            {var}['done'] = True\n",
    f"{ret_indent}    else:\n",
    f"{ret_indent}        pid = {var}.get('pid') if isinstance({var}, dict) else None\n",
    f"{ret_indent}        if isinstance(pid, int) and Path(f\"/proc/{{pid}}\").exists():\n",
    f"{ret_indent}            {var}['status'] = 'running'\n",
    f"{ret_indent}        elif isinstance({var}, dict) and {var}.get('status') == 'running':\n",
    f"{ret_indent}            {var}['status'] = 'stale'\n",
    f"{ret_indent}except Exception as _e:\n",
    f"{ret_indent}    # never break the API response because of status enrichment\n",
    f"{ret_indent}    if isinstance({var}, dict):\n",
    f"{ret_indent}        {var}.setdefault('status_note', f\"status_enrich_error: {{_e}}\")\n",
    "\n",
]

new_block = block[:ret_k] + snippet + block[ret_k:]
new_lines = lines[:def_i] + new_block + lines[end:]

ts = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = APP.with_name(f"{APP.name}.bak.{ts}")
backup.write_text(text, encoding="utf-8")

APP.write_text("".join(new_lines), encoding="utf-8")
print(f"OK: patched {APP}")
print(f"OK: backup  {backup}")

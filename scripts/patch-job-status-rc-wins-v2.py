from pathlib import Path
import re
import sys
from datetime import datetime

APP = Path("app/app.py")
if not APP.exists():
    print(f"ERROR: missing {APP}")
    sys.exit(1)

text = APP.read_text(encoding="utf-8")
marker = "JOB_STATUS_RC_WINS_V2"
if marker in text:
    print("Patch already applied (marker found).")
    sys.exit(0)

lines = text.splitlines(True)

# Find the route decorator for /api/job/<...>
route_i = None
for i, l in enumerate(lines):
    if l.lstrip().startswith("@") and "/api/job/<" in l:
        route_i = i
        break
if route_i is None:
    print("ERROR: Could not find decorator for /api/job/<...> in app/app.py")
    sys.exit(2)

# Find the def line following the decorator
def_i = None
for j in range(route_i + 1, min(route_i + 50, len(lines))):
    if re.match(r"^\s*def\s+\w+\s*\(", lines[j]):
        def_i = j
        break
if def_i is None:
    print("ERROR: Could not find function definition after /api/job/<...> decorator")
    sys.exit(3)

base_indent = re.match(r"^(\s*)", lines[def_i]).group(1)

# Find end of function block
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

# Find "return jsonify(" and capture the full call even if multi-line
ret_start = None
for k in range(len(block) - 1, -1, -1):
    if "return" in block[k] and "jsonify" in block[k] and "return" in block[k]:
        if "return jsonify" in block[k].replace(" ", "") or "returnjsonify" in block[k].replace(" ", ""):
            if "jsonify" in block[k] and "(" in block[k]:
                ret_start = k
                break

if ret_start is None:
    print("ERROR: Could not find a return jsonify(...) in the /api/job/<...> handler.")
    sys.exit(4)

# Build a contiguous string from ret_start onward until parens balance
call_text = ""
call_lines = []
paren = 0
started = False
ret_end = None

for idx in range(ret_start, len(block)):
    s = block[idx]
    call_lines.append(s)
    call_text += s

    # crude but effective: count parentheses from the first "jsonify("
    if not started:
        m = re.search(r"jsonify\s*\(", s)
        if m:
            started = True
            # count from the "(" we found to end of line
            tail = s[m.end()-1:]
            paren += tail.count("(") - tail.count(")")
    else:
        paren += s.count("(") - s.count(")")

    if started and paren <= 0:
        ret_end = idx
        break

if ret_end is None:
    print("ERROR: Could not balance parentheses for jsonify(...) call (unexpected formatting).")
    sys.exit(5)

first_line = block[ret_start]
ret_indent = re.match(r"^(\s*)", first_line).group(1)

# Extract the expression inside jsonify(...)
m0 = re.search(r"jsonify\s*\(", call_text)
if not m0:
    print("ERROR: Could not locate jsonify( in captured return.")
    sys.exit(6)

start_pos = m0.end()
# Find the matching closing paren for that opening
level = 1
pos = start_pos
while pos < len(call_text) and level > 0:
    ch = call_text[pos]
    if ch == "(":
        level += 1
    elif ch == ")":
        level -= 1
    pos += 1

if level != 0:
    print("ERROR: Failed to find closing ')' for jsonify(")
    sys.exit(7)

expr = call_text[start_pos:pos-1].strip()

# We only support dict literal or variable; if it's dict-literal-ish, rewrite to resp = <expr>
is_dictish = expr.lstrip().startswith("{") and expr.rstrip().endswith("}")
is_var = re.match(r"^[A-Za-z_]\w*$", expr) is not None

if not (is_dictish or is_var):
    print(f"ERROR: jsonify argument is not a dict literal or simple var. Got: {expr!r}")
    sys.exit(8)

# Replacement code
job_expr = "resp.get('job') if isinstance(resp, dict) else None"

replacement = []
replacement.append(f"{ret_indent}# {marker}: rc file wins over stale 'running' state\n")
replacement.append(f"{ret_indent}resp = {expr}\n")
replacement.append(f"{ret_indent}try:\n")
replacement.append(f"{ret_indent}    jobs_dir = Path('cache/jobs')\n")
replacement.append(f"{ret_indent}    rc_path = jobs_dir / f\"{{job_id}}.rc\"\n")
replacement.append(f"{ret_indent}    j = {job_expr}\n")
replacement.append(f"{ret_indent}    if rc_path.exists() and isinstance(j, dict):\n")
replacement.append(f"{ret_indent}        rc_txt = rc_path.read_text(encoding='utf-8', errors='ignore').strip()\n")
replacement.append(f"{ret_indent}        try:\n")
replacement.append(f"{ret_indent}            rc_val = int(rc_txt)\n")
replacement.append(f"{ret_indent}        except Exception:\n")
replacement.append(f"{ret_indent}            rc_val = None\n")
replacement.append(f"{ret_indent}        j['rc'] = rc_val\n")
replacement.append(f"{ret_indent}        j['status'] = 'success' if rc_val == 0 else 'failed'\n")
replacement.append(f"{ret_indent}        j['done'] = True\n")
replacement.append(f"{ret_indent}    elif isinstance(j, dict):\n")
replacement.append(f"{ret_indent}        pid = j.get('pid')\n")
replacement.append(f"{ret_indent}        if isinstance(pid, int) and Path(f\"/proc/{{pid}}\").exists():\n")
replacement.append(f"{ret_indent}            j['status'] = 'running'\n")
replacement.append(f"{ret_indent}        elif j.get('status') == 'running':\n")
replacement.append(f"{ret_indent}            j['status'] = 'stale'\n")
replacement.append(f"{ret_indent}except Exception as _e:\n")
replacement.append(f"{ret_indent}    if isinstance(resp, dict):\n")
replacement.append(f"{ret_indent}        resp.setdefault('status_note', f\"status_enrich_error: {{_e}}\")\n")
replacement.append(f"{ret_indent}return jsonify(resp)\n")

new_block = block[:ret_start] + replacement + block[ret_end+1:]
new_lines = lines[:def_i] + new_block + lines[end:]

ts = datetime.now().strftime("%Y%m%d-%H%M%S")
backup = APP.with_name(f"{APP.name}.bak.{ts}")
backup.write_text(text, encoding="utf-8")
APP.write_text("".join(new_lines), encoding="utf-8")

print(f"OK: patched {APP}")
print(f"OK: backup  {backup}")

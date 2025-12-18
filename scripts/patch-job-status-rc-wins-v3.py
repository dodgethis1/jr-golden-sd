from pathlib import Path
import re
import sys
from datetime import datetime

APP = Path("app/app.py")
if not APP.exists():
    print(f"ERROR: missing {APP}")
    sys.exit(1)

text = APP.read_text(encoding="utf-8")
marker = "JOB_STATUS_RC_WINS_V3"
if marker in text:
    print("Patch already applied (marker found).")
    sys.exit(0)

lines = text.splitlines(True)

def extract_paths_from_decorator(line: str):
    # returns list of string literals in decorator line
    return re.findall(r"['\"](/api/[^'\"]+)['\"]", line)

def is_base_job_route(path: str) -> bool:
    # want exactly /api/job/<something> with nothing after the closing >
    if not path.startswith("/api/job/<"):
        return False
    if ">" not in path:
        return False
    suffix = path.split(">", 1)[1]
    return "/" not in suffix  # excludes /tail, /cancel, etc.

route_i = None
route_path = None
for i, l in enumerate(lines):
    if not l.lstrip().startswith("@"):
        continue
    for p in extract_paths_from_decorator(l):
        if is_base_job_route(p):
            route_i = i
            route_path = p
            break
    if route_i is not None:
        break

if route_i is None:
    print("ERROR: Could not find base decorator for /api/job/<job_id> (no /tail).")
    # help debug
    hits = []
    for i, l in enumerate(lines):
        if "/api/job/<" in l:
            hits.append((i+1, l.rstrip()))
    print("Found these lines containing '/api/job/<':")
    for ln, s in hits[:30]:
        print(f"  L{ln}: {s}")
    sys.exit(2)

# find def after decorator
def_i = None
for j in range(route_i + 1, min(route_i + 60, len(lines))):
    if re.match(r"^\s*def\s+\w+\s*\(", lines[j]):
        def_i = j
        break
if def_i is None:
    print("ERROR: Could not find function definition after base /api/job/<...> decorator")
    sys.exit(3)

base_indent = re.match(r"^(\s*)", lines[def_i]).group(1)

# parse first param name from def signature
m_sig = re.search(r"^\s*def\s+\w+\s*\(\s*([^)]+)\s*\)\s*:", lines[def_i])
if not m_sig:
    print("ERROR: Could not parse function signature line:", lines[def_i].rstrip())
    sys.exit(4)

params = [p.strip() for p in m_sig.group(1).split(",") if p.strip()]
if not params:
    print("ERROR: No params found in handler signature (expected job id param).")
    sys.exit(5)

first = params[0]
# strip type hints and defaults
first = first.split(":", 1)[0].split("=", 1)[0].strip()
if not re.match(r"^[A-Za-z_]\w*$", first):
    print(f"ERROR: Could not extract a safe param name from signature: {params[0]!r}")
    sys.exit(6)

jobid_var = first

# find end of function block
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

# locate last return jsonify(...) and capture multi-line call
ret_start = None
for k in range(len(block) - 1, -1, -1):
    if "return" in block[k] and "jsonify" in block[k]:
        ret_start = k
        break
if ret_start is None:
    print("ERROR: Could not find return jsonify(...) in base /api/job/<...> handler.")
    sys.exit(7)

call_text = ""
paren = 0
started = False
ret_end = None
for idx in range(ret_start, len(block)):
    s = block[idx]
    call_text += s
    if not started:
        m = re.search(r"jsonify\s*\(", s)
        if m:
            started = True
            tail = s[m.end()-1:]
            paren += tail.count("(") - tail.count(")")
    else:
        paren += s.count("(") - s.count(")")
    if started and paren <= 0:
        ret_end = idx
        break

if ret_end is None:
    print("ERROR: Could not capture full jsonify(...) call (paren mismatch).")
    sys.exit(8)

first_line = block[ret_start]
ret_indent = re.match(r"^(\s*)", first_line).group(1)

m0 = re.search(r"jsonify\s*\(", call_text)
if not m0:
    print("ERROR: jsonify( not found in captured return.")
    sys.exit(9)

start_pos = m0.end()
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
    sys.exit(10)

expr = call_text[start_pos:pos-1].strip()

# rewrite return jsonify(EXPR) into:
#   resp = EXPR
#   ... rc-wins enrichment ...
#   return jsonify(resp)
replacement = []
replacement.append(f"{ret_indent}# {marker}: rc file wins over stale 'running' state (base job endpoint {route_path})\n")
replacement.append(f"{ret_indent}resp = {expr}\n")
replacement.append(f"{ret_indent}try:\n")
replacement.append(f"{ret_indent}    jobs_dir = Path('cache/jobs')\n")
replacement.append(f"{ret_indent}    rc_path = jobs_dir / f\"{{{jobid_var}}}.rc\"\n")
replacement.append(f"{ret_indent}    j = None\n")
replacement.append(f"{ret_indent}    if isinstance(resp, dict) and isinstance(resp.get('job'), dict):\n")
replacement.append(f"{ret_indent}        j = resp['job']\n")
replacement.append(f"{ret_indent}    elif isinstance(resp, dict) and ('id' in resp) and ('status' in resp):\n")
replacement.append(f"{ret_indent}        j = resp\n")
replacement.append(f"{ret_indent}    if rc_path.exists() and isinstance(j, dict):\n")
replacement.append(f"{ret_indent}        rc_txt = rc_path.read_text(encoding='utf-8', errors='ignore').strip()\n")
replacement.append(f"{ret_indent}        try:\n")
replacement.append(f"{ret_indent}            rc_val = int(rc_txt)\n")
replacement.append(f"{ret_indent}        except Exception:\n")
replacement.append(f"{ret_indent}            rc_val = None\n")
replacement.append(f"{ret_indent}        # normalize naming: API has used exit_code historically\n")
replacement.append(f"{ret_indent}        j['exit_code'] = rc_val\n")
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
print(f"OK: targeted base route {route_path} with param '{jobid_var}'")

from pathlib import Path
import re
import sys
from datetime import datetime

APP = Path("app/app.py")
if not APP.exists():
    print("ERROR: app/app.py not found")
    sys.exit(1)

orig = APP.read_text(encoding="utf-8")
lines = orig.splitlines(True)

def backup():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    b = APP.with_name(f"{APP.name}.bak.harden.{ts}")
    b.write_text(orig, encoding="utf-8")
    return b

def find_def_block(name: str):
    pat = re.compile(rf"^def\s+{re.escape(name)}\s*\(")
    s = None
    for i,l in enumerate(lines):
        if pat.match(l):
            s = i
            break
    if s is None:
        return None, None
    e = None
    for j in range(s+1, len(lines)):
        if lines[j].startswith("@app.") or re.match(r"^def\s+\w+\s*\(", lines[j]):
            e = j
            break
    if e is None:
        e = len(lines)
    return s, e

def find_route_block(route: str):
    deco = f'@app.get("{route}")'
    s = None
    for i,l in enumerate(lines):
        if l.strip() == deco:
            s = i
            break
    if s is None:
        return None, None
    e = None
    for j in range(s+1, len(lines)):
        if lines[j].startswith("@app."):
            e = j
            break
    if e is None:
        e = len(lines)
    return s, e

changed = False

# 1) Inject rc-wins into job_refresh (single source of truth)
marker_refresh = "JOB_STATUS_RC_WINS_JOB_REFRESH"
jr_s, jr_e = find_def_block("job_refresh")
if jr_s is None:
    print("ERROR: def job_refresh(...) not found")
    sys.exit(2)

refresh_block = lines[jr_s:jr_e]
if not any(marker_refresh in l for l in refresh_block):
    ret_i = None
    for i,l in enumerate(refresh_block):
        if re.match(r"^\s{4}return\s+job\s*$", l):
            ret_i = i
            break
    if ret_i is None:
        print("ERROR: could not find `return job` inside job_refresh")
        sys.exit(3)

    indent = " " * 4
    insert = [
        f"{indent}# {marker_refresh}: rc file wins when present\n",
        f"{indent}try:\n",
        f"{indent}    import re\n",
        f"{indent}    from pathlib import Path\n",
        f"{indent}    if isinstance(job, dict):\n",
        f"{indent}        _jid = job.get('id') or job.get('job_id')\n",
        f"{indent}        _jid = str(_jid) if _jid is not None else ''\n",
        f"{indent}        if _jid and re.fullmatch(r\"[A-Za-z0-9_-]+\", _jid):\n",
        f"{indent}            rc_path = Path('cache/jobs') / (_jid + '.rc')\n",
        f"{indent}            if rc_path.exists():\n",
        f"{indent}                rc_txt = rc_path.read_text(encoding='utf-8', errors='ignore').strip()\n",
        f"{indent}                try:\n",
        f"{indent}                    rc_val = int(rc_txt)\n",
        f"{indent}                except Exception:\n",
        f"{indent}                    rc_val = None\n",
        f"{indent}                job['exit_code'] = rc_val\n",
        f"{indent}                job['rc'] = rc_val\n",
        f"{indent}                job['status'] = 'success' if rc_val == 0 else 'failed'\n",
        f"{indent}                job['done'] = True\n",
        f"{indent}            else:\n",
        f"{indent}                if job.get('status') == 'running':\n",
        f"{indent}                    pid = job.get('pid')\n",
        f"{indent}                    if isinstance(pid, int) and (Path('/proc') / str(pid)).exists():\n",
        f"{indent}                        job['status'] = 'running'\n",
        f"{indent}                    else:\n",
        f"{indent}                        job['status'] = 'stale'\n",
        f"{indent}except Exception as e:\n",
        f"{indent}    if isinstance(job, dict):\n",
        f"{indent}        job.setdefault('status_note', 'status_enrich_error: ' + str(e))\n",
    ]

    refresh_block = refresh_block[:ret_i] + insert + refresh_block[ret_i:]
    lines[jr_s:jr_e] = refresh_block
    changed = True
    print("OK: injected rc-wins into job_refresh")

# 2) Add job_id validation to /api/job/<job_id>
marker_validate = "JOB_ID_VALIDATE_API_JOB"
route_s, route_e = find_route_block("/api/job/<job_id>")
if route_s is None:
    print("ERROR: route /api/job/<job_id> not found")
    sys.exit(4)

route_block = lines[route_s:route_e]
if not any(marker_validate in l for l in route_block):
    def_i = None
    for i,l in enumerate(route_block):
        if re.match(r"^\s*def\s+api_job\s*\(", l):
            def_i = i
            break
    if def_i is None:
        print("ERROR: def api_job(...) not found in route block")
        sys.exit(5)

    indent = " " * 4
    insert = [
        f"{indent}# {marker_validate}: job_id is used to form filenames; keep it boring\n",
        f"{indent}import re\n",
        f"{indent}if not re.fullmatch(r\"[A-Za-z0-9_-]+\", job_id or \"\"):\n",
        f"{indent}    return jsonify({{\"ok\": False, \"error\": \"invalid job_id\"}}), 400\n",
    ]
    route_block = route_block[:def_i+1] + insert + route_block[def_i+1:]
    lines[route_s:route_e] = route_block
    changed = True
    print("OK: added job_id validation to api_job")

# 3) Remove old per-route rc-wins block from api_job (now redundant) IF refresh marker exists
marker_old = "JOB_STATUS_RC_WINS_API_JOB"
route_block = lines[route_s:route_e]
has_refresh = (marker_refresh in "".join(lines[jr_s:jr_e]))
if has_refresh and any(marker_old in l for l in route_block):
    start_i = None
    for i,l in enumerate(route_block):
        if marker_old in l:
            start_i = i
            break
    end_i = None
    for j in range(start_i+1, len(route_block)):
        if "Don't spam huge logs" in route_block[j] or re.match(r"^\s*return\s+jsonify", route_block[j]):
            end_i = j
            break
    if start_i is not None and end_i is not None and end_i > start_i:
        del route_block[start_i:end_i]
        lines[route_s:route_e] = route_block
        changed = True
        print("OK: removed old per-route rc-wins block from api_job")

if not changed:
    print("OK: no changes needed (already hardened)")
    sys.exit(0)

bak = backup()
APP.write_text("".join(lines), encoding="utf-8")
print(f"OK: wrote {APP}")
print(f"OK: backup {bak}")

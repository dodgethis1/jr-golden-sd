from pathlib import Path
import re

def patch_app_py():
    p = Path("app/app.py")
    s = p.read_text(encoding="utf-8")

    changed = False

    # Ensure version_info() exists (small + self-contained)
    if re.search(r'(?m)^\s*def\s+version_info\s*\(\)\s*:\s*$', s) is None:
        helper = r'''
def version_info():
    """
    Versioning policy:
      - SemVer tags: vMAJOR.MINOR.PATCH
      - Build identity: git describe --tags --dirty --always
    """
    import os, re, subprocess

    def _git(args):
        try:
            r = subprocess.run(["git", "-C", BASE_DIR, *args], capture_output=True, text=True)
            if r.returncode != 0:
                return None
            out = (r.stdout or "").strip()
            return out or None
        except Exception:
            return None

    describe = _git(["describe", "--tags", "--dirty", "--always"])
    commit = _git(["rev-parse", "--short=12", "HEAD"])
    st = (_git(["status", "--porcelain"]) or "")
    dirty = bool(st.strip())

    semver = None
    if describe:
        m = re.match(r"^(v\d+\.\d+\.\d+)", describe)
        if m:
            semver = m.group(1)

    version = os.environ.get("JR_GOLDEN_SD_VERSION") or describe or commit or "unknown"
    source = "env" if os.environ.get("JR_GOLDEN_SD_VERSION") else "git"
    return {"version": version, "describe": describe, "commit": commit, "dirty": dirty, "semver": semver, "source": source}
'''
        # Insert after BASE_DIR if present, else after app = Flask
        m = re.search(r'(?m)^BASE_DIR\s*=.*$', s)
        if m:
            ins = m.end()
            s = s[:ins] + "\n" + helper + s[ins:]
        else:
            m2 = re.search(r'(?m)^app\s*=\s*Flask\(.*$', s)
            ins = m2.end() if m2 else 0
            s = s[:ins] + "\n" + helper + s[ins:]
        changed = True

    # Patch the /api/health function by locating decorator, then replacing its return jsonify(...) line
    lines = s.splitlines(True)
    dec_i = None
    for i, ln in enumerate(lines):
        if re.search(r'^\s*@app\.(get|route)\(\s*[\'"]/api/health[\'"]', ln):
            dec_i = i
            break
    if dec_i is None:
        raise SystemExit("ERROR: could not find /api/health decorator in app/app.py")

    # Find function end = next top-level @app.*
    end_i = len(lines)
    for j in range(dec_i + 1, len(lines)):
        if re.match(r'^@app\.', lines[j]):
            end_i = j
            break

    block = lines[dec_i:end_i]

    # Ensure vi = version_info() exists in the block
    if not any("vi = version_info()" in ln for ln in block):
        # insert after def line
        for k, ln in enumerate(block):
            if re.match(r'^\s*def\s+\w+\s*\(.*\)\s*:\s*$', ln):
                indent = re.match(r'^(\s*)', block[k+1]).group(1) if k+1 < len(block) else "    "
                block.insert(k+1, f"{indent}vi = version_info()\n")
                changed = True
                break

    # Replace first 'return jsonify(...' inside that block
    ret_k = None
    for k, ln in enumerate(block):
        if "return jsonify(" in ln:
            ret_k = k
            break
    if ret_k is None:
        raise SystemExit("ERROR: found /api/health but no return jsonify(...) inside handler")

    indent = re.match(r'^(\s*)', block[ret_k]).group(1)
    new_return = (
        f'{indent}return jsonify({{\n'
        f'{indent}  "ok": True,\n'
        f'{indent}  "version": vi.get("version"),\n'
        f'{indent}  "semver": vi.get("semver"),\n'
        f'{indent}  "git_describe": vi.get("describe"),\n'
        f'{indent}  "git_commit": vi.get("commit"),\n'
        f'{indent}  "git_dirty": vi.get("dirty"),\n'
        f'{indent}  "version_source": vi.get("source"),\n'
        f'{indent}  **m\n'
        f'{indent}}})\n'
    )

    block[ret_k] = new_return
    changed = True

    s2 = "".join(lines[:dec_i]) + "".join(block) + "".join(lines[end_i:])
    if s2 != s:
        p.write_text(s2, encoding="utf-8")
        print("OK: patched app/app.py (/api/health now returns version fields)")
    else:
        print("NOTE: app/app.py unchanged (already patched?)")

def patch_static():
    p = Path("static/index.html")
    s = p.read_text(encoding="utf-8")

    before = s
    # Fix: + /tail?lines=200"  -> + "/tail?lines=200"
    s = re.sub(r'\+\s*/tail\?lines=200"', '+ "/tail?lines=200"', s)

    if s != before:
        p.write_text(s, encoding="utf-8")
        print("OK: patched static/index.html (fixed /tail string concat)")
    else:
        print("NOTE: static/index.html unchanged (pattern not found or already fixed)")

patch_app_py()
patch_static()

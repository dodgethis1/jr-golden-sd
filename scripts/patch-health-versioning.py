from pathlib import Path
import re
import sys

path = Path("app/app.py")
text = path.read_text(encoding="utf-8")
lines = text.splitlines(True)  # keep newlines

def find_health_decorator(lines):
    dec = re.compile(r'^\s*@app\.(get|route)\(\s*[\'"]/api/health[\'"]', re.M)
    for i, ln in enumerate(lines):
        if dec.search(ln):
            return i
    return None

def find_def_after(lines, start_i):
    # allows: def api_health():  OR def api_health() -> Something:
    d = re.compile(r'^\s*def\s+\w+\s*\(.*\)\s*(?:->\s*[^:]+)?\s*:\s*$', re.M)
    for i in range(start_i + 1, len(lines)):
        if d.match(lines[i]):
            return i
    return None

def find_block_end(lines, def_i):
    # end at next top-level decorator
    for i in range(def_i + 1, len(lines)):
        if re.match(r'^\s*@app\.', lines[i]) and (len(lines[i]) - len(lines[i].lstrip())) == 0:
            return i
    return len(lines)

def ensure_version_info(lines):
    if any(re.match(r'^\s*def\s+version_info\s*\(\)\s*:\s*$', ln) for ln in lines):
        return lines, False

    helper = (
        '\n'
        'def version_info():\n'
        '    """\n'
        '    Versioning policy:\n'
        '      - SemVer tags: vMAJOR.MINOR.PATCH\n'
        '      - Build identity: git describe --tags --dirty --always\n'
        '    """\n'
        '    import os, re, subprocess\n'
        '\n'
        '    def _git(args):\n'
        '        try:\n'
        '            r = subprocess.run(["git", "-C", BASE_DIR, *args], capture_output=True, text=True)\n'
        '            if r.returncode != 0:\n'
        '                return None\n'
        '            return (r.stdout or "").strip() or None\n'
        '        except Exception:\n'
        '            return None\n'
        '\n'
        '    describe = _git(["describe", "--tags", "--dirty", "--always"])\n'
        '    commit = _git(["rev-parse", "--short=12", "HEAD"])\n'
        '    st = _git(["status", "--porcelain"]) or ""\n'
        '    dirty = bool(st.strip())\n'
        '\n'
        '    semver = None\n'
        '    if describe:\n'
        '        m = re.match(r"^(v\\d+\\.\\d+\\.\\d+)", describe)\n'
        '        if m:\n'
        '            semver = m.group(1)\n'
        '\n'
        '    version = os.environ.get("JR_GOLDEN_SD_VERSION") or describe or commit or "unknown"\n'
        '    source = "env" if os.environ.get("JR_GOLDEN_SD_VERSION") else "git"\n'
        '    return {\n'
        '        "version": version,\n'
        '        "describe": describe,\n'
        '        "commit": commit,\n'
        '        "dirty": dirty,\n'
        '        "semver": semver,\n'
        '        "source": source,\n'
        '    }\n'
    )

    # insert after BASE_DIR assignment if possible, else near top after app=Flask
    base_i = None
    for i, ln in enumerate(lines):
        if re.match(r'^\s*BASE_DIR\s*=\s*', ln):
            base_i = i
            break

    if base_i is not None:
        insert_at = base_i + 1
    else:
        app_i = None
        for i, ln in enumerate(lines):
            if "app = Flask(" in ln:
                app_i = i
                break
        insert_at = (app_i + 1) if app_i is not None else 0

    out = lines[:insert_at] + [helper] + lines[insert_at:]
    return out, True

def ensure_vi_in_function(block_lines):
    if any("version_info()" in ln for ln in block_lines):
        return block_lines, False

    # find insert point after optional docstring
    def_line = block_lines[0]
    indent = re.match(r'^(\s*)', block_lines[1]).group(1) if len(block_lines) > 1 else "    "

    i = 1
    # skip blank lines
    while i < len(block_lines) and block_lines[i].strip() == "":
        i += 1

    # docstring?
    if i < len(block_lines) and block_lines[i].lstrip().startswith(('"""', "'''")):
        quote = block_lines[i].lstrip()[:3]
        i += 1
        while i < len(block_lines):
            if quote in block_lines[i]:
                i += 1
                break
            i += 1

    insert = f"{indent}vi = version_info()\n"
    out = block_lines[:i] + [insert] + block_lines[i:]
    return out, True

def replace_version_key(block_lines):
    # Replace first dict key "version": ... or 'version': ...
    key_re = re.compile(r'^(\s*)(["\'])version\2\s*:\s*.*')
    for i, ln in enumerate(block_lines):
        m = key_re.match(ln)
        if m:
            ind = m.group(1)
            repl = [
                f'{ind}"version": vi.get("version"),\n',
                f'{ind}"semver": vi.get("semver"),\n',
                f'{ind}"git_describe": vi.get("describe"),\n',
                f'{ind}"git_commit": vi.get("commit"),\n',
                f'{ind}"git_dirty": vi.get("dirty"),\n',
                f'{ind}"version_source": vi.get("source"),\n',
            ]
            out = block_lines[:i] + repl + block_lines[i+1:]
            return out, True
    return block_lines, False

# --- main patch flow ---
dec_i = find_health_decorator(lines)
if dec_i is None:
    print("ERROR: could not find @app.get/@app.route for /api/health")
    hits = [ (i+1, ln.rstrip()) for i, ln in enumerate(lines) if "/api/health" in ln ]
    print("Found /api/health mentions:", hits[:10])
    sys.exit(2)

def_i = find_def_after(lines, dec_i)
if def_i is None:
    print("ERROR: found /api/health decorator but no def after it")
    sys.exit(3)

end_i = find_block_end(lines, def_i)

lines, added_helper = ensure_version_info(lines)

# recompute indexes if helper insertion happened before health block
if added_helper:
    dec_i = find_health_decorator(lines)
    def_i = find_def_after(lines, dec_i)
    end_i = find_block_end(lines, def_i)

block = lines[def_i:end_i]

block, added_vi = ensure_vi_in_function(block)
block, replaced = replace_version_key(block)

if not replaced:
    print("ERROR: couldn't find a 'version' key inside /api/health response to replace.")
    print("Dumping /api/health block header for inspection:")
    for ln in block[:60]:
        print(ln.rstrip())
    sys.exit(4)

out = lines[:def_i] + block + lines[end_i:]
path.write_text("".join(out), encoding="utf-8")

print("OK: patched app/app.py")
print(f" - added version_info(): {added_helper}")
print(f" - inserted vi=version_info(): {added_vi}")
print(f" - replaced version key: {replaced}")

from pathlib import Path
import sys
import re

APP = Path("app/app.py")
DOC = Path("docs/OS_CATALOG.md")

def die(msg: str):
    print("ERROR:", msg, file=sys.stderr)
    raise SystemExit(1)

if not APP.exists():
    die(f"Missing {APP}")

txt = APP.read_text(encoding="utf-8")

# -----------------------------
# Patch 1: /api/os search improvement + aliases
# -----------------------------
marker_search = "# JR_SEARCH_V2"
needle_line = 'catalog = [x for x in catalog if (q in x["name"].lower() or q in (x["description"] or "").lower())]'

if marker_search in txt:
    print("OK: search patch already present")
else:
    if needle_line not in txt:
        die("Could not find the original /api/os filter line to replace. File changed unexpectedly.")
    replacement = f"""{marker_search}
        # More forgiving search: tokenize + match across multiple fields.
        # Also handle common aliases people actually type.
        aliases = {{
            "raspi": "raspberry",
            "rpi": "raspberry",
        }}
        q2 = aliases.get(q, q)
        terms = [t for t in re.split(r"\\s+", q2) if t]

        def _hay(it):
            return " ".join([
                str(it.get("name") or ""),
                str(it.get("description") or ""),
                str(it.get("provider_label") or ""),
                " ".join(it.get("devices") or []),
                str(it.get("id") or ""),
            ]).lower()

        def _match(it):
            h = _hay(it)
            return all(t in h for t in terms)

        catalog = [x for x in catalog if _match(x)]
"""
    txt = txt.replace(needle_line, replacement)
    print("OK: applied /api/os search patch")

# -----------------------------
# Patch 2: job_refresh() should trust rc file over pid (pid reuse / stale pid)
# -----------------------------
marker_job = "# JR_JOB_RC_OVERRIDE"

if marker_job in txt:
    print("OK: job rc override patch already present")
else:
    m = re.search(r'^(def\s+job_refresh\s*\(.*\)\s*:\s*)$', txt, flags=re.M)
    if not m:
        die("Could not find def job_refresh(...): to patch.")
    insert_at = m.end(0)
    inject = f"""
    {marker_job}
    # If the rc file exists, the job is finished. This also avoids PID-reuse lies.
    try:
        rc_path = (job or {{}}).get("rc_path")
    except Exception:
        rc_path = None

    if rc_path and os.path.exists(rc_path):
        try:
            rc_txt = Path(rc_path).read_text(encoding="utf-8", errors="replace").strip()
            rc = int(rc_txt or "1")
        except Exception:
            rc = 1

        job["rc"] = rc
        job["pid_alive"] = False
        job["status"] = "success" if rc == 0 else "failed"
        job["updated_at"] = time.time()
        job["pid"] = None
"""
    txt = txt[:insert_at] + inject + txt[insert_at:]
    print("OK: applied job rc override patch")

APP.write_text(txt, encoding="utf-8")
print("WROTE:", APP)

# -----------------------------
# Patch 3: docs/OS_CATALOG.md (was TODO)
# -----------------------------
doc_body = """# OS_CATALOG

This project builds an OS catalog at request time from provider JSON files.

## Providers
- Directory: `data/os-providers/`
- Files: `*.json`
- Each provider may be `"enabled": true/false`

Current default provider:
- `01-rpi-imager.json` → Raspberry Pi Imager (official) v4 list:
  - `https://downloads.raspberrypi.com/os_list_imagingutility_v4.json`

## How the catalog is built
On `GET /api/os`:
1. Read enabled provider files.
2. For each `type: "imager_v4"` provider:
   - Fetch the provider URL into `cache/<provider_id>.json` (TTL ~6 hours).
   - If the network fetch fails, the server falls back to the cached file.
3. Flatten the `os_list` tree by walking `subitems` and collecting nodes that contain a `url`.
4. Normalize each entry into a single list of items with fields like:
   - `id`, `name`, `description`, `url`, `image_download_size`, `sha256`, `devices`, etc.

## Item IDs
IDs are generated to be stable-ish across runs:
- Format: `<provider_id>:<slug(name)>:<sha1(url|name)[:10]>`
Example:
- `rpi-imager-official:sd-card-boot:33a103a571`

## Search behavior
`GET /api/os?q=...` matches case-insensitively across:
- name, description, provider label, devices, and id

Common aliases are supported:
- `raspi` → `raspberry`
- `rpi` → `raspberry`

Tip: if you want “everything”, omit `q` entirely.
"""

if DOC.exists() and "(TODO)" not in DOC.read_text(encoding="utf-8", errors="replace"):
    print("OK: OS_CATALOG.md already filled (leaving as-is)")
else:
    DOC.write_text(doc_body, encoding="utf-8")
    print("WROTE:", DOC)

import json, os, subprocess, re, io, time, hashlib, secrets
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError
from flask import Flask, jsonify, send_from_directory, Response, request

APP_PORT = int(os.environ.get("JR_GOLDEN_SD_PORT", "8025"))
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

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

CACHE_DIR = os.path.join(BASE_DIR, "cache")

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"))

# ---------------- core helpers ----------------

def sh(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()

def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)

def load_policy() -> dict:
    # One-word, ALL-CAPS safety token for destructive writes
    default_word = os.environ.get("JR_WRITE_WORD", "ERASE").strip().upper() or "ERASE"
    default_word = re.split(r"\s+", default_word)[0] if default_word else "ERASE"
    pol = {"write_word": default_word, "arm_ttl_seconds": 600}
    try:
        path = os.path.join(BASE_DIR, "data", "policy.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            w = str(obj.get("write_word", default_word)).strip().upper() or default_word
            w = re.split(r"\s+", w)[0] if w else default_word
            pol["write_word"] = w
            if "arm_ttl_seconds" in obj:
                pol["arm_ttl_seconds"] = int(obj["arm_ttl_seconds"])
    except Exception:
        pass
    return pol

def get_version() -> str:
    try:
        return sh(["git", "describe", "--tags", "--always", "--dirty"])
    except Exception:
        return "0.0.0-dev"

def root_source() -> str:
    try:
        return sh(["findmnt", "-no", "SOURCE", "/"])
    except Exception:
        return ""

def parent_disk(devpath: str) -> str:
    dev = devpath.replace("/dev/", "")
    if not dev:
        return ""
    try:
        pk = sh(["lsblk", "-no", "PKNAME", f"/dev/{dev}"])
        return pk.strip()
    except Exception:
        return dev.rstrip("0123456789").rstrip("p")

def detect_mode() -> dict:
    rs = root_source()
    parent = parent_disk(rs)
    mode = "unknown"
    if parent.startswith("mmcblk"):
        mode = "SD"
    elif parent.startswith("nvme"):
        mode = "NVMe"
    else:
        try:
            tran = sh(["lsblk", "-no", "TRAN", f"/dev/{parent}"]).strip().lower()
            if tran == "usb":
                mode = "USB"
        except Exception:
            pass
    return {"root_source": rs, "root_parent": parent, "mode": mode}

def list_urls(port: int) -> list[str]:
    urls = []
    try:
        out = sh(["ip", "-br", "a"])
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            if parts[1] != "UP":
                continue
            for p in parts[2:]:
                if re.match(r"^\d+\.\d+\.\d+\.\d+/\d+$", p):
                    ip4 = p.split("/")[0]
                    if ip4.startswith("127."):
                        continue
                    urls.append(f"http://{ip4}:{port}/")
    except Exception:
        pass

    # no promises, but harmless
    host = os.environ.get("HOSTNAME", "").strip()
    if host:
        urls.append(f"http://{host}.local:{port}/")

    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def cache_get(url: str, cache_name: str, ttl_seconds: int = 6*3600) -> bytes:
    ensure_cache_dir()
    cpath = os.path.join(CACHE_DIR, cache_name)
    now = time.time()

    if os.path.exists(cpath):
        age = now - os.path.getmtime(cpath)
        if age < ttl_seconds:
            with open(cpath, "rb") as f:
                return f.read()

    req = Request(url, headers={"User-Agent": "jr-golden-sd/0.1"})
    try:
        with urlopen(req, timeout=20) as r:
            data = r.read()
        with open(cpath, "wb") as f:
            f.write(data)
        return data
    except URLError:
        if os.path.exists(cpath):
            with open(cpath, "rb") as f:
                return f.read()
        raise

def slug_id(provider_id: str, url: str, name: str) -> str:
    h = hashlib.sha1((url + "|" + name).encode("utf-8")).hexdigest()[:10]
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    return f"{provider_id}:{base}:{h}"

def flatten_imager_os(obj) -> list[dict]:
    out = []
    def walk(node):
        if isinstance(node, dict):
            if "url" in node and isinstance(node.get("url"), str):
                out.append(node)
            elif "subitems" in node and isinstance(node.get("subitems"), list):
                for s in node["subitems"]:
                    walk(s)
        elif isinstance(node, list):
            for x in node:
                walk(x)
    walk(obj.get("os_list", []))
    return out

def read_provider_files() -> list[dict]:
    pdir = os.path.join(BASE_DIR, "data", "os-providers")
    providers = []
    if not os.path.isdir(pdir):
        return providers
    for fn in sorted(os.listdir(pdir)):
        if fn.endswith(".json"):
            path = os.path.join(pdir, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    obj = json.load(f)
                if obj.get("enabled", True):
                    providers.append(obj)
            except Exception:
                continue
    return providers

def load_os_catalog() -> list[dict]:
    providers = read_provider_files()
    all_items = []
    for p in providers:
        if p.get("type") == "imager_v4":
            data = cache_get(p["url"], f"{p['id']}.json", ttl_seconds=6*3600)
            repo = json.loads(data.decode("utf-8", errors="replace"))
            items = flatten_imager_os(repo)
            for it in items:
                name = it.get("name", "unknown")
                os_id = slug_id(p["id"], it.get("url", ""), name)
                all_items.append({
                    "id": os_id,
                    "provider_id": p["id"],
                    "provider_label": p.get("label", p["id"]),
                    "name": name,
                    "description": it.get("description", ""),
                    "url": it.get("url"),
                    "image_download_size": it.get("image_download_size"),
                    "image_download_sha256": it.get("image_download_sha256"),
                    "extract_size": it.get("extract_size"),
                    "extract_sha256": it.get("extract_sha256"),
                    "release_date": it.get("release_date"),
                    "devices": it.get("devices", []),
                    "init_format": it.get("init_format"),
                })
    all_items.sort(key=lambda x: (x["provider_id"], x["name"]))
    return all_items

def find_os(os_id: str, catalog: list[dict]) -> dict | None:
    for it in catalog:
        if it["id"] == os_id:
            return it
    return None

def guess_decompress_cmd(url: str) -> str:
    u = (url or "").lower()
    if u.endswith(".img.xz") or u.endswith(".xz"):
        return "xz -dc"
    if u.endswith(".zip"):
        return "unzip -p"
    return "(unknown extractor)"

# ---------------- disk safety ----------------

def safety_state() -> dict:
    cols = "NAME,KNAME,PATH,MODEL,SERIAL,SIZE,TYPE,TRAN,MOUNTPOINT,FSTYPE,ROTA,RM"
    raw = sh(["lsblk", "-J", "-o", cols])
    obj = json.loads(raw)

    m = detect_mode()
    root_parent = m["root_parent"]

    disks = []
    for d in obj.get("blockdevices", []):
        if d.get("type") != "disk":
            continue

        # Safety: ignore zram/loop/ram and anything without a transport
        name = (d.get("name") or "")
        tran = d.get("tran")
        if tran is None:
            continue
        if name.startswith(("zram", "loop", "ram")):
            continue

        disks.append({
            "name": d.get("name"),
            "path": d.get("path"),
            "tran": d.get("tran"),
            "size": d.get("size"),
            "model": d.get("model"),
            "serial": d.get("serial"),
            "rm": d.get("rm"),
            "rota": d.get("rota"),
            "is_root_disk": (d.get("name") == root_parent),
        })

    eligible = [x for x in disks if not x["is_root_disk"]]
    return {
        "mode": m["mode"],
        "root_source": m["root_source"],
        "root_parent": root_parent,
        "disks": disks,
        "eligible_targets": eligible,
        "can_flash_here": (m["mode"] == "SD"),
    }

# ---------------- arming state (still no writes) ----------------

def arm_state_path() -> str:
    ensure_cache_dir()
    return os.path.join(CACHE_DIR, "arm_state.json")

def load_arm_state() -> dict | None:
    path = arm_state_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            st = json.load(f)
        if float(st.get("expires_at", 0)) < time.time():
            return None
        return st
    except Exception:
        return None

def save_arm_state(st: dict):
    path = arm_state_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(st, f)

def clear_arm_state():
    path = arm_state_path()
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# ---------------- jobs (downloads, later flash) ----------------

def jobs_dir() -> str:
    ensure_cache_dir()
    d = os.path.join(CACHE_DIR, "jobs")
    os.makedirs(d, exist_ok=True)
    return d

def job_file(job_id: str) -> str:
    return os.path.join(jobs_dir(), f"{job_id}.json")

def job_is_alive(pid: int) -> bool:
    return pid > 0 and os.path.exists(f"/proc/{pid}")

def job_load(job_id: str) -> dict | None:
    path = job_file(job_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def job_save(job: dict):
    job["updated_at"] = time.time()
    with open(job_file(job["id"]), "w", encoding="utf-8") as f:
        json.dump(job, f)

def job_refresh(job: dict) -> dict:
    # If running but process is gone, resolve via rc file
    if job.get("status") == "running":
        pid = int(job.get("pid", 0) or 0)
        if not job_is_alive(pid):
            rc_path = job.get("rc_path")
            rc = None
            if rc_path and os.path.exists(rc_path):
                try:
                    rc = int(Path(rc_path).read_text().strip() or "1")
                except Exception:
                    rc = 1
            job["status"] = "success" if rc == 0 else "failed"
            job["exit_code"] = rc if rc is not None else 1
            job_save(job)
    # JOB_STATUS_RC_WINS_JOB_REFRESH: rc file wins when present
    try:
        import re
        from pathlib import Path
        if isinstance(job, dict):
            _jid = job.get('id') or job.get('job_id')
            _jid = str(_jid) if _jid is not None else ''
            if _jid and re.fullmatch(r"[A-Za-z0-9_-]+", _jid):
                rc_path = Path('cache/jobs') / (_jid + '.rc')
                if rc_path.exists():
                    rc_txt = rc_path.read_text(encoding='utf-8', errors='ignore').strip()
                    try:
                        rc_val = int(rc_txt)
                    except Exception:
                        rc_val = None
                    job['exit_code'] = rc_val
                    job['rc'] = rc_val
                    job['status'] = 'success' if rc_val == 0 else 'failed'
                    job['done'] = True
                else:
                    if job.get('status') == 'running':
                        pid = job.get('pid')
                        if isinstance(pid, int) and (Path('/proc') / str(pid)).exists():
                            job['status'] = 'running'
                        else:
                            job['status'] = 'stale'
    except Exception as e:
        if isinstance(job, dict):
            job.setdefault('status_note', 'status_enrich_error: ' + str(e))
    return job

def start_job(job_type: str, script_body: str, meta: dict) -> dict:
    jid = secrets.token_hex(8)
    d = jobs_dir()
    script_path = os.path.join(d, f"{jid}.sh")
    log_path = os.path.join(d, f"{jid}.log")
    rc_path = os.path.join(d, f"{jid}.rc")

    script = "#!/bin/bash\n"
    script += "set -euo pipefail\n"
    script += f"trap 'echo $? > {shlex_quote(rc_path)}' EXIT\n"
    script += script_body.strip() + "\n"

    Path(script_path).write_text(script)
    os.chmod(script_path, 0o700)

    lf = open(log_path, "ab", buffering=0)
    proc = subprocess.Popen(["bash", script_path], stdout=lf, stderr=subprocess.STDOUT, start_new_session=True)

    job = {
        "id": jid,
        "type": job_type,
        "status": "running",
        "pid": proc.pid,
        "created_at": time.time(),
        "updated_at": time.time(),
        "script_path": script_path,
        "log_path": log_path,
        "rc_path": rc_path,
        "meta": meta or {},
    }
    job_save(job)
    return job

def shlex_quote(s: str) -> str:
    import shlex
    return shlex.quote(s)

def os_cache_dir() -> str:
    ensure_cache_dir()
    d = os.path.join(CACHE_DIR, "os")
    os.makedirs(d, exist_ok=True)
    return d

def os_cache_key(os_id: str, url: str) -> str:
    return hashlib.sha1((os_id + "|" + url).encode("utf-8")).hexdigest()[:16]

def os_cache_paths(os_id: str, url: str) -> dict:
    key = os_cache_key(os_id, url)
    base = os.path.join(os_cache_dir(), key)
    return {
        "key": key,
        "base": base,
        "meta": base + ".meta.json",
        "bin":  base + ".bin"
    }


# ---------------- routes ----------------

@app.get("/api/health")
def health():
    vi = version_info()
    m = detect_mode()
    return jsonify({
      "ok": True,
      "version": vi.get("version"),
      "semver": vi.get("semver"),
      "git_describe": vi.get("describe"),
      "git_commit": vi.get("commit"),
      "git_dirty": vi.get("dirty"),
      "version_source": vi.get("source"),
      **m
    })

@app.get("/api/urls")
def api_urls():
    return jsonify({"urls": list_urls(APP_PORT)})

@app.get("/api/safety")
def safety():
    s = safety_state()
    pol = load_policy()
    armed = load_arm_state()
    return jsonify({
        "version": get_version(),
        "policy": {
            "flash_enabled": bool(pol.get("flash_enabled", False)),      # STILL READ-ONLY
            "can_flash_here": s["can_flash_here"],
            "root_disk_blocked": True,
            "requires_sd_mode": True,
            "write_word": pol.get("write_word", "ERASE"),
            "arm_ttl_seconds": int(pol.get("arm_ttl_seconds", 600)),
        },
        "armed": {
            "active": bool(armed),
            "target": armed.get("target") if armed else None,
            "os_id": armed.get("os_id") if armed else None,
            "expires_at": armed.get("expires_at") if armed else None,
        },
        "state": {
            "mode": s["mode"],
            "root_source": s["root_source"],
            "root_parent": s["root_parent"],
        },
        "eligible_targets": s["eligible_targets"],
    })

@app.get("/api/disks")
def disks():
    # backward compat + UI visibility
    s = safety_state()
    return jsonify({
        "root_source": s["root_source"],
        "root_parent": s["root_parent"],
        "mode": s["mode"],
        "disks": s["disks"],
    })

@app.get("/api/os")
def api_os():
    catalog = load_os_catalog()
    q = request.args.get("q", "").strip().lower()
    if q in ("raspi", "rpi"):
        q = "raspberry"
    if q:
        catalog = [x for x in catalog if (q in x["name"].lower() or q in (x["description"] or "").lower())]
    return jsonify({"count": len(catalog), "items": catalog[:250]})

@app.post("/api/plan_flash")
def api_plan_flash():
    # DRY-RUN plan only
    body = request.get_json(force=True, silent=True) or {}
    target = str(body.get("target", "")).strip()
    os_id = str(body.get("os_id", "")).strip()

    s = safety_state()
    eligible_paths = {x["path"] for x in s["eligible_targets"]}

    if not s["can_flash_here"]:
        return jsonify({"ok": False, "error": "Not in SD mode. Flashing is only allowed when booted from SD."}), 400
    if target not in eligible_paths:
        return jsonify({"ok": False, "error": f"Target {target} is not an eligible target (root disk is blocked)."}), 400

    catalog = load_os_catalog()
    os_item = find_os(os_id, catalog)
    if not os_item:
        return jsonify({"ok": False, "error": "Unknown os_id. Refresh OS list and try again."}), 400

    pol = load_policy()
    url = os_item["url"]

    plan = {
        "ok": True,
        "note": "DRY-RUN ONLY. No writes occur in this build.",
        "confirmations_required": [
            {"type": "WORD", "value": pol.get("write_word", "ERASE")},
            {"type": "TARGET", "value": target},
        ],
        "target": target,
        "os": {
            "id": os_item["id"],
            "name": os_item["name"],
            "provider": os_item["provider_label"],
            "release_date": os_item.get("release_date"),
            "url": url,
            "download_sha256": os_item.get("image_download_sha256"),
            "extract_sha256": os_item.get("extract_sha256"),
            "download_size": os_item.get("image_download_size"),
            "extract_size": os_item.get("extract_size"),
        },
        "steps": [
            {"step": 1, "action": "Re-check safety", "detail": "Confirm target is not the root disk and SD mode is active."},
            {"step": 2, "action": "Download image", "detail": f"curl -L '{url}' -o cache/os.img (or cache/os.img.xz/zip)"},
            {"step": 3, "action": "Verify checksum (if available)", "detail": "Compare SHA256 of download/extract if publisher hash is provided."},
            {"step": 4, "action": "Decompress + write", "detail": f"{guess_decompress_cmd(url)} cache/os.* | sudo dd of={target} bs=4M conv=fsync status=progress"},
            {"step": 5, "action": "Sync + re-read partition table", "detail": "sync; sudo partprobe"},
        ],
        "warnings": [
            "This plan will destroy all data on the target disk when we enable flashing.",
            "Root disk is always blocked. Target must be explicitly selected and confirmed.",
        ]
    }
    return jsonify(plan)

@app.get("/api/arm_status")
def arm_status():
    st = load_arm_state()
    return jsonify({"active": bool(st), "state": st})

@app.post("/api/arm")
def arm():
    # STILL NO WRITES. This just creates a short-lived token that a future /api/flash will require.
    body = request.get_json(force=True, silent=True) or {}
    target = str(body.get("target", "")).strip()
    os_id = str(body.get("os_id", "")).strip()
    word = str(body.get("word", "")).strip().upper()
    confirm_target = str(body.get("confirm_target", "")).strip()
    serial_suffix = str(body.get("serial_suffix", "")).strip()

    pol = load_policy()
    s = safety_state()
    eligible = {x["path"]: x for x in s["eligible_targets"]}

    if not s["can_flash_here"]:
        return jsonify({"ok": False, "error": "Not in SD mode. Arming is only allowed when booted from SD."}), 400
    if target not in eligible:
        return jsonify({"ok": False, "error": "Target is not eligible (root disk is blocked)."}), 400
    if confirm_target != target:
        return jsonify({"ok": False, "error": "Target confirmation does not match exactly."}), 400
    if word != pol.get("write_word", "ERASE"):
        return jsonify({"ok": False, "error": f"Write word must be exactly: {pol.get('write_word','ERASE')}"}), 400

    if serial_suffix:
        actual = (eligible[target].get("serial") or "")
        if actual and not actual.endswith(serial_suffix):
            return jsonify({"ok": False, "error": "Serial suffix does not match target disk."}), 400

    ttl = int(pol.get("arm_ttl_seconds", 600))
    now = time.time()
    token = secrets.token_urlsafe(16)
    st = {
        "token": token,
        "target": target,
        "os_id": os_id,
        "issued_at": now,
        "expires_at": now + ttl,
    }
    save_arm_state(st)
    return jsonify({"ok": True, "armed": True, "state": st})

@app.post("/api/disarm")
def disarm():
    clear_arm_state()
    return jsonify({"ok": True, "armed": False})



@app.post("/api/flash")
def api_flash():
    """
    DESTRUCTIVE: Writes a cached OS image to a target disk.
    Requires:
      - SD mode (safety_state().can_flash_here)
      - policy.flash_enabled == true
      - valid, unexpired ARM token matching target + os_id
    """
    body = request.get_json(force=True, silent=True) or {}
    target = str(body.get("target", "")).strip()
    os_id = str(body.get("os_id", "")).strip()
    token = str(body.get("token", "")).strip()
    confirm_target = str(body.get("confirm_target", "")).strip()
    serial_suffix = str(body.get("serial_suffix", "")).strip()

    pol = load_policy()
    if not bool(pol.get("flash_enabled", False)):
        return jsonify({"ok": False, "error": "Flashing is disabled (policy.flash_enabled=false)."}), 403

    sstate = safety_state()
    eligible = {x["path"]: x for x in sstate["eligible_targets"]}

    if not sstate["can_flash_here"]:
        return jsonify({"ok": False, "error": "Not in SD mode. Flashing is only allowed when booted from SD."}), 400
    if not target or target not in eligible:
        return jsonify({"ok": False, "error": "Target is not eligible (root disk is blocked)."}), 400
    if confirm_target and confirm_target != target:
        return jsonify({"ok": False, "error": "Target confirmation does not match exactly."}), 400

    armed = load_arm_state()
    if not armed:
        return jsonify({"ok": False, "error": "Not armed. Call /api/arm first."}), 400

    now = time.time()
    exp = float(armed.get("expires_at") or 0)
    if exp <= now:
        clear_arm_state()
        return jsonify({"ok": False, "error": "ARM token expired. Re-arm and try again."}), 400

    if armed.get("target") != target:
        return jsonify({"ok": False, "error": "ARM state target does not match requested target."}), 400

    if not os_id:
        os_id = str(armed.get("os_id") or "").strip()
    if not os_id:
        return jsonify({"ok": False, "error": "os_id required (and must match what you armed with)."}), 400
    if armed.get("os_id") and armed.get("os_id") != os_id:
        return jsonify({"ok": False, "error": "ARM state os_id does not match requested os_id."}), 400

    if not token or token != str(armed.get("token") or ""):
        return jsonify({"ok": False, "error": "Invalid or missing token. Use the token returned by /api/arm."}), 400

    if serial_suffix:
        actual = (eligible[target].get("serial") or "")
        if actual and not actual.endswith(serial_suffix):
            return jsonify({"ok": False, "error": "Serial suffix does not match target disk."}), 400

    catalog = load_os_catalog()
    os_item = find_os(os_id, catalog)
    if not os_item:
        return jsonify({"ok": False, "error": "Unknown os_id. Refresh OS list and try again."}), 400

    url = os_item["url"]
    paths = os_cache_paths(os_id, url)
    in_path = paths["bin"]

    if not os.path.exists(in_path):
        return jsonify({"ok": False, "error": "OS image not cached. Call /api/download_os first.", "paths": paths}), 400

    # One-shot: disarm immediately so the token can't be reused.
    clear_arm_state()

    script = f"""
echo "=== FLASH JOB ==="
echo "TARGET={shlex_quote(target)}"
echo "IN={shlex_quote(in_path)}"
echo "URL={shlex_quote(url)}"

TARGET={shlex_quote(target)}
IN={shlex_quote(in_path)}
URL={shlex_quote(url)}

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo -n"
fi

if [ ! -b "$TARGET" ]; then
  echo "ERROR: target is not a block device: $TARGET"
  exit 10
fi
if [ ! -f "$IN" ]; then
  echo "ERROR: cached image missing: $IN"
  exit 11
fi

echo
echo "=== Unmount anything mounted on target (if any) ==="
lsblk -nrpo NAME,MOUNTPOINT "$TARGET" | awk 'NF>=2 && $2!="" {{print $1}}' | while read -r dev; do
  echo "umount $dev"
  $SUDO umount "$dev" 2>/dev/null || true
done

echo
echo "=== Write image to target (DESTROYS DATA) ==="
if [[ "$URL" == *.xz ]]; then
  command -v xz >/dev/null || {{ echo "ERROR: xz not installed"; exit 20; }}
  xz -dc "$IN" | $SUDO dd of="$TARGET" bs=4M conv=fsync status=progress
elif [[ "$URL" == *.gz ]]; then
  command -v gzip >/dev/null || {{ echo "ERROR: gzip not installed"; exit 21; }}
  gzip -dc "$IN" | $SUDO dd of="$TARGET" bs=4M conv=fsync status=progress
elif [[ "$URL" == *.zip ]]; then
  command -v unzip >/dev/null || {{ echo "ERROR: unzip not installed"; exit 22; }}
  unzip -p "$IN" | $SUDO dd of="$TARGET" bs=4M conv=fsync status=progress
else
  cat "$IN" | $SUDO dd of="$TARGET" bs=4M conv=fsync status=progress
fi

echo
echo "=== Sync + re-read partitions ==="
$SUDO sync
$SUDO partprobe "$TARGET" 2>/dev/null || true
$SUDO udevadm settle 2>/dev/null || true
echo "=== FLASH COMPLETE ==="
"""

    job = start_job("flash", script, {
        "os_id": os_id,
        "url": url,
        "in": in_path,
        "target": target,
        "paths": paths,
    })
    return jsonify({"ok": True, "job_id": job["id"], "job": job, "paths": paths})


@app.get("/api/job/<job_id>")
def api_job(job_id: str):
    # JOB_ID_VALIDATE_API_JOB: job_id is used to form filenames; keep it boring
    import re
    if not re.fullmatch(r"[A-Za-z0-9_-]+", job_id or ""):
        return jsonify({"ok": False, "error": "invalid job_id"}), 400
    job = job_load(job_id)
    if not job:
        return jsonify({"ok": False, "error": "Unknown job id"}), 404
    job = job_refresh(job)
    # JOB_STATUS_RC_WINS_API_JOB: rc file wins over stale 'running' state
    try:
        from pathlib import Path
        rc_path = Path('cache/jobs') / f"{job_id}.rc"
        if rc_path.exists():
            rc_txt = rc_path.read_text(encoding='utf-8', errors='ignore').strip()
            try:
                rc_val = int(rc_txt)
            except Exception:
                rc_val = None
            job['exit_code'] = rc_val
            job['rc'] = rc_val
            job['status'] = 'success' if rc_val == 0 else 'failed'
            job['done'] = True
        else:
            pid = job.get('pid')
            if isinstance(pid, int) and Path(f"/proc/{pid}").exists():
                job['status'] = 'running'
            elif job.get('status') == 'running':
                job['status'] = 'stale'
    except Exception as e:
        job.setdefault('status_note', f"status_enrich_error: {e}")
    # Don't spam huge logs in JSON; provide log path and let caller fetch tail via ssh if needed
    return jsonify({"ok": True, "job": job})


@app.get("/api/job/<job_id>/tail")
def api_job_tail(job_id):
  import re
  from pathlib import Path

  # job_id is used to form a filename; keep it boring and safe.
  if not re.fullmatch(r"[A-Za-z0-9_-]+", job_id or ""):
    return jsonify({"error": "invalid job_id"}), 400

  try:
    n = int(request.args.get("lines", "200"))
  except Exception:
    n = 200
  n = max(1, min(n, 2000))

  log_path = Path("cache/jobs") / f"{job_id}.log"
  if not log_path.exists():
    return jsonify({"job_id": job_id, "exists": False, "lines": []}), 404

  max_bytes = 512 * 1024  # read last 512KB max
  try:
    with log_path.open("rb") as f:
      f.seek(0, 2)
      size = f.tell()
      start = max(0, size - max_bytes)
      f.seek(start)
      data = f.read()
  except Exception as e:
    return jsonify({"job_id": job_id, "exists": True, "error": str(e)}), 500

  text = data.decode("utf-8", errors="replace")
  all_lines = text.splitlines()
  lines = all_lines[-n:]
  truncated = (len(all_lines) > len(lines)) or (start > 0)

  st = log_path.stat()
  return jsonify({
    "job_id": job_id,
    "exists": True,
    "lines": lines,
    "returned": len(lines),
    "truncated": truncated,
    "bytes_read": len(data),
    "mtime": st.st_mtime,
  })

@app.get("/api/os_cache")
def api_os_cache():
    os_id = request.args.get("os_id", "").strip()
    if not os_id:
        return jsonify({"ok": False, "error": "os_id required"}), 400
    catalog = load_os_catalog()
    os_item = find_os(os_id, catalog)
    if not os_item:
        return jsonify({"ok": False, "error": "Unknown os_id"}), 404
    paths = os_cache_paths(os_id, os_item["url"])
    meta = {}
    if os.path.exists(paths["meta"]):
        try:
            with open(paths["meta"], "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}
    exists = os.path.exists(paths["bin"])
    size = os.path.getsize(paths["bin"]) if exists else 0
    return jsonify({"ok": True, "cached": bool(exists), "size_bytes": size, "paths": paths, "meta": meta})

@app.post("/api/download_os")
def api_download_os():
    # Downloads image to cache on demand. Still NO disk writes.
    body = request.get_json(force=True, silent=True) or {}
    os_id = str(body.get("os_id", "")).strip()

    if not os_id:
        return jsonify({"ok": False, "error": "os_id required"}), 400

    sstate = safety_state()
    if not sstate["can_flash_here"]:
        return jsonify({"ok": False, "error": "Not in SD mode. Downloads are only allowed in Golden SD mode."}), 400

    catalog = load_os_catalog()
    os_item = find_os(os_id, catalog)
    if not os_item:
        return jsonify({"ok": False, "error": "Unknown os_id. Refresh OS list and try again."}), 400

    url = os_item["url"]
    expect = os_item.get("image_download_sha256") or ""
    paths = os_cache_paths(os_id, url)

    # If already cached, return cache info
    if os.path.exists(paths["bin"]) and os.path.exists(paths["meta"]):
        return jsonify({"ok": True, "cached": True, "paths": paths})

    # Write meta stub now (job will fill in actual sha/size)
    meta = {
        "os_id": os_id,
        "name": os_item.get("name"),
        "provider": os_item.get("provider_label"),
        "url": url,
        "expected_sha256": expect,
        "created_at": time.time(),
        "path": paths["bin"],
    }
    with open(paths["meta"], "w", encoding="utf-8") as f:
        json.dump(meta, f)

    script = f"""
echo "Downloading: {shlex_quote(url)}"
OUT={shlex_quote(paths["bin"])}
TMP="$OUT.tmp"
META={shlex_quote(paths["meta"])}
EXPECT={shlex_quote(expect)}

mkdir -p {shlex_quote(os_cache_dir())}

curl -L --fail --retry 3 --retry-delay 2 -o "$TMP" {shlex_quote(url)}
SHA=$(sha256sum "$TMP" | awk '{{print $1}}')
SIZE=$(stat -c %s "$TMP" || wc -c < "$TMP")

if [ -n "$EXPECT" ] && [ "$SHA" != "$EXPECT" ]; then
  echo "SHA256 MISMATCH"
  echo "expected=$EXPECT"
  echo "actual=$SHA"
  exit 2
fi

mv "$TMP" "$OUT"

python3 - <<'PY2'
import json, os, time
meta_path = os.environ.get("JR_META")
sha = os.environ.get("JR_SHA")
size = int(os.environ.get("JR_SIZE") or "0")
with open(meta_path, "r", encoding="utf-8") as f:
    m = json.load(f)
m["downloaded_at"] = time.time()
m["sha256_actual"] = sha
m["size_bytes"] = size
with open(meta_path, "w", encoding="utf-8") as f:
    json.dump(m, f)
print("META_UPDATED")
PY2
"""
    # inject env vars for python meta updater using bash exports
    script = script.replace("python3 - <<'PY2'", 'export JR_META="$META"\nexport JR_SHA="$SHA"\nexport JR_SIZE="$SIZE"\npython3 - <<\'PY2\'')

    job = start_job("download_os", script, {"os_id": os_id, "url": url, "out": paths["bin"]})

@app.get("/api/qr")
def api_qr():
    url = request.args.get("u", "").strip()
    if not url:
        urls = list_urls(APP_PORT)
        url = urls[0] if urls else f"http://127.0.0.1:{APP_PORT}/"
    import qrcode
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), mimetype="image/png")

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.get("/assets/<path:p>")
def assets(p):
    return send_from_directory(app.static_folder, p)

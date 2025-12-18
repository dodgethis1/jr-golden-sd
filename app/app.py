import json, os, subprocess, re, io, time, hashlib
from urllib.request import urlopen, Request
from urllib.error import URLError
from flask import Flask, jsonify, send_from_directory, Response, request

APP_PORT = int(os.environ.get("JR_GOLDEN_SD_PORT", "8025"))
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CACHE_DIR = os.path.join(BASE_DIR, "cache")

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"))

def sh(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()

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
    host = os.environ.get("HOSTNAME", "").strip()
    if host:
        urls.append(f"http://{host}.local:{port}/")

    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

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

        # Eligibility filtering (safety): ignore zram/loop/ram and anything without TRAN
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

def read_provider_files() -> list[dict]:
    pdir = os.path.join(BASE_DIR, "data", "os-providers")
    providers = []
    if not os.path.isdir(pdir):
        return providers
    for fn in sorted(os.listdir(pdir)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(pdir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if obj.get("enabled", True):
                providers.append(obj)
        except Exception:
            continue
    return providers

def cache_get(url: str, cache_name: str, ttl_seconds: int = 6*3600) -> bytes:
    os.makedirs(CACHE_DIR, exist_ok=True)
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
        # fallback to stale cache if present
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

def load_os_catalog() -> list[dict]:
    providers = read_provider_files()
    all_items = []
    for p in providers:
        if p.get("type") == "imager_v4":
            url = p["url"]
            data = cache_get(url, f"{p['id']}.json", ttl_seconds=6*3600)
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
    # Keep list stable-ish and not insane: sort by provider then name
    all_items.sort(key=lambda x: (x["provider_id"], x["name"]))
    return all_items

def find_os(os_id: str, catalog: list[dict]) -> dict | None:
    for it in catalog:
        if it["id"] == os_id:
            return it
    return None

def guess_decompress_cmd(url: str) -> str:
    u = url.lower()
    if u.endswith(".img.xz") or u.endswith(".xz"):
        return "xz -dc"
    if u.endswith(".zip"):
        return "unzip -p"
    return "(unknown extractor)"

@app.get("/api/health")
def health():
    m = detect_mode()
    return jsonify({"ok": True, "version": get_version(), **m})

@app.get("/api/urls")
def api_urls():
    return jsonify({"urls": list_urls(APP_PORT)})

@app.get("/api/safety")
def safety():
    s = safety_state()
    return jsonify({
        "version": get_version(),
        "policy": {
            "flash_enabled": False,  # still read-only build
            "can_flash_here": s["can_flash_here"],
            "root_disk_blocked": True,
            "requires_sd_mode": True,
        },
        "state": {
            "mode": s["mode"],
            "root_source": s["root_source"],
            "root_parent": s["root_parent"],
        },
        "eligible_targets": s["eligible_targets"],
    })

@app.get("/api/os")
def api_os():
    catalog = load_os_catalog()
    # optional q filter for UI
    q = request.args.get("q", "").strip().lower()
    if q:
        catalog = [x for x in catalog if (q in x["name"].lower() or q in (x["description"] or "").lower())]
    # cap to avoid phone choking
    return jsonify({"count": len(catalog), "items": catalog[:250]})

@app.post("/api/plan_flash")
def api_plan_flash():
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

    url = os_item["url"]
    plan = {
        "ok": True,
        "note": "DRY-RUN ONLY. No writes occur in this build.",
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
            "init_format": os_item.get("init_format"),
        },
        "steps": [
            {"step": 1, "action": "Re-check safety", "detail": "Confirm target is not the root disk and SD mode is active."},
            {"step": 2, "action": "Download image", "detail": f"curl -L '{url}' -o cache/os.img (or cache/os.img.xz/zip)"},
            {"step": 3, "action": "Verify checksum (if available)", "detail": "Compare SHA256 of download/extract if publisher hash is provided."},
            {"step": 4, "action": "Decompress + write", "detail": f"{guess_decompress_cmd(url)} cache/os.* | sudo dd of={target} bs=4M conv=fsync status=progress"},
            {"step": 5, "action": "Sync + re-read partition table", "detail": "sync; sudo partprobe"},
            {"step": 6, "action": "First boot customization", "detail": "If supported (Pi OS cloud-init), write user-data/network-config onto boot partition."}
        ],
        "warnings": [
            "This plan will destroy all data on the target disk when we enable flashing.",
            "Root disk is always blocked. Target must be explicitly selected and confirmed.",
            "Some OS images may not support first-boot customization; then it’s flash-only."
        ]
    }
    return jsonify(plan)

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

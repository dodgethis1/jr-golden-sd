import json, os, subprocess, re, io
from flask import Flask, jsonify, send_from_directory, Response, request

APP_PORT = int(os.environ.get("JR_GOLDEN_SD_PORT", "8025"))
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

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
        # fallback: strip partition suffixes
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
        # try transport hint
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
            # e.g. "eth0 UP 192.168.0.53/24 fe80::..."
            parts = line.split()
            if len(parts) < 3:
                continue
            iface = parts[0]
            state = parts[1]
            if state != "UP":
                continue
            # find IPv4s
            for p in parts[2:]:
                if re.match(r"^\d+\.\d+\.\d+\.\d+/\d+$", p):
                    ip4 = p.split("/")[0]
                    if ip4.startswith("127."):
                        continue
                    urls.append(f"http://{ip4}:{port}/")
    except Exception:
        pass

    # mDNS guess (only helpful if avahi works on your LAN)
    host = os.environ.get("HOSTNAME", "").strip()
    if host:
        urls.append(f"http://{host}.local:{port}/")

    # de-dupe while preserving order
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

@app.get("/api/health")
def health():
    m = detect_mode()
    return jsonify({
        "ok": True,
        "version": get_version(),
        **m
    })

@app.get("/api/urls")
def api_urls():
    return jsonify({"urls": list_urls(APP_PORT)})

@app.get("/api/disks")
def disks():
    cols = "NAME,KNAME,PATH,MODEL,SERIAL,SIZE,TYPE,TRAN,MOUNTPOINT,FSTYPE,ROTA,RM"
    raw = sh(["lsblk", "-J", "-o", cols])
    obj = json.loads(raw)
    rs = root_source()
    root_parent = parent_disk(rs)
    for d in obj.get("blockdevices", []):
        if d.get("type") == "disk":
            d["is_root_disk"] = (d.get("name") == root_parent)
    return jsonify({
        "root_source": rs,
        "root_parent": root_parent,
        "lsblk": obj,
    })

@app.get("/api/qr")
def api_qr():
    # Generates a QR PNG for the provided URL, or first detected URL.
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT)

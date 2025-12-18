import json, os, subprocess
from flask import Flask, jsonify, send_from_directory

APP_PORT = int(os.environ.get("JR_GOLDEN_SD_PORT", "8025"))
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"))

def sh(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True).strip()

def get_version() -> str:
    try:
        v = sh(["git", "describe", "--tags", "--always", "--dirty"])
        return v
    except Exception:
        return "0.0.0-dev"

def root_source() -> str:
    # e.g. /dev/mmcblk0p2 or /dev/nvme0n1p2
    try:
        return sh(["findmnt", "-no", "SOURCE", "/"])
    except Exception:
        return ""

def parent_disk(devpath: str) -> str:
    # Given /dev/mmcblk0p2 -> mmcblk0 ; /dev/nvme0n1p2 -> nvme0n1
    dev = devpath.replace("/dev/", "")
    if not dev:
        return ""
    try:
        pk = sh(["lsblk", "-no", "PKNAME", f"/dev/{dev}"])
        return pk.strip()
    except Exception:
        # fallback: strip trailing partition markers
        return dev.rstrip("0123456789").rstrip("p")

@app.get("/api/health")
def health():
    return jsonify({
        "ok": True,
        "version": get_version(),
        "root_source": root_source(),
    })

@app.get("/api/disks")
def disks():
    # Rich-ish lsblk JSON. We annotate which disk is the current root disk.
    cols = "NAME,KNAME,PATH,MODEL,SERIAL,SIZE,TYPE,TRAN,MOUNTPOINT,FSTYPE,ROTA,RM"
    raw = sh(["lsblk", "-J", "-o", cols])
    obj = json.loads(raw)
    rs = root_source()
    root_parent = parent_disk(rs)
    for d in obj.get("blockdevices", []):
        # mark top-level disks only
        if d.get("type") == "disk":
            d["is_root_disk"] = (d.get("name") == root_parent)
    return jsonify({
        "root_source": rs,
        "root_parent": root_parent,
        "lsblk": obj,
    })

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.get("/assets/<path:p>")
def assets(p):
    return send_from_directory(app.static_folder, p)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT)

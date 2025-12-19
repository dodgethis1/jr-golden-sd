from pathlib import Path
import sys

MARKER = "API_DEVICES_V1"

p = Path("app/app.py")
text = p.read_text(encoding="utf-8")
if MARKER in text:
    print("OK: devices endpoint already present (marker found).")
    sys.exit(0)

lines = text.splitlines(True)

# Find the /api/health decorator, then insert right after that function (before next @app.* decorator)
i = None
for idx, line in enumerate(lines):
    if line.strip() == '@app.get("/api/health")':
        i = idx
        break

if i is None:
    raise SystemExit('ERROR: Could not find @app.get("/api/health") to anchor insertion.')

j = None
for idx in range(i + 1, len(lines)):
    s = lines[idx]
    if s.startswith("@app.") and idx != i:
        j = idx
        break

if j is None:
    raise SystemExit("ERROR: Could not find next @app.* decorator after /api/health block.")

insert = r'''
# API_DEVICES_V1: read-only device inventory + Option-A target classification
def _devices_run(argv):
    import subprocess
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, (p.stdout or ""), (p.stderr or "")

def device_snapshot():
    import json, os, re, time

    rc, out, _err = _devices_run(["findmnt", "-no", "SOURCE", "/"])
    root_source = (out.strip() if rc == 0 else "")

    root_parent = ""
    if root_source:
        rc2, out2, _err2 = _devices_run(["lsblk", "-no", "PKNAME", root_source])
        root_parent = out2.strip()

        # Fallback parsing if lsblk PKNAME fails for some reason
        if not root_parent:
            name = os.path.basename(root_source).replace("/dev/", "")
            if name.startswith("nvme") and "p" in name:
                root_parent = name.split("p")[0]
            elif name.startswith("mmcblk") and "p" in name:
                root_parent = name.split("p")[0]
            else:
                root_parent = re.sub(r"\d+$", "", name)

    mode = "UNKNOWN"
    if root_parent.startswith("mmcblk"):
        mode = "SD"
    elif root_parent.startswith("nvme"):
        mode = "NVME"

    cols = "NAME,PATH,SIZE,MODEL,TRAN,RM,RO,TYPE,MOUNTPOINTS,FSTYPE,UUID,PKNAME"
    rc3, out3, _err3 = _devices_run(["lsblk", "-J", "-e7", "-o", cols])
    lsblk_json = {}
    if rc3 == 0 and out3.strip():
        try:
            lsblk_json = json.loads(out3)
        except Exception:
            lsblk_json = {"error": "lsblk_json_parse_failed"}

    blocks = (lsblk_json.get("blockdevices") if isinstance(lsblk_json, dict) else None) or []

    def collect_mountpoints(node):
        mps = []
        mp = node.get("mountpoints") or node.get("mountpoint")
        if isinstance(mp, list):
            mps += [x for x in mp if x]
        elif isinstance(mp, str) and mp:
            mps.append(mp)
        for ch in node.get("children") or []:
            mps += collect_mountpoints(ch)
        return mps

    disks_out = []
    for d in blocks:
        if d.get("type") != "disk":
            continue
        name = d.get("name") or ""
        if name.startswith(("ram", "zram", "loop")):
            continue

        mps = collect_mountpoints(d)
        is_root_parent = (name == root_parent)

        allowed = True
        why = []

        if is_root_parent:
            allowed = False
            why.append("is_root_parent")
        if mps:
            allowed = False
            why.append("mounted")

        # Option A rules
        if mode == "SD":
            # Booted from SD: allow flashing NVMe only
            if not (name.startswith("nvme") or (d.get("tran") == "nvme")):
                allowed = False
                why.append("mode_SD_allows_only_nvme_targets")
        elif mode == "NVME":
            # Booted from NVMe: allow flashing SD (mmcblk) or USB
            if not (name.startswith("mmcblk") or (d.get("tran") == "usb")):
                allowed = False
                why.append("mode_NVME_allows_only_sd_or_usb_targets")
        else:
            allowed = False
            why.append("mode_unknown")

        disks_out.append({
            "name": name,
            "path": d.get("path"),
            "size": d.get("size"),
            "model": d.get("model"),
            "tran": d.get("tran"),
            "rm": d.get("rm"),
            "ro": d.get("ro"),
            "mountpoints": mps,
            "is_root_parent": is_root_parent,
            "allowed_target_option_a": allowed,
            "why_not": why,
        })

    return {
        "generated_at": time.time(),
        "root_source": root_source,
        "root_parent": root_parent,
        "mode": mode,
        "disks": disks_out,
    }

@app.get("/api/devices")
def api_devices():
    snap = device_snapshot()
    return jsonify({"ok": True, **snap})
'''.lstrip("\n")

lines[j:j] = [insert]
p.write_text("".join(lines), encoding="utf-8")
print("OK: inserted /api/devices endpoint.")

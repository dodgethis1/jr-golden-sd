#!/usr/bin/env python3
import json, time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "http://127.0.0.1:8025"

def http_json(method, path, obj=None, timeout=6):
    url = BASE + path
    data = None
    headers = {}
    if obj is not None:
        data = json.dumps(obj).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(url, data=data, headers=headers, method=method)
    raw = b""
    code = None

    try:
        with urlopen(req, timeout=timeout) as r:
            code = r.getcode()
            raw = r.read() or b""
    except HTTPError as e:
        code = e.code
        raw = e.read() or b""
    except URLError as e:
        return None, {"ok": False, "error": f"URLError: {e}"}
    except Exception as e:
        return None, {"ok": False, "error": f"{type(e).__name__}: {e}"}

    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return code, {"ok": False, "error": "empty response body"}
    try:
        return code, json.loads(text)
    except Exception:
        return code, {"ok": False, "error": "non-json response", "raw": text[:4000]}

def wait_health(max_s=10):
    deadline = time.time() + max_s
    last = None
    while time.time() < deadline:
        code, data = http_json("GET", "/api/health", timeout=2)
        last = (code, data)
        if code == 200 and isinstance(data, dict) and data.get("ok"):
            return data
        time.sleep(0.25)
    raise SystemExit(f"Health never became OK. Last={last}")

def pick_allowed_target():
    code, snap = http_json("GET", "/api/devices", timeout=4)
    if code != 200 or not isinstance(snap, dict):
        raise SystemExit(f"/api/devices failed: {code} {snap}")
    disks = snap.get("disks") or []
    targets = [d.get("path") for d in disks if d.get("allowed_target_option_a")]
    targets = [t for t in targets if isinstance(t, str) and t.startswith("/dev/")]
    if not targets:
        raise SystemExit(f"No allowed targets found (Option A). disks={len(disks)}")
    return targets[0], snap

def pick_os_id():
    code, cat = http_json("GET", "/api/os?q=raspi", timeout=6)
    if code != 200 or not isinstance(cat, dict):
        raise SystemExit(f"/api/os failed: {code} {cat}")
    items = cat.get("items") or []
    if not items:
        raise SystemExit("No OS items returned.")
    return items[0].get("id")

def main():
    h = wait_health()
    print(f"health: ok mode={h.get('mode')} version={h.get('version')}")

    code, safety = http_json("GET", "/api/safety", timeout=4)
    if code != 200 or not isinstance(safety, dict):
        raise SystemExit(f"/api/safety failed: {code} {safety}")
    word = ((safety.get("policy") or {}).get("write_word") or "ERASE").strip().upper() or "ERASE"

    target, devsnap = pick_allowed_target()
    os_id = pick_os_id()

    print("mode:", devsnap.get("mode"), "root_parent:", devsnap.get("root_parent"))
    print("target:", target)
    print("os_id:", os_id)
    print("write_word:", word)

    code, plan = http_json("POST", "/api/plan_flash", {"target": target, "os_id": os_id}, timeout=10)
    print("\nplan:", code, plan)
    if code != 200 or not plan.get("ok"):
        raise SystemExit("plan_flash failed")

    plan_id = plan.get("plan_id")
    if not plan_id:
        raise SystemExit("plan_flash did not return plan_id")

    arm_body = {
        "plan_id": plan_id,
        "target": target,
        "os_id": os_id,
        "word": word,
        "confirm_target": target,
    }
    code, arm = http_json("POST", "/api/arm", arm_body, timeout=10)
    print("\narm:", code, arm)

    code, dis = http_json("POST", "/api/disarm", {}, timeout=5)
    print("\ndisarm:", code, dis)

if __name__ == "__main__":
    main()

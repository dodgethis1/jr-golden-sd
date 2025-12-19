#!/usr/bin/env bash
set -euo pipefail

BASE="http://127.0.0.1:8025"

python3 - <<'PY'
import json, time, urllib.request
from urllib.error import HTTPError, URLError

BASE = "http://127.0.0.1:8025"

def http_json(method: str, path: str, obj=None, timeout=8):
  url = BASE + path
  data = None
  headers = {}
  if obj is not None:
    data = json.dumps(obj).encode()
    headers["Content-Type"] = "application/json"
  req = urllib.request.Request(url, data=data, headers=headers, method=method)
  try:
    with urllib.request.urlopen(req, timeout=timeout) as r:
      body = r.read().decode("utf-8", errors="replace").strip()
      try:
        j = json.loads(body) if body else {}
      except Exception:
        j = {"_raw": body}
      return r.status, j
  except HTTPError as e:
    body = e.read().decode("utf-8", errors="replace").strip()
    try:
      j = json.loads(body) if body else {}
    except Exception:
      j = {"_raw": body}
    return e.code, j
  except URLError as e:
    return 0, {"error": f"URLError: {e}"}

# wait for health
ok = False
for _ in range(40):
  st, j = http_json("GET", "/api/health", None, timeout=2)
  if st == 200 and j.get("ok"):
    ok = True
    break
  time.sleep(0.25)
if not ok:
  raise SystemExit("FAIL: /api/health never became ok=true")

st, dev = http_json("GET", "/api/devices")
if st != 200 or not dev.get("disks"):
  raise SystemExit(f"FAIL: /api/devices status={st} body={dev}")

targets = [d["path"] for d in (dev.get("disks") or []) if d.get("allowed_target_option_a")]
if not targets:
  raise SystemExit("FAIL: No allowed targets found (Option A).")
target = targets[0]

st, safety = http_json("GET", "/api/safety")
word = ((safety.get("policy") or {}).get("write_word")) or "ERASE"

# pick an OS (keep it consistent with the other smoke)
st, cat = http_json("GET", "/api/os?q=raspi")
items = cat.get("items") or []
if st != 200 or not items:
  raise SystemExit(f"FAIL: /api/os?q=raspi status={st} body={cat}")
os_id = items[0]["id"]

print("mode:", (safety.get("state") or {}).get("mode"), "root_parent:", (safety.get("state") or {}).get("root_parent"))
print("allowed_targets:", targets)
print()

# plan
st, plan = http_json("POST", "/api/plan_flash", {"target": target, "os_id": os_id})
print("plan:", st, plan)
if st != 200 or not plan.get("ok") or not plan.get("plan_id"):
  raise SystemExit("FAIL: plan_flash did not return ok=true + plan_id")

plan_id = plan.get("plan_id")

# arm (MUST include plan_id)
arm_body = {
  "plan_id": plan_id,
  "target": target,
  "os_id": os_id,
  "word": word,
  "confirm_target": target,
}
st, arm = http_json("POST", "/api/arm", arm_body)
print()
print("arm:", st, arm)
if st != 200 or not arm.get("ok") or not ((arm.get("state") or {}).get("token")):
  raise SystemExit("FAIL: arm did not return ok=true + token")

# disarm
st, dis = http_json("POST", "/api/disarm", {})
print()
print("disarm:", st, dis)
if st != 200 or not dis.get("ok"):
  raise SystemExit("FAIL: disarm did not return ok=true")

print()
print("SMOKE PLAN/ARM/DISARM OK")
PY

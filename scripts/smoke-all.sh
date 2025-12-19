#!/usr/bin/env bash
set -euo pipefail

base="${BASE_URL:-http://127.0.0.1:8025}"
cd /opt/jr-pi-toolkit/golden-sd || { echo "FAIL: repo path missing"; exit 2; }

echo "== health (expect ok=true) =="
curl -sS --max-time 3 "${base}/api/health" | python3 -c 'import sys, json
d = json.loads(sys.stdin.read() or "{}")
ok = d.get("ok")
if ok is not True:
    raise SystemExit(f"FAIL: health ok != true (got {ok!r})")
print("OK: health", "mode="+str(d.get("mode")), "version="+str(d.get("version")))'

echo
echo "== os catalog query raspi (expect >=1 item) =="
curl -sS --max-time 8 "${base}/api/os?q=raspi" | python3 -c 'import sys, json
d = json.loads(sys.stdin.read() or "{}")
items = None
if isinstance(d, list):
    items = d
elif isinstance(d, dict):
    for k in ("items","results","os","data"):
        v = d.get(k)
        if isinstance(v, list):
            items = v
            break
if not isinstance(items, list):
    raise SystemExit("FAIL: /api/os response not list-like")
if len(items) < 1:
    raise SystemExit("FAIL: /api/os?q=raspi returned 0 items")
print(f"OK: /api/os?q=raspi items={len(items)}")'

echo
echo "== job status suite =="
./scripts/smoke-job-status.sh

echo
echo "SMOKE ALL OK"

#!/usr/bin/env bash
set -euo pipefail

base="${BASE_URL:-http://127.0.0.1:8025}"
cd /opt/jr-pi-toolkit/golden-sd || { echo "FAIL: repo path missing"; exit 2; }

jid="smoke-rc-$(date +%s)"
mkdir -p cache/jobs

printf '{"id":"%s","status":"running","pid":999999,"note":"smoke test job"}\n' "$jid" > "cache/jobs/${jid}.json"
printf '0\n' > "cache/jobs/${jid}.rc"

echo "== GET /api/job/${jid} (expect status=success, exit_code=0) =="
body="$(curl -sS --max-time 3 "${base}/api/job/${jid}")"

printf '%s' "$body" | python3 -c 'import sys, json
d = json.loads(sys.stdin.read() or "{}")
j = d.get("job") or {}
st = j.get("status")
ec = j.get("exit_code")
if st != "success":
    raise SystemExit(f"FAIL: status not success (got {st!r})")
if ec != 0:
    raise SystemExit(f"FAIL: expected exit_code=0 (got {ec!r})")
print("OK: rc-wins job status")'

echo
echo "== GET invalid job id (expect HTTP 400) =="
code="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 3 "${base}/api/job/bad.id" || true)"
test "$code" = "400" || { echo "FAIL: expected 400, got $code"; exit 4; }
echo "OK: invalid job id returns 400"

echo
echo "SMOKE JOB STATUS OK"

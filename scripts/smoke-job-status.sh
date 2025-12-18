#!/bin/bash
set -euo pipefail
cd /opt/jr-pi-toolkit/golden-sd || exit 1

base="http://127.0.0.1:8025"

jid="smoke-rc-$(date +%s)"
mkdir -p cache/jobs

cat > "cache/jobs/${jid}.json" <<EOF
{"id":"${jid}","status":"running","pid":999999,"note":"smoke test job"}
EOF

printf "0\n" > "cache/jobs/${jid}.rc"

echo "== GET /api/job/${jid} (expect success, exit_code 0) =="
body="$(curl -sS --max-time 3 "${base}/api/job/${jid}")"
echo "$body" | python3 -m json.tool | sed -n '1,80p'

# Parse JSON properly so whitespace can't screw us
printf '%s' "$body" | python3 -c 'import json,sys
data=json.load(sys.stdin)
job=data.get("job") or {}
status=job.get("status")
exit_code=job.get("exit_code")
if status!="success":
    print(f"FAIL: expected status=success, got {status!r}")
    raise SystemExit(3)
if exit_code!=0:
    print(f"FAIL: expected exit_code=0, got {exit_code!r}")
    raise SystemExit(4)
print("OK: job success + exit_code 0")
'

echo "== GET invalid job id (expect 400) =="
code="$(curl -sS -o /dev/null -w "%{http_code}" "${base}/api/job/bad.id")"
test "$code" = "400" || { echo "FAIL: expected 400, got $code"; exit 5; }

echo "SMOKE OK"

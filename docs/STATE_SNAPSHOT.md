# Golden SD State Snapshot

Generated: 2025-12-18T13:07:20-06:00

## Git
```
## main...origin/main
?? app/app.py.bak.20251218-125542
?? docs/HANDOFF.md
?? docs/STATE_SNAPSHOT.md
?? scripts/make-handoff-snapshot.sh
origin	git@github.com:dodgethis1/jr-golden-sd.git (fetch)
origin	git@github.com:dodgethis1/jr-golden-sd.git (push)
277beeb feat(api): add job log tail endpoint (/api/job/<job_id>/tail)
```

## Service
```
● jr-golden-sd.service - JR Golden SD Web UI
     Loaded: loaded (/etc/systemd/system/jr-golden-sd.service; enabled; preset: enabled)
     Active: active (running) since Thu 2025-12-18 13:00:08 CST; 7min ago
 Invocation: 148f2ee6db254b5c9d5d5033ce351bf8
   Main PID: 4380 (gunicorn)
      Tasks: 3 (limit: 19365)
        CPU: 346ms
     CGroup: /system.slice/jr-golden-sd.service
             ├─4380 /opt/jr-pi-toolkit/golden-sd/.venv/bin/python /opt/jr-pi-toolkit/golden-sd/.venv/bin/gunicorn -w 2 -b 0.0.0.0:8025 app.app:app
             ├─4384 /opt/jr-pi-toolkit/golden-sd/.venv/bin/python /opt/jr-pi-toolkit/golden-sd/.venv/bin/gunicorn -w 2 -b 0.0.0.0:8025 app.app:app
             └─4385 /opt/jr-pi-toolkit/golden-sd/.venv/bin/python /opt/jr-pi-toolkit/golden-sd/.venv/bin/gunicorn -w 2 -b 0.0.0.0:8025 app.app:app

Dec 18 13:00:08 rpi-goldensd systemd[1]: Started jr-golden-sd.service - JR Golden SD Web UI.
Dec 18 13:00:08 rpi-goldensd gunicorn[4380]: [2025-12-18 13:00:08 -0600] [4380] [INFO] Starting gunicorn 23.0.0
Dec 18 13:00:08 rpi-goldensd gunicorn[4380]: [2025-12-18 13:00:08 -0600] [4380] [INFO] Listening at: http://0.0.0.0:8025 (4380)
Dec 18 13:00:08 rpi-goldensd gunicorn[4380]: [2025-12-18 13:00:08 -0600] [4380] [INFO] Using worker: sync
Dec 18 13:00:08 rpi-goldensd gunicorn[4384]: [2025-12-18 13:00:08 -0600] [4384] [INFO] Booting worker with pid: 4384
Dec 18 13:00:08 rpi-goldensd gunicorn[4385]: [2025-12-18 13:00:08 -0600] [4385] [INFO] Booting worker with pid: 4385
```

## Listening (8025)
```
LISTEN 0      2048         0.0.0.0:8025      0.0.0.0:*    users:(("gunicorn",pid=4385,fd=5),("gunicorn",pid=4384,fd=5),("gunicorn",pid=4380,fd=5))
```

## Health + Safety
```
{"mode":"SD","ok":true,"root_parent":"mmcblk0","root_source":"/dev/mmcblk0p2","version":"277beeb"}

{"armed":{"active":false,"expires_at":null,"os_id":null,"target":null},"eligible_targets":[{"is_root_disk":false,"model":"TEAM TM5FF3001T","name":"nvme0n1","path":"/dev/nvme0n1","rm":false,"rota":false,"serial":"TPBF2501090030100111","size":"953.9G","tran":"nvme"}],"policy":{"arm_ttl_seconds":600,"can_flash_here":true,"flash_enabled":false,"requires_sd_mode":true,"root_disk_blocked":true,"write_word":"ERASE"},"state":{"mode":"SD","root_parent":"mmcblk0","root_source":"/dev/mmcblk0p2"},"version":"277beeb"}
```

## UI files (static/)
```
static/index.html
```

## UI references to API routes
```
static/index.html:93:  const data = await j("/api/os" + (q ? ("?q=" + encodeURIComponent(q)) : ""));
static/index.html:106:  const h = await j("/api/health");
static/index.html:113:  const u = await j("/api/urls");
static/index.html:119:    `<b>QR (scan me):</b><br><img src="/api/qr?u=${encodeURIComponent(first)}" alt="QR"><br><small><code>${first}</code></small>`;
static/index.html:121:  const s = await j("/api/safety");
static/index.html:150:    const r = await fetch("/api/plan_flash", {
static/index.html:167:    const r = await fetch("/api/arm", {
static/index.html:180:    const r = await fetch("/api/download_os", {
static/index.html:191:    const r = await fetch("/api/disarm", { method: "POST" });
```

## Flask route decorators (app/app.py)
```
397:@app.get("/api/health")
402:@app.get("/api/urls")
406:@app.get("/api/safety")
435:@app.get("/api/disks")
446:@app.get("/api/os")
454:@app.post("/api/plan_flash")
510:@app.get("/api/arm_status")
515:@app.post("/api/arm")
556:@app.post("/api/disarm")
563:@app.post("/api/flash")
700:@app.get("/api/job/<job_id>")
710:@app.get("/api/job/<job_id>/tail")
756:@app.get("/api/os_cache")
777:@app.post("/api/download_os")
859:@app.get("/api/qr")
871:@app.get("/")
875:@app.get("/assets/<path:p>")
```

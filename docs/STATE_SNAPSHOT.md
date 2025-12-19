# STATE SNAPSHOT

- Generated: 2025-12-19T10:31:28-06:00
- Host: rpi-goldensd
- Repo: /opt/jr-pi-toolkit/golden-sd
- Branch: feat/plan-flash-dryrun-token
- Commit: be18948

## Base URLs (from /api/urls if available)
```json
{
    "urls": [
        "http://192.168.0.53:8025/",
        "http://192.168.0.54:8025/"
    ]
}
```

## Flask routes (runtime url_map)
```json
{
    "routes": [
        {
            "rule": "/",
            "methods": [
                "GET"
            ],
            "endpoint": "index"
        },
        {
            "rule": "/api/arm",
            "methods": [
                "POST"
            ],
            "endpoint": "arm"
        },
        {
            "rule": "/api/arm_status",
            "methods": [
                "GET"
            ],
            "endpoint": "arm_status"
        },
        {
            "rule": "/api/devices",
            "methods": [
                "GET"
            ],
            "endpoint": "api_devices"
        },
        {
            "rule": "/api/disarm",
            "methods": [
                "POST"
            ],
            "endpoint": "disarm"
        },
        {
            "rule": "/api/disks",
            "methods": [
                "GET"
            ],
            "endpoint": "disks"
        },
        {
            "rule": "/api/download_os",
            "methods": [
                "POST"
            ],
            "endpoint": "api_download_os"
        },
        {
            "rule": "/api/flash",
            "methods": [
                "POST"
            ],
            "endpoint": "api_flash"
        },
        {
            "rule": "/api/health",
            "methods": [
                "GET"
            ],
            "endpoint": "health"
        },
        {
            "rule": "/api/job/<job_id>",
            "methods": [
                "GET"
            ],
            "endpoint": "api_job"
        },
        {
            "rule": "/api/job/<job_id>/tail",
            "methods": [
                "GET"
            ],
            "endpoint": "api_job_tail"
        },
        {
            "rule": "/api/os",
            "methods": [
                "GET"
            ],
            "endpoint": "api_os"
        },
        {
            "rule": "/api/os_cache",
            "methods": [
                "GET"
            ],
            "endpoint": "api_os_cache"
        },
        {
            "rule": "/api/plan_flash",
            "methods": [
                "POST"
            ],
            "endpoint": "api_plan_flash"
        },
        {
            "rule": "/api/qr",
            "methods": [
                "GET"
            ],
            "endpoint": "api_qr"
        },
        {
            "rule": "/api/safety",
            "methods": [
                "GET"
            ],
            "endpoint": "safety"
        },
        {
            "rule": "/api/urls",
            "methods": [
                "GET"
            ],
            "endpoint": "api_urls"
        },
        {
            "rule": "/assets/<path:p>",
            "methods": [
                "GET"
            ],
            "endpoint": "assets"
        },
        {
            "rule": "/static/<path:filename>",
            "methods": [
                "GET"
            ],
            "endpoint": "static"
        }
    ]
}
```

## Frontend files (static/)
- `static/index.html`

## Frontend references to API routes (best-effort)
- `/api/arm`
- `/api/arm_status`
- `/api/disarm`
- `/api/disks`
- `/api/download_os`
- `/api/health`
- `/api/job/`
- `/api/job/<`
- `/api/os`
- `/api/plan_flash`
- `/api/qr?u=`
- `/api/safety`
- `/api/urls`

## Health + safety (current)
### /api/health
```json
{
    "git_commit": "be1894836c91",
    "git_describe": "be18948-dirty",
    "git_dirty": true,
    "mode": "SD",
    "ok": true,
    "root_parent": "mmcblk0",
    "root_source": "/dev/mmcblk0p2",
    "semver": null,
    "version": "be18948-dirty",
    "version_source": "git"
}
```

### /api/safety
```json
{
    "armed": {
        "active": false,
        "expires_at": null,
        "os_id": null,
        "target": null
    },
    "eligible_targets": [
        {
            "is_root_disk": false,
            "model": "TEAM TM5FF3001T",
            "name": "nvme0n1",
            "path": "/dev/nvme0n1",
            "rm": false,
            "rota": false,
            "serial": "TPBF2501090030100111",
            "size": "953.9G",
            "tran": "nvme"
        }
    ],
    "policy": {
        "arm_ttl_seconds": 600,
        "can_flash_here": true,
        "flash_enabled": false,
        "requires_sd_mode": true,
        "root_disk_blocked": true,
        "write_word": "ERASE"
    },
    "state": {
        "mode": "SD",
        "root_parent": "mmcblk0",
        "root_source": "/dev/mmcblk0p2"
    },
    "version": "be18948-dirty"
}
```

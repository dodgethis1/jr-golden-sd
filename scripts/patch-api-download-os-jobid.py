from pathlib import Path
import re

p = Path("app/app.py")
s = p.read_text(encoding="utf-8")

# Replace the 2-line "job_id = ..." + "return jsonify(...job_id...)" block we injected
pat = re.compile(
    r'(job\s*=\s*start_job\("download_os",\s*script,\s*\{"os_id":\s*os_id,\s*"url":\s*url,\s*"out":\s*paths\["bin"\]\}\)\s*\n)'
    r'(\s*job_id\s*=\s*.*\n)'
    r'(\s*return\s+jsonify\(\{"ok":\s*True,\s*"cached":\s*False,\s*"job_id":\s*job_id,\s*"paths":\s*paths\}\),\s*202\s*\n)'
)

m = pat.search(s)
if not m:
    raise SystemExit("ERROR: Could not find the injected job_id/return block to replace. Paste the api_download_os section again if needed.")

indent = re.match(r'\s*', m.group(2)).group(0)

replacement = (
    m.group(1) +
    f"{indent}# start_job() may return a dict or a string; normalize to job_id\n" +
    f"{indent}job_id = None\n" +
    f"{indent}if isinstance(job, dict):\n" +
    f"{indent}    job_id = job.get('job_id') or job.get('id') or job.get('job') or job.get('jid')\n" +
    f"{indent}else:\n" +
    f"{indent}    job_id = str(job) if job is not None else None\n" +
    f"{indent}return jsonify({{'ok': True, 'cached': False, 'job_id': job_id, 'job': job, 'paths': paths}}), 202\n"
)

s2, n = pat.subn(replacement, s, count=1)
if n != 1:
    raise SystemExit(f"ERROR: Expected 1 replacement, got {n}")

p.write_text(s2, encoding="utf-8")
print("OK: Patched api_download_os to return job_id robustly.")

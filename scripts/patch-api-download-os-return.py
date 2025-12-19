from pathlib import Path

p = Path("app/app.py")
s = p.read_text(encoding="utf-8").splitlines(True)

needle = 'job = start_job("download_os", script, {"os_id": os_id, "url": url, "out": paths["bin"]})'

# idempotent: if we already added our return, don't do it again
if any('cached": False' in line and "job_id" in line and "/api/download_os" not in line for line in s):
    print("OK: looks like download_os already returns cached:false + job_id somewhere; not patching.")
    raise SystemExit(0)

out = []
patched = False
for line in s:
    out.append(line)
    if (not patched) and (needle in line):
        indent = line[:len(line) - len(line.lstrip())]
        out.append("\n")
        out.append(f"{indent}job_id = job.get(\"job_id\") if isinstance(job, dict) else job\n")
        out.append(f"{indent}return jsonify({{\"ok\": True, \"cached\": False, \"job_id\": job_id, \"paths\": paths}}), 202\n")
        patched = True

if not patched:
    raise SystemExit("ERROR: Could not find expected start_job('download_os', ...) line to patch.")

p.write_text("".join(out), encoding="utf-8")
print("OK: Patched api_download_os to return JSON after starting job.")

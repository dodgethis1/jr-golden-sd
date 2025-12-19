from pathlib import Path
from datetime import datetime

path = Path("static/index.html")
text = path.read_text(encoding="utf-8")

marker = "JR_AUTO_FOLLOW_DOWNLOAD_JOB_V2"
if marker in text:
    print("OK: already patched:", marker)
    raise SystemExit(0)

needle = 'document.getElementById("dlBtn").addEventListener("click", async () => {'
i0 = text.find(needle)
if i0 < 0:
    print("ERROR: could not find dlBtn handler")
    raise SystemExit(1)

dlout = 'document.getElementById("dlOut").innerHTML'
i1 = text.find(dlout, i0)
if i1 < 0:
    print("ERROR: could not find dlOut render inside dlBtn handler")
    raise SystemExit(1)

# Insert right after the dlOut statement ends (first semicolon after that line)
semi = text.find(";</", i1)
if semi < 0:
    semi = text.find(";\n", i1)
if semi < 0:
    semi = text.find(";", i1)
if semi < 0:
    print("ERROR: could not find statement end for dlOut render")
    raise SystemExit(1)

insert_at = semi + 1

snippet = f"""
      // {marker}: when /api/download_os returns a job, auto-fill Job monitor + start following.
      try {{
        const jid = (data && (data.job_id || (data.job && data.job.id))) ? (data.job_id || data.job.id) : "";
        if (jid) {{
          const jobIdEl = document.getElementById("jobId");
          if (jobIdEl) jobIdEl.value = jid;
          startJobFollow(jid);
        }}
      }} catch (e) {{
        console.warn("auto-follow download job failed:", e);
      }}
"""

bak = path.with_suffix(path.suffix + ".bak." + datetime.now().strftime("%Y%m%d-%H%M%S"))
bak.write_text(text, encoding="utf-8")

text2 = text[:insert_at] + snippet + text[insert_at:]
path.write_text(text2, encoding="utf-8")

print("OK: patched", path)
print("OK: backup ->", bak)

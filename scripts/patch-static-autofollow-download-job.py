from pathlib import Path
from datetime import datetime

p = Path("static/index.html")
txt = p.read_text(encoding="utf-8")

marker = "JR_AUTO_FOLLOW_DOWNLOAD_JOB_V1"
if marker in txt:
    print("OK: already patched")
    raise SystemExit(0)

# Find the download button handler block by anchoring between dlBtn and disarmBtn
a = txt.find('document.getElementById("dlBtn")')
if a < 0:
    a = txt.find("document.getElementById('dlBtn')")
if a < 0:
    raise SystemExit('ERROR: could not find dlBtn handler in static/index.html')

b = txt.find('document.getElementById("disarmBtn")', a)
if b < 0:
    b = txt.find("document.getElementById('disarmBtn')", a)
if b < 0:
    raise SystemExit('ERROR: could not find disarmBtn anchor after dlBtn (file layout changed)')

block = txt[a:b]

# Find where dlOut gets written so we can inject right after it
needle1 = 'document.getElementById("dlOut").innerHTML'
needle2 = "document.getElementById('dlOut').innerHTML"
k = block.find(needle1)
if k < 0:
    k = block.find(needle2)
if k < 0:
    raise SystemExit('ERROR: could not find dlOut innerHTML assignment inside dlBtn block')

# Insert after the next semicolon following the dlOut assignment
semi = block.find(";", k)
if semi < 0:
    raise SystemExit("ERROR: couldn't find statement terminator ';' after dlOut assignment")

inject = (
    "\n"
    f"      // {marker}: if backend returns a job_id, auto-follow it in the Job monitor\n"
    "      try{\n"
    "        if (data && data.job_id){\n"
    "          startJobFollow(String(data.job_id));\n"
    "        }\n"
    "      }catch(e){\n"
    '        console.warn("auto-follow download_os job failed:", e);\n'
    "      }\n"
)

new_block = block[:semi+1] + inject + block[semi+1:]
new_txt = txt[:a] + new_block + txt[b:]

bak = p.with_name(f"index.html.bak.{datetime.now().strftime('%Y%m%d-%H%M%S')}")
bak.write_text(txt, encoding="utf-8")
p.write_text(new_txt, encoding="utf-8")

print(f"OK: patched {p}")
print(f"OK: backup  {bak}")

from pathlib import Path
from datetime import datetime

marker = "<!-- PASTE_SAFETY_RULES -->"

section = f"""{marker}
## Paste-safe instructions rules (for ChatGPT + operator)

**Goal:** Prevent “mangled paste” failures during Windows PowerShell → SSH → bash workflows.

### What a heredoc is (plain English)
A *heredoc* is a shell feature that writes a multi-line block into a file, typically using `<<EOF` ... `EOF`.
If the closing terminator line (like `EOF`) gets corrupted or dropped mid-paste, the shell may keep consuming input and break the session.

### Rules for all copy/paste blocks we generate
1. **One heredoc maximum per paste block.**  
   If we need multiple files, split into multiple paste blocks.
2. **No nested heredocs.**  
   Avoid heredocs inside scripts that themselves contain heredocs.
3. **Two-step flow:**  
   - Step A: write file(s)  
   - Step B: run/verify  
   Never mix “write + execute” in the same paste when it’s large or delicate.
4. **Interactive safety mode by default:**  
   Use `set -u` for interactive/debug steps so one failure doesn’t nuke the SSH session.  
   Use `set -euo pipefail` only for short, final scripts where failing fast is desired.
5. **Delimiter hygiene:**  
   Heredoc terminators (`EOF`, `PY`, `SH`, etc.) must be **alone on a line**, with **no spaces** and no indentation.
6. **Whitespace-proof validation:**  
   Don’t grep JSON strings with exact spacing. Parse JSON (e.g., `python3 -m json.tool` or a small Python `json.loads`) to assert values.
7. **Minimize paste size:**  
   Prefer smaller, sequential paste blocks over one giant paste blob.

### Operator hint
If a paste gets mangled, the fix is usually: **overwrite the target file completely** with a clean paste block, then re-run the command.
"""

targets = [
    Path("docs/HANDOFF.md"),
    Path("docs/HANDOFF_CHATGPT.md"),
]

patched_any = False

for t in targets:
    if not t.exists():
        continue

    text = t.read_text(encoding="utf-8", errors="ignore")
    if marker in text:
        continue

    bak = t.with_name(f"{t.name}.bak.{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    bak.write_text(text, encoding="utf-8")

    # Append at end with a clean blank line
    new_text = text.rstrip() + "\n\n" + section.strip() + "\n"
    t.write_text(new_text, encoding="utf-8")
    print(f"OK: patched {t} (backup {bak.name})")
    patched_any = True

if not patched_any:
    print("OK: no changes needed (marker already present or no target docs found).")

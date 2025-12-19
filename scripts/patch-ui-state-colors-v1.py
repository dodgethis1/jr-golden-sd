from pathlib import Path
import re
import sys

p = Path("static/index.html")
s = p.read_text(encoding="utf-8")

if "JR_STATE_COLORS_V1" in s:
    print("OK: JR_STATE_COLORS_V1 already present")
    sys.exit(0)

def must_replace(pattern, repl, desc, flags=0):
    global s
    s2, n = re.subn(pattern, repl, s, count=1, flags=flags)
    if n != 1:
        print(f"ERROR: failed patch step: {desc}", file=sys.stderr)
        sys.exit(1)
    s = s2

# 1) Add CSS for semantic pill colors + box borders (append near end of <style>)
css_add = r"""
  /* JR_STATE_COLORS_V1: semantic colors for quick "all green" readiness scanning */
  :root{
    --ok: #16a34a;
    --bad: #dc2626;
    --amber: #f59e0b;
    --info: var(--link);
  }
  :root[data-theme="dark"]{
    --ok: #22c55e;
    --bad: #ff5566;
    --amber: #fbbf24;
    --info: var(--link);
  }

  /* override earlier warn usage to actually be amber */
  .warn { border-color: var(--amber); }

  .box.ok  { border-color: var(--ok); }
  .box.bad { border-color: var(--bad); }

  .pill.ok {
    border-color: var(--ok);
    background: color-mix(in srgb, var(--ok) 18%, var(--pill-bg));
  }
  .pill.bad {
    border-color: var(--bad);
    background: color-mix(in srgb, var(--bad) 16%, var(--pill-bg));
  }
  .pill.warn {
    border-color: var(--amber);
    background: color-mix(in srgb, var(--amber) 18%, var(--pill-bg));
  }
  .pill.info {
    border-color: var(--info);
    background: color-mix(in srgb, var(--info) 16%, var(--pill-bg));
  }
"""
if "</style>" not in s:
    print("ERROR: no </style> found", file=sys.stderr)
    sys.exit(1)
s = s.replace("</style>", css_add + "\n</style>", 1)

# 2) Insert pill helper functions (right before fmtDisk)
helper_block = r"""
// JR_STATE_COLORS_V1 helpers
function pill(kind, txt){
  const k = kind ? (" " + kind) : "";
  return `<span class="pill${k}">${esc(txt)}</span>`;
}
function pillBool(v, okTxt="true", badTxt="false"){
  return pill(v ? "ok" : "bad", v ? okTxt : badTxt);
}
// end JR_STATE_COLORS_V1 helpers

"""
must_replace(r"(\nfunction fmtDisk\()", "\n" + helper_block + "function fmtDisk(", "insert pill helpers before fmtDisk", flags=0)

# 3) Ensure eligible targets are defined once (move earlier, remove later redeclare)
must_replace(
    r"(const pol = \(safety && safety\.policy\) \|\| \{\};\n)",
    r"\1\n  const eligible = (safety && safety.eligible_targets) ? safety.eligible_targets : [];\n",
    "define eligible targets near policy"
)

# Remove later `const eligible = ...;` line inside the disk section
s2, n = re.subn(r"\n\s*const eligible = \(safety && safety\.eligible_targets\) \? safety\.eligible_targets : \[\];\n", "\n  // eligible defined above\n", s, count=1)
if n != 1:
    print("ERROR: couldn't remove later eligible redeclare", file=sys.stderr)
    sys.exit(1)
s = s2

# 4) Add computed kinds + ready indicator inputs right after rootDisk line
insert_after = r'(const rootDisk = rootParent \? \(\"/dev/\" \+ rootParent\) : \"\(unknown\)\";\n)'
insertion = r"""\1
  const modeKind = (mode === "SD") ? "ok" : "warn";

  const canFlashKnown = (pol.can_flash_here !== undefined && pol.can_flash_here !== null);
  const canFlashVal = (pol.can_flash_here === true);
  const canFlashKind = canFlashKnown ? (canFlashVal ? "ok" : "bad") : "warn";
  const canFlashTxt2 = canFlashKnown ? String(canFlashVal) : "unknown";

  const rootBlockedKnown = (pol.root_disk_blocked !== undefined && pol.root_disk_blocked !== null);
  const rootBlockedVal = (pol.root_disk_blocked === true);
  const rootBlockedKind = rootBlockedKnown ? (rootBlockedVal ? "ok" : "bad") : "warn";
  const rootBlockedTxt2 = rootBlockedKnown ? String(rootBlockedVal) : "unknown";

  const reqSDKnown = (pol.requires_sd_mode !== undefined && pol.requires_sd_mode !== null);
  const reqSDVal = (pol.requires_sd_mode === true);
  const reqSDKind = reqSDKnown ? ((reqSDVal and mode == "SD") and "ok" or (reqSDVal and "warn" or "bad")) : "warn"
"""
# The above has Python-ish "and/or" if left as-is. So we do it cleanly in JS instead:
insertion = r"""\1
  const modeKind = (mode === "SD") ? "ok" : "warn";

  const canFlashKnown = (pol.can_flash_here !== undefined && pol.can_flash_here !== null);
  const canFlashVal = (pol.can_flash_here === true);
  const canFlashKind = canFlashKnown ? (canFlashVal ? "ok" : "bad") : "warn";
  const canFlashTxt2 = canFlashKnown ? String(canFlashVal) : "unknown";

  const rootBlockedKnown = (pol.root_disk_blocked !== undefined && pol.root_disk_blocked !== null);
  const rootBlockedVal = (pol.root_disk_blocked === true);
  const rootBlockedKind = rootBlockedKnown ? (rootBlockedVal ? "ok" : "bad") : "warn";
  const rootBlockedTxt2 = rootBlockedKnown ? String(rootBlockedVal) : "unknown";

  const reqSDKnown = (pol.requires_sd_mode !== undefined && pol.requires_sd_mode !== null);
  const reqSDVal = (pol.requires_sd_mode === true);
  const reqSDKind = reqSDKnown ? ((reqSDVal && mode === "SD") ? "ok" : (reqSDVal ? "warn" : "bad")) : "warn";
  const reqSDTxt2 = reqSDKnown ? String(reqSDVal) : "unknown";

  const flashKind = flashEnabled ? "ok" : "bad";
  const armedKind = armed ? "ok" : "bad";

  const ready = !!(flashEnabled && canFlashVal && rootBlockedVal && (mode === "SD") && (eligible.length > 0));
  const readyKind = ready ? "ok" : "bad";
  const readyTxt  = ready ? "READY" : "NOT READY";
"""
must_replace(insert_after, insertion, "insert computed kinds after rootDisk", flags=0)

# 5) Patch headline pill rendering
must_replace(
    r"`<div class=\"mode\">Mode: <span class=\"pill\">\$\{esc\(mode\)\}<\/span><\/div>` \+",
    r"`<div class=\"mode\">Mode: ${pill(modeKind, mode)}</div>` +",
    "mode pill uses semantic class"
)

must_replace(
    r"`<div><b>Armed:<\/b> <span class=\"pill\">\$\{armed \? \"YES\" : \"no\"\}<\/span><\/div>` \+",
    r"`<div><b>Ready:</b> ${pill(readyKind, readyTxt)}</div>` +\n        `<div><b>Armed:</b> ${pill(armedKind, armed ? \"YES\" : \"no\")}</div>` +",
    "add READY indicator + armed pill class"
)

# 6) Patch policy rendering + box borders
must_replace(
    r"policy\.classList\.toggle\(\"warn\", !flashEnabled\);\n  policy\.innerHTML =",
    r"policy.classList.toggle(\"ok\", flashEnabled);\n  policy.classList.toggle(\"bad\", !flashEnabled);\n  policy.innerHTML =",
    "policy box border uses ok/bad"
)

must_replace(
    r"`<div class=\"small\">Flash policy: <span class=\"pill\">\$\{flashTxt\}<\/span><\/div>` \+",
    r"`<div class=\"small\">Flash policy: ${pill(flashKind, flashTxt)}</div>` +",
    "flash policy pill"
)
must_replace(
    r"`<div class=\"small\">Can flash here \(mode rules\): <span class=\"pill\">\$\{esc\(canFlashHere\)\}<\/span><\/div>` \+",
    r"`<div class=\"small\">Can flash here (mode rules): ${pill(canFlashKind, canFlashTxt2)}</div>` +",
    "can_flash_here pill"
)
must_replace(
    r"`<div class=\"small\">Write word: <span class=\"pill\">\$\{esc\(pol\.write_word \|\| \"\"\)\}<\/span> • Arm TTL: <span class=\"pill\">\$\{esc\(pol\.arm_ttl_seconds \?\? \"\"\)\}s<\/span><\/div>` \+",
    r"`<div class=\"small\">Write word: ${pill(\"info\", pol.write_word || \"\")} • Arm TTL: ${pill(\"info\", String(pol.arm_ttl_seconds ?? \"\") + \"s\")}</div>` +",
    "write_word + ttl pills"
)
must_replace(
    r"`<div class=\"small\">Root disk blocked: <span class=\"pill\">\$\{esc\(pol\.root_disk_blocked \?\? \"\"\)\}<\/span> • Requires SD mode: <span class=\"pill\">\$\{esc\(pol\.requires_sd_mode \?\? \"\"\)\}<\/span><\/div>`;",
    r"`<div class=\"small\">Root disk blocked: ${pill(rootBlockedKind, rootBlockedTxt2)} • Requires SD mode: ${pill(reqSDKind, reqSDTxt2)}</div>`;",
    "root_disk_blocked + requires_sd_mode pills"
)

# 7) Colorize targets box border + list items
# Add targetsBox border toggles right after we have eligible/blocked computed.
# We'll patch by inserting toggles right before targetsBox.innerHTML =
must_replace(
    r"(const blockedLines = blocked\.length[\s\S]*?\n\s*:\s*\"<div class='small'\>\(none\)<\/div>\";\n\n\s*)targetsBox\.innerHTML =",
    r"\1targetsBox.classList.toggle(\"ok\", eligible.length > 0);\n  targetsBox.classList.toggle(\"warn\", eligible.length === 0);\n\n  targetsBox.innerHTML =",
    "targetsBox border toggles based on eligible targets",
    flags=re.DOTALL
)

# Eligible list items include green cue
s = s.replace(
    'eligible.map(d => `<li>${fmtDisk(d)}</li>`).join("")',
    'eligible.map(d => `<li>✓ ${fmtDisk(d)} ${pill("ok","allowed")}</li>`).join("")'
)

# Blocked list items include red cue
s = s.replace(
    'return `<li>${fmtDisk(d)} <span class="pill">${esc(reason)}</span></li>`;',
    'return `<li>✗ ${fmtDisk(d)} ${pill("bad", reason)}</li>`;'
)

p.write_text(s, encoding="utf-8")
print("OK: patched static/index.html (JR_STATE_COLORS_V1)")

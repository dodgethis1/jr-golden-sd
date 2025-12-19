from pathlib import Path
import re, sys

p = Path("static/index.html")
s = p.read_text(encoding="utf-8", errors="replace")

MARK = "// JR_STATE_CUES_V1"
if MARK in s:
    print("OK: JR_STATE_CUES_V1 already present (no changes).")
    sys.exit(0)

# 1) Insert helper + applyStateClasses before the status timer (stable anchor)
anchor = re.search(r"\n\s*let\s+_statusTimer\s*=\s*null\s*;", s)
if not anchor:
    print("ERROR: couldn't find '_statusTimer' anchor (refusing).", file=sys.stderr)
    sys.exit(1)

insert = r"""
""" + MARK + r"""
  function _jrSetState(el, cls){
    if (!el) return;
    el.classList.remove("state-ok","state-warn","state-bad");
    if (cls) el.classList.add(cls);
  }

  function applyStateClasses(safety, disks, arm){
    const policy = (safety && safety.policy) ? safety.policy : {};
    const eligible = (safety && safety.eligible_targets) ? safety.eligible_targets : [];
    const armed = !!(arm && (arm.active || (arm.armed && arm.armed.active)));

    const flashEnabled = (policy.flash_enabled === true);
    const canFlashHere = (policy.can_flash_here === true);
    const rootBlocked  = (policy.root_disk_blocked !== false);

    // READY means: backend reachable (we’re in the success path), safety allows flashing here, root is blocked, and at least one eligible target exists.
    const ready = flashEnabled && canFlashHere && rootBlocked && (eligible.length > 0);

    // Apply “traffic light” to key panels
    _jrSetState(document.getElementById("headline"), ready ? "state-ok" : "state-warn");
    _jrSetState(document.getElementById("policy"),   canFlashHere ? (armed ? "state-warn" : "state-ok") : "state-bad");
    _jrSetState(document.getElementById("targetsBox"), (eligible.length > 0) ? "state-ok" : "state-warn");

    // Body-level hints for CSS
    try{
      document.body.classList.toggle("armed", armed);
      document.body.classList.add("backend-up");
      document.body.classList.remove("backend-down");
    }catch{}
  }
  // end JR_STATE_CUES_V1

"""

s = s[:anchor.start()] + "\n" + insert + s[anchor.start():]

# 2) After renderStatus(...) in refreshStatusOnce, call applyStateClasses (guarded)
pat = re.compile(r"(renderStatus\(\s*safety\s*,\s*disks\s*,\s*arm\s*\)\s*;\s*)")
if not pat.search(s):
    print("ERROR: couldn't find renderStatus(safety, disks, arm); (refusing).", file=sys.stderr)
    sys.exit(1)

s = pat.sub(r"\1\n      try { applyStateClasses(safety, disks, arm); } catch (e) { console.warn('applyStateClasses failed:', e); }\n", s, count=1)

# 3) In the catch block for refreshStatusOnce, mark backend-down (best-effort)
catch_pat = re.compile(r'(headline\.textContent\s*=\s*"Backend starting.*?";\s*)', re.S)
if catch_pat.search(s):
    s = catch_pat.sub(r"\1\n      try{ document.body.classList.add('backend-down'); document.body.classList.remove('backend-up'); }catch{}\n", s, count=1)

p.write_text(s, encoding="utf-8")
print("OK: injected state cues JS (JR_STATE_CUES_V1)")

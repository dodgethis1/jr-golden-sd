from __future__ import annotations
from pathlib import Path
from datetime import datetime
import re
import sys

MARKER = "JR_STATUS_PANEL_V1"

p = Path("static/index.html")
if not p.exists():
    print("ERROR: static/index.html not found", file=sys.stderr)
    sys.exit(1)

orig = p.read_text(encoding="utf-8")
if MARKER in orig:
    print("OK: patch already applied (marker present).")
    sys.exit(0)

s = orig

# --- 1) Replace fetch helper with retrying JSON fetch (tolerates brief empty responses) ---
pat = re.compile(
    r'async function j\s*\(\s*url\s*\)\s*\{\s*const r\s*=\s*await fetch\(url\);\s*return await r\.json\(\);\s*\}',
    re.M,
)
replacement = r'''async function j(url, opts={}){
  const retries = Number.isFinite(opts.retries) ? opts.retries : 12;
  const baseDelayMs = Number.isFinite(opts.delay_ms) ? opts.delay_ms : 250;

  let lastErr = null;
  for (let i=0; i<retries; i++){
    try{
      const r = await fetch(url, { cache: "no-store" });
      const txt = await r.text();

      if (!r.ok){
        const msg = (txt || "").trim().slice(0, 300);
        throw new Error(`HTTP ${r.status} ${r.statusText}${msg ? (": " + msg) : ""}`);
      }
      if (!txt || !txt.trim()){
        throw new Error("empty response");
      }
      return JSON.parse(txt);
    } catch (e){
      lastErr = e;
      const wait = Math.min(1200, baseDelayMs * (i + 1));
      await new Promise(res => setTimeout(res, wait));
    }
  }
  throw lastErr || new Error("request failed");
}'''
s2, n = pat.subn(replacement, s, count=1)
if n != 1:
    print("ERROR: could not replace async function j(url){...} (pattern mismatch).", file=sys.stderr)
    sys.exit(1)
s = s2

# --- 2) Insert Allowed Targets box under Policy box ---
needle = '<div class="box warn" id="policy">Loading policy…</div>'
if needle not in s:
    print("ERROR: could not find policy box to insert after.", file=sys.stderr)
    sys.exit(1)

s = s.replace(needle, needle + '\n\n  <div class="box" id="targetsBox">Loading disks…</div>\n', 1)

# --- 3) Inject status rendering + polling (read-only) before `let lastPlan = null;` ---
inject_point = "let lastPlan = null;"
if inject_point not in s:
    print("ERROR: could not find injection point (let lastPlan = null;).", file=sys.stderr)
    sys.exit(1)

inject_js = """// """ + MARKER + """: Mode banner + allowed targets panel + startup-retry
function esc(x){
  return String(x ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
}
function fmtDisk(d){
  const path = d.path || "";
  const size = d.size ? ` (${esc(d.size)})` : "";
  const tran = d.tran ? ` ${esc(d.tran)}` : "";
  const model = d.model ? ` • ${esc(d.model)}` : "";
  const serial = d.serial ? ` • ${esc(String(d.serial).slice(-8))}` : "";
  return `<span class="mono">${esc(path)}</span>${size}<span class="small"> • ${tran}${model}${serial}</span>`;
}
function renderStatus(safety, disks, armStatus){
  const headline = document.getElementById("headline");
  const policy = document.getElementById("policy");
  const targetsBox = document.getElementById("targetsBox");
  if (!headline || !policy || !targetsBox) return;

  const st = (safety && safety.state) || {};
  const pol = (safety && safety.policy) || {};
  const ver = (safety && safety.version) ? safety.version : "";

  const mode = st.mode || "unknown";
  const rootParent = st.root_parent || "";
  const rootSource = st.root_source || "";
  const rootDisk = rootParent ? ("/dev/" + rootParent) : "(unknown)";

  const armed = (armStatus && armStatus.active) || (safety && safety.armed && safety.armed.active) || false;
  const armedExpires = (safety && safety.armed && safety.armed.expires_at) ? tsToLocal(safety.armed.expires_at) : "";

  const flashEnabled = !!pol.flash_enabled;
  const flashTxt = flashEnabled ? "ENABLED" : "DISABLED";
  const canFlashHere = (pol.can_flash_here !== undefined) ? String(!!pol.can_flash_here) : "unknown";

  headline.innerHTML =
    `<div class="row" style="align-items:flex-start;">` +
      `<div style="flex: 2 1 360px;">` +
        `<div class="mode">Mode: <span class="pill">${esc(mode)}</span></div>` +
        `<div class="small">Root disk: <span class="mono">${esc(rootDisk)}</span> (root_source: <span class="mono">${esc(rootSource)}</span>)</div>` +
        `<div class="small">Version: <span class="mono">${esc(ver)}</span></div>` +
      `</div>` +
      `<div style="flex: 1 1 260px;">` +
        `<div><b>Armed:</b> <span class="pill">${armed ? "YES" : "no"}</span></div>` +
        `<div class="small">${(armed && armedExpires) ? ("Expires: " + esc(armedExpires)) : ""}</div>` +
      `</div>` +
    `</div>`;

  policy.classList.toggle("warn", !flashEnabled);
  policy.innerHTML =
    `<b>Policy:</b><br>` +
    `<div class="small">Flash policy: <span class="pill">${flashTxt}</span></div>` +
    `<div class="small">Can flash here (mode rules): <span class="pill">${esc(canFlashHere)}</span></div>` +
    `<div class="small">Write word: <span class="pill">${esc(pol.write_word || "")}</span> • Arm TTL: <span class="pill">${esc(pol.arm_ttl_seconds ?? "")}s</span></div>` +
    `<div class="small">Root disk blocked: <span class="pill">${esc(pol.root_disk_blocked ?? "")}</span> • Requires SD mode: <span class="pill">${esc(pol.requires_sd_mode ?? "")}</span></div>`;

  const disksList = (disks && disks.disks) ? disks.disks : [];
  const eligible = (safety && safety.eligible_targets) ? safety.eligible_targets : [];
  const eligiblePaths = new Set(eligible.map(x => x.path));

  const allowedLines = eligible.length
    ? ("<ul>" + eligible.map(d => `<li>${fmtDisk(d)}</li>`).join("") + "</ul>")
    : "<div class='small'>(none)</div>";

  const blocked = disksList.filter(d => !eligiblePaths.has(d.path));
  const blockedLines = blocked.length
    ? ("<ul>" + blocked.map(d => {
          const reason = d.is_root_disk ? "blocked: root disk" : "blocked: not eligible in current mode";
          return `<li>${fmtDisk(d)} <span class="pill">${esc(reason)}</span></li>`;
        }).join("") + "</ul>")
    : "<div class='small'>(none)</div>";

  targetsBox.innerHTML =
    `<b>Allowed targets (eligible now):</b>${allowedLines}` +
    `<hr style="margin:12px 0;">` +
    `<b>Detected disks (blocked):</b>${blockedLines}`;
}

let _statusTimer = null;
async function refreshStatusOnce(){
  try {
    await j("/api/health", {retries: 12, delay_ms: 250});
    const safety = await j("/api/safety", {retries: 12, delay_ms: 250});
    const disks  = await j("/api/disks",  {retries: 12, delay_ms: 250});
    const arm    = await j("/api/arm_status", {retries: 12, delay_ms: 250});
    renderStatus(safety, disks, arm);
  } catch (e) {
    const headline = document.getElementById("headline");
    const targetsBox = document.getElementById("targetsBox");
    if (headline) headline.textContent = "Backend starting… (retrying)";
    if (targetsBox) targetsBox.textContent = "Waiting for backend…";
  }
}
function startStatusPoll(){
  if (_statusTimer) return;
  refreshStatusOnce();
  _statusTimer = setInterval(refreshStatusOnce, 5000);
}
window.addEventListener("load", startStatusPoll);
// end """ + MARKER + """
"""

s = s.replace(inject_point, inject_js + "\n\n" + inject_point, 1)

# --- Backup + write ---
ts = datetime.now().strftime("%Y%m%d-%H%M%S")
bak = p.with_name(f"index.html.bak.{ts}")
bak.write_text(orig, encoding="utf-8")
p.write_text(s, encoding="utf-8")

print(f"OK: patched {p} (backup: {bak})")

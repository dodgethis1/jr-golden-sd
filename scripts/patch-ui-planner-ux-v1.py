from pathlib import Path
import re
import sys

p = Path("static/index.html")
s = p.read_text(encoding="utf-8")

if "JR_PLANNER_UX_V1" in s:
    print("OK: JR_PLANNER_UX_V1 already present (no changes).")
    sys.exit(0)

marker = "// end JR_STATUS_PANEL_V1"
if marker not in s:
    print("ERR: could not find status panel marker.")
    sys.exit(1)

planner_block = r'''
// JR_PLANNER_UX_V1: planner quality-of-life + guardrails (still NO new capabilities)
let _plannerTargetsSig = null;
let _plannerWriteWord = null;

function targetsSig(list){
  try { return (list || []).map(x => x.path).join("|"); } catch { return ""; }
}

function syncPlannerFromSafety(safety){
  const tSel = document.getElementById("target");
  const confirmEl = document.getElementById("confirmTarget");
  const wordEl = document.getElementById("word");

  const eligible = (safety && safety.eligible_targets) ? safety.eligible_targets : [];
  const pol = (safety && safety.policy) ? safety.policy : {};

  if (tSel){
    const sig = targetsSig(eligible);
    const prev = tSel.value || "";
    if (sig !== _plannerTargetsSig){
      tSel.innerHTML = "";
      eligible.forEach(d => {
        const label = `${d.path} (${d.size||""} ${d.model||""} ${d.serial||""})`;
        opt(tSel, d.path, label);
      });
      if (prev && eligible.some(d => d.path === prev)) tSel.value = prev;
      _plannerTargetsSig = sig;
    }
  }

  const curTarget = (tSel && tSel.value) ? tSel.value : "";
  if (confirmEl){
    confirmEl.placeholder = curTarget || confirmEl.placeholder || "";
    if (!confirmEl.value) confirmEl.value = curTarget || "";
  }

  if (wordEl){
    const ww = (pol && pol.write_word) ? String(pol.write_word) : "";
    wordEl.placeholder = ww || wordEl.placeholder || "";
    if (!wordEl.value && ww) wordEl.value = ww;
    _plannerWriteWord = ww || _plannerWriteWord;
  }
}

async function ensureTargetsLoaded(){
  const tSel = document.getElementById("target");
  if (tSel && tSel.options && tSel.options.length > 0) return;
  const safety = await j("/api/safety", {retries: 12, delay_ms: 250});
  syncPlannerFromSafety(safety);
}
// end JR_PLANNER_UX_V1
'''.strip("\n")

# Insert planner block right after status panel marker
s = s.replace(marker, marker + "\n\n" + planner_block + "\n", 1)

# Ensure refreshStatusOnce also keeps planner inputs synced
pat_refresh = r'renderStatus\(safety,\s*disks,\s*arm\);\s*\n'
if not re.search(pat_refresh, s):
    print("ERR: could not find renderStatus(safety, disks, arm) call to augment.")
    sys.exit(1)
s = re.sub(pat_refresh, 'renderStatus(safety, disks, arm);\n      syncPlannerFromSafety(safety);\n', s, count=1)

# Replace IIFE prelude that overwrites headline/policy + target population
pat_iife = r'\(\s*async\s*\(\s*\)\s*=>\s*\{\s*\n\s*const h = await j\("/api/health"\);\s*[\s\S]*?await loadOS\(""\);\s*\n'
m = re.search(pat_iife, s)
if not m:
    print("ERR: could not find the old IIFE prelude (health/policy/targets block).")
    sys.exit(1)

new_iife = r'''(async () => {
    // NOTE: headline/policy/allowed targets are handled by JR_STATUS_PANEL_V1.
    const u = await j("/api/urls", {retries: 12, delay_ms: 250});
    document.getElementById("urls").innerHTML =
      `<b>Open this from your phone/PC:</b>
       <ul>${(u.urls||[]).map(x => `<li><a href="${x}">${x}</a></li>`).join("")}</ul>`;
    const first = (u.urls && u.urls[0]) ? u.urls[0] : location.origin + "/";
    document.getElementById("qr").innerHTML =
      `<b>QR (scan me):</b><br><img src="/api/qr?u=${encodeURIComponent(first)}" alt="QR"><br><small><code>${first}</code></small>`;

    // Prime status + planner once early (window load will also start polling)
    try { await refreshStatusOnce(); } catch {}
    await ensureTargetsLoaded();

    const tSel = document.getElementById("target");
    const confirmEl = document.getElementById("confirmTarget");
    if (tSel && confirmEl){
      confirmEl.placeholder = tSel.value || confirmEl.placeholder || "";
      if (!confirmEl.value) confirmEl.value = tSel.value || "";
      tSel.addEventListener("change", () => {
        confirmEl.value = tSel.value;
        confirmEl.placeholder = tSel.value;
      });
    }

    await loadOS("");
'''
s = re.sub(pat_iife, new_iife, s, count=1)

# Replace plan button handler
pat_plan = r'document\.getElementById\("planBtn"\)\.addEventListener\("click",\s*async\s*\(\)\s*=>\s*\{\s*[\s\S]*?\n\s*\}\);\s*\n'
if not re.search(pat_plan, s):
    print("ERR: could not find planBtn handler.")
    sys.exit(1)

plan_handler = r'''document.getElementById("planBtn").addEventListener("click", async () => {
      const out = document.getElementById("planOut");
      if (out) out.innerHTML = `<span class="pill">working…</span>`;

      await ensureTargetsLoaded();

      const target = (tSel && tSel.value) ? tSel.value : "";
      const os_id = (document.getElementById("os").value || "").trim();

      if (!target || !os_id){
        if (out) out.innerHTML = `<b>Plan error:</b> <span class="pill">missing</span> select a target and OS.`;
        return;
      }

      let data = null;
      try{
        const r = await fetch("/api/plan_flash", {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({ target, os_id })
        });
        const txt = await r.text();
        data = txt ? JSON.parse(txt) : {};
        if (!r.ok || (data && data.ok === false)){
          const msg = (data && data.error) ? data.error : (txt || `HTTP ${r.status}`);
          throw new Error(msg);
        }
      } catch(e){
        if (out) out.innerHTML = `<b>Plan error:</b><pre>${esc(String(e))}</pre>`;
        return;
      }

      lastPlan = {
        target,
        os_id,
        plan_id: data.plan_id || null,
        expires_at: data.expires_at || null,
        data
      };

      const exp = data.expires_at ? tsToLocal(data.expires_at) : "";
      const pid = data.plan_id ? `<code>${esc(data.plan_id)}</code>` : `<span class="pill">missing plan_id</span>`;

      if (out) out.innerHTML =
        `<b>Plan:</b><br>` +
        `<div class="small">Target: <span class="mono">${esc(target)}</span> • OS: <span class="mono">${esc(os_id)}</span></div>` +
        `<div class="small">plan_id: ${pid}${exp ? (" • Expires: <span class='mono'>" + esc(exp) + "</span>") : ""}</div>` +
        `<div class="small">Next: ARM will send this plan_id automatically (still no writes).</div>` +
        `<pre>${esc(JSON.stringify(data, null, 2))}</pre>`;

      try { await refreshStatusOnce(); } catch {}
    });
'''
s = re.sub(pat_plan, plan_handler, s, count=1)

# Replace arm button handler (adds plan_id + guardrails)
pat_arm = r'document\.getElementById\("armBtn"\)\.addEventListener\("click",\s*async\s*\(\)\s*=>\s*\{\s*[\s\S]*?\n\s*\}\);\s*\n'
if not re.search(pat_arm, s):
    print("ERR: could not find armBtn handler.")
    sys.exit(1)

arm_handler = r'''document.getElementById("armBtn").addEventListener("click", async () => {
      const out = document.getElementById("armOut");
      if (out) out.innerHTML = `<span class="pill">working…</span>`;

      await ensureTargetsLoaded();

      const target = (tSel && tSel.value) ? tSel.value : "";
      const os_id = (document.getElementById("os").value || "").trim();
      const word = (document.getElementById("word").value || "");
      const confirm_target = (document.getElementById("confirmTarget").value || "").trim();
      const serial_suffix = (document.getElementById("serialSuffix").value || "");

      if (!lastPlan || !lastPlan.plan_id){
        if (out) out.innerHTML = `<b>ARM blocked:</b> <span class="pill">need plan</span><br><small>Click <b>Generate plan</b> first (plan_id is required).</small>`;
        return;
      }
      if (lastPlan.target !== target || lastPlan.os_id !== os_id){
        if (out) out.innerHTML =
          `<b>ARM blocked:</b> <span class="pill">plan mismatch</span><br>` +
          `<small>Selection changed since the last plan. Re-run <b>Generate plan</b>.</small>`;
        return;
      }
      if (confirm_target !== target){
        if (out) out.innerHTML =
          `<b>ARM blocked:</b> <span class="pill">confirm_target mismatch</span><br>` +
          `<small>Type the exact target: <span class="mono">${esc(target)}</span></small>`;
        return;
      }

      let data = null;
      try{
        const r = await fetch("/api/arm", {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify({
            target,
            os_id,
            plan_id: lastPlan.plan_id,
            word,
            confirm_target,
            serial_suffix
          })
        });
        const txt = await r.text();
        data = txt ? JSON.parse(txt) : {};
        if (!r.ok || (data && data.ok === false)){
          const msg = (data && data.error) ? data.error : (txt || `HTTP ${r.status}`);
          throw new Error(msg);
        }
      } catch(e){
        if (out) out.innerHTML = `<b>ARM error:</b><pre>${esc(String(e))}</pre>`;
        return;
      }

      if (out) out.innerHTML =
        `<b>ARM response:</b><br>` +
        `<div class="small">Target: <span class="mono">${esc(target)}</span> • plan_id: <code>${esc(lastPlan.plan_id)}</code></div>` +
        `<pre>${esc(JSON.stringify(data, null, 2))}</pre>`;

      try { await refreshStatusOnce(); } catch {}
    });
'''
s = re.sub(pat_arm, arm_handler, s, count=1)

# Replace disarm handler to also refresh status + better errors
pat_disarm = r'document\.getElementById\("disarmBtn"\)\.addEventListener\("click",\s*async\s*\(\)\s*=>\s*\{\s*[\s\S]*?\n\s*\}\);\s*\n'
if not re.search(pat_disarm, s):
    print("ERR: could not find disarmBtn handler.")
    sys.exit(1)

disarm_handler = r'''document.getElementById("disarmBtn").addEventListener("click", async () => {
      const out = document.getElementById("armOut");
      if (out) out.innerHTML = `<span class="pill">working…</span>`;
      try{
        const r = await fetch("/api/disarm", { method: "POST" });
        const txt = await r.text();
        const data = txt ? JSON.parse(txt) : {};
        if (!r.ok || (data && data.ok === false)){
          const msg = (data && data.error) ? data.error : (txt || `HTTP ${r.status}`);
          throw new Error(msg);
        }
        if (out) out.innerHTML = `<b>DISARM response:</b><pre>${esc(JSON.stringify(data, null, 2))}</pre>`;
      } catch(e){
        if (out) out.innerHTML = `<b>DISARM error:</b><pre>${esc(String(e))}</pre>`;
      }
      try { await refreshStatusOnce(); } catch {}
    });
'''
s = re.sub(pat_disarm, disarm_handler, s, count=1)

p.write_text(s, encoding="utf-8")
print("OK: patched static/index.html (JR_PLANNER_UX_V1)")

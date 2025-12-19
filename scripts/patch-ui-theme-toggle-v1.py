from pathlib import Path
import re
import time
import sys

p = Path("static/index.html")
text = p.read_text(encoding="utf-8")

stamp = time.strftime("%Y%m%d-%H%M%S")
bak = p.with_name(f"index.html.bak.{stamp}")
bak.write_text(text, encoding="utf-8")

NEW_STYLE = r"""<style>
  :root{
    --bg: #f6f7f9;
    --panel: #ffffff;
    --text: #111827;
    --muted: rgba(17,24,39,.72);
    --border: rgba(17,24,39,.18);
    --pill: rgba(17,24,39,.06);
    --mono-bg: rgba(17,24,39,.06);
    --warn: #b00020;
    --ok: #0a7b34;
    --link: #0b63ce;
    --shadow: 0 1px 2px rgba(0,0,0,.06);
  }

  /* Default to system dark mode */
  @media (prefers-color-scheme: dark){
    :root{
      --bg: #0b1220;
      --panel: #0f1b33;
      --text: #e5e7eb;
      --muted: rgba(229,231,235,.72);
      --border: rgba(229,231,235,.18);
      --pill: rgba(229,231,235,.08);
      --mono-bg: rgba(229,231,235,.08);
      --warn: #ff4d6d;
      --ok: #2bd576;
      --link: #7ab7ff;
      --shadow: 0 1px 2px rgba(0,0,0,.35);
    }
  }

  /* Manual overrides (button cycles these) */
  body.theme-light{
    --bg: #f6f7f9;
    --panel: #ffffff;
    --text: #111827;
    --muted: rgba(17,24,39,.72);
    --border: rgba(17,24,39,.18);
    --pill: rgba(17,24,39,.06);
    --mono-bg: rgba(17,24,39,.06);
    --warn: #b00020;
    --ok: #0a7b34;
    --link: #0b63ce;
    --shadow: 0 1px 2px rgba(0,0,0,.06);
  }
  body.theme-dark{
    --bg: #0b1220;
    --panel: #0f1b33;
    --text: #e5e7eb;
    --muted: rgba(229,231,235,.72);
    --border: rgba(229,231,235,.18);
    --pill: rgba(229,231,235,.08);
    --mono-bg: rgba(229,231,235,.08);
    --warn: #ff4d6d;
    --ok: #2bd576;
    --link: #7ab7ff;
    --shadow: 0 1px 2px rgba(0,0,0,.35);
  }

  body{
    font-family: system-ui, sans-serif;
    padding: 16px;
    background: var(--bg);
    color: var(--text);
  }

  a{ color: var(--link); }
  a:visited{ color: var(--link); }

  .topbar{
    display:flex;
    gap:12px;
    align-items:center;
    justify-content:space-between;
    margin-bottom: 8px;
  }
  .topbar h2{ margin:0; }

  .box{
    border: 1px solid var(--border);
    background: var(--panel);
    box-shadow: var(--shadow);
    border-radius: 12px;
    padding: 12px;
    margin: 12px 0;
  }
  .warn{
    border-color: var(--warn);
    box-shadow: 0 0 0 1px rgba(255,0,0,.08), var(--shadow);
  }

  .mode{ font-size: 22px; font-weight: 800; }

  .pill{
    display:inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    background: var(--pill);
    border: 1px solid var(--border);
  }

  code, pre{
    background: var(--mono-bg);
    padding: 8px;
    border-radius: 10px;
    overflow:auto;
  }

  input, select, button{
    font-size: 16px;
    padding: 8px;
    color: var(--text);
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
  }
  button{ cursor: pointer; }
  button:hover{ filter: brightness(1.02); }

  .grid{ display: grid; grid-template-columns: 1fr; gap: 12px; }
  @media (min-width: 900px){ .grid{ grid-template-columns: 1fr 1fr; } }

  .row{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
  .row > *{ flex: 1 1 220px; }

  .mono{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
  .log{ max-height: 340px; overflow:auto; white-space: pre-wrap; word-break: break-word; }
  .small{ font-size: 12px; opacity: 0.85; color: var(--muted); }
</style>"""

THEME_JS = r"""// JR_THEME_TOGGLE_V1: Auto/Dark/Light toggle (localStorage)
(function(){
  const KEY = "jr_theme_mode"; // "", "dark", "light"
  const BTN_ID = "themeBtn";

  function cap(s){ return s ? (s[0].toUpperCase() + s.slice(1)) : s; }

  function safeGet(){
    try { return (localStorage.getItem(KEY) || "").trim(); } catch { return ""; }
  }
  function safeSet(v){
    try {
      if (v) localStorage.setItem(KEY, v);
      else localStorage.removeItem(KEY);
    } catch {}
  }

  function apply(mode){
    document.body.classList.remove("theme-light","theme-dark");
    if (mode === "dark") document.body.classList.add("theme-dark");
    if (mode === "light") document.body.classList.add("theme-light");
    const b = document.getElementById(BTN_ID);
    if (b) b.textContent = "Theme: " + (mode ? cap(mode) : "Auto");
  }

  function next(mode){
    // Auto -> Dark -> Light -> Auto
    if (!mode) return "dark";
    if (mode === "dark") return "light";
    return "";
  }

  window.addEventListener("load", () => {
    const cur = safeGet();
    apply(cur);
    const b = document.getElementById(BTN_ID);
    if (b){
      b.addEventListener("click", () => {
        const n = next(safeGet());
        safeSet(n);
        apply(n);
      });
    }
  });
})();"""

# 1) Replace the <style>...</style> block (first one only)
if "<style>" not in text:
  print("ERROR: no <style> block found in static/index.html", file=sys.stderr)
  sys.exit(1)

text2 = re.sub(r"<style>.*?</style>", NEW_STYLE, text, count=1, flags=re.S)
if text2 == text:
  print("ERROR: failed to replace <style> block", file=sys.stderr)
  sys.exit(1)

# 2) Replace the plain h2 with a topbar + theme button (id stable)
if "themeBtn" not in text2:
  text2 = text2.replace(
    "<h2>JR Golden SD</h2>",
    '<div class="topbar" data-jr="JR_THEME_TOGGLE_V1"><h2>JR Golden SD</h2><button id="themeBtn" class="pill" title="Cycle Auto/Dark/Light">Theme: Auto</button></div>',
    1
  )

# 3) Inject theme JS right after <script> (only once)
if "JR_THEME_TOGGLE_V1" not in text2:
  m = re.search(r"<script>\s*", text2)
  if not m:
    print("ERROR: no <script> tag found", file=sys.stderr)
    sys.exit(1)
  insert_at = m.end()
  text2 = text2[:insert_at] + "\n" + THEME_JS + "\n\n" + text2[insert_at:]

p.write_text(text2, encoding="utf-8")
print(f"OK: patched {p} (backup: {bak})")

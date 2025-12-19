from pathlib import Path
import re
import sys

p = Path("static/index.html")
s = p.read_text(encoding="utf-8")

if "JR_THEME_TOGGLE_V1" in s:
    print("OK: theme toggle already present")
    sys.exit(0)

# Replace the entire <style>...</style> block with a themed version.
style_re = re.compile(r"<style>\s*.*?\s*</style>", re.DOTALL | re.IGNORECASE)
new_style = """<style>
  /* JR_THEME_TOGGLE_V1: light/dark + a little color */
  html { color-scheme: light dark; }

  :root{
    --bg: #ffffff;
    --fg: #0b1220;
    --muted: #4b5563;
    --box: #ffffff;
    --border: #cfd6de;

    --pill-bg: #eef2f6;
    --pill-fg: #0b1220;

    --pre-bg: #eef2f6;

    --link: #1d4ed8;
    --accent: #16a34a;
    --warn: #b00020;

    --btn-bg: #0f172a;
    --btn-fg: #ffffff;
    --btn-border: #0f172a;
  }

  /* If user doesn't choose, follow system preference */
  @media (prefers-color-scheme: dark){
    :root:not([data-theme]){
      --bg: #0b0f14;
      --fg: #e6edf3;
      --muted: #9aa4ad;
      --box: #111826;
      --border: #2b3442;

      --pill-bg: #1f2a37;
      --pill-fg: #e6edf3;

      --pre-bg: #0f172a;

      --link: #7aa2ff;
      --accent: #22c55e;
      --warn: #ff5566;

      --btn-bg: #1f2a37;
      --btn-fg: #e6edf3;
      --btn-border: #2b3442;
    }
  }

  /* Explicit override */
  :root[data-theme="dark"]{
    --bg: #0b0f14;
    --fg: #e6edf3;
    --muted: #9aa4ad;
    --box: #111826;
    --border: #2b3442;

    --pill-bg: #1f2a37;
    --pill-fg: #e6edf3;

    --pre-bg: #0f172a;

    --link: #7aa2ff;
    --accent: #22c55e;
    --warn: #ff5566;

    --btn-bg: #1f2a37;
    --btn-fg: #e6edf3;
    --btn-border: #2b3442;
  }

  body {
    font-family: system-ui, sans-serif;
    padding: 16px;
    background: var(--bg);
    color: var(--fg);
  }

  a { color: var(--link); }

  .box {
    border: 1px solid var(--border);
    background: var(--box);
    border-radius: 12px;
    padding: 12px;
    margin: 12px 0;
    box-shadow: 0 1px 8px rgba(0,0,0,0.06);
  }

  .warn { border-color: var(--warn); }

  .mode { font-size: 22px; font-weight: 800; }

  .pill {
    display:inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    background: var(--pill-bg);
    color: var(--pill-fg);
    border: 1px solid rgba(0,0,0,0.06);
  }

  code, pre {
    background: var(--pre-bg);
    padding: 8px;
    border-radius: 10px;
    overflow:auto;
  }

  input, select, button { font-size: 16px; padding: 8px; }
  button {
    cursor: pointer;
    background: var(--btn-bg);
    color: var(--btn-fg);
    border: 1px solid var(--btn-border);
    border-radius: 10px;
  }
  button:hover { filter: brightness(1.05); }

  .grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
  @media (min-width: 900px) { .grid { grid-template-columns: 1fr 1fr; } }

  .row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
  .row > * { flex: 1 1 220px; }

  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
  .log { max-height: 340px; overflow:auto; white-space: pre-wrap; word-break: break-word; }
  .small { font-size: 12px; opacity: 0.85; color: var(--muted); }
</style>"""

if not style_re.search(s):
    print("ERROR: couldn't find <style> block to replace", file=sys.stderr)
    sys.exit(1)

s = style_re.sub(new_style, s, count=1)

# Replace the plain <h2> with a header row containing a theme button.
s = s.replace(
    "<h2>JR Golden SD</h2>",
    '<div class="row" style="justify-content:space-between;align-items:center;">'
    '<h2 style="margin:0;flex: 1 1 auto;">JR Golden SD</h2>'
    '<button id="themeBtn" class="pill" style="flex: 0 0 auto; border:1px solid rgba(0,0,0,0.12);">'
    'Theme: auto</button>'
    "</div>"
)

# Inject theme JS right after <script>
marker = "<script>"
if marker not in s:
    print("ERROR: couldn't find <script> tag", file=sys.stderr)
    sys.exit(1)

theme_js = """<script>
// JR_THEME_TOGGLE_V1: auto/light/dark toggle (persists in localStorage)
(function(){
  try{
    const k="jr_theme";
    const root=document.documentElement;
    const saved=localStorage.getItem(k);
    if (saved==="dark" || saved==="light"){
      root.setAttribute("data-theme", saved);
    }
  }catch{}
})();

function initThemeBtn(){
  const btn = document.getElementById("themeBtn");
  if (!btn) return;
  const k="jr_theme";
  const root=document.documentElement;

  function cur(){ return root.getAttribute("data-theme") || ""; }
  function label(){
    const v = cur();
    btn.textContent = v ? ("Theme: " + v) : "Theme: auto";
  }

  btn.addEventListener("click", () => {
    const v = cur();
    const next = (v === "dark") ? "light" : (v === "light") ? "" : "dark";
    if (!next){
      root.removeAttribute("data-theme");
      try{ localStorage.removeItem(k); }catch{}
    } else {
      root.setAttribute("data-theme", next);
      try{ localStorage.setItem(k, next); }catch{}
    }
    label();
  });

  label();
}
window.addEventListener("load", initThemeBtn);

"""

s = s.replace(marker, theme_js, 1)

p.write_text(s, encoding="utf-8")
print("OK: patched static/index.html (theme toggle + dark mode)")

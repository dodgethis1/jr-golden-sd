from pathlib import Path
import re, sys

p = Path("static/index.html")
s = p.read_text(encoding="utf-8", errors="replace")

MARK = "/* JR_THEME_V1 */"
if MARK in s:
    print("OK: JR_THEME_V1 already present (no changes).")
    sys.exit(0)

m = re.search(r"</style\s*>", s, flags=re.I)
if not m:
    print("ERROR: couldn't find </style> in static/index.html (refusing).", file=sys.stderr)
    sys.exit(1)

css = r"""
  /* JR_THEME_V1: Dark mode + state cue styling (CSS-only, safe) */
  :root{
    --jr-bg: #f6f7f9;
    --jr-panel: #ffffff;
    --jr-text: #111827;
    --jr-muted: rgba(17,24,39,.72);
    --jr-border: rgba(17,24,39,.18);
    --jr-pill: rgba(17,24,39,.06);
    --jr-mono: rgba(17,24,39,.06);
    --jr-shadow: 0 1px 2px rgba(0,0,0,.06);

    --jr-ok: #16a34a;
    --jr-warn: #f59e0b;
    --jr-bad: #ef4444;
    --jr-info: #2563eb;
  }

  @media (prefers-color-scheme: dark){
    :root{
      --jr-bg: #0b1220;
      --jr-panel: #0f1b33;
      --jr-text: #e5e7eb;
      --jr-muted: rgba(229,231,235,.72);
      --jr-border: rgba(229,231,235,.18);
      --jr-pill: rgba(229,231,235,.08);
      --jr-mono: rgba(229,231,235,.08);
      --jr-shadow: 0 1px 2px rgba(0,0,0,.35);

      --jr-ok: #2bd576;
      --jr-warn: #ffcc66;
      --jr-bad: #ff4d6d;
      --jr-info: #7ab7ff;
    }
  }

  body{ background: var(--jr-bg) !important; color: var(--jr-text) !important; }
  a{ color: var(--jr-info) !important; }

  /* Try to theme the common “panel/card” boxes without knowing every class name */
  .card, .panel, .box, .section,
  #headline, #policy, #targetsBox, #urls, #qr{
    background: var(--jr-panel) !important;
    color: var(--jr-text) !important;
    border-color: var(--jr-border) !important;
    box-shadow: var(--jr-shadow) !important;
  }

  pre, code, .mono{
    background: var(--jr-mono) !important;
    color: var(--jr-text) !important;
    border-color: var(--jr-border) !important;
  }

  input, select, button, textarea{
    background: var(--jr-panel) !important;
    color: var(--jr-text) !important;
    border-color: var(--jr-border) !important;
  }

  .pill{
    background: var(--jr-pill) !important;
    color: var(--jr-text) !important;
    border: 1px solid var(--jr-border) !important;
  }

  /* These are “traffic light” classes we’ll hook up in Step 2 */
  .state-ok{ border-left: 6px solid var(--jr-ok) !important; }
  .state-warn{ border-left: 6px solid var(--jr-warn) !important; }
  .state-bad{ border-left: 6px solid var(--jr-bad) !important; }

  /* Optional: make backend-down feel obvious even if content is stale */
  body.backend-down #headline{ outline: 2px solid var(--jr-bad); outline-offset: 2px; }
  body.backend-up #headline{ outline: 2px solid var(--jr-ok); outline-offset: 2px; }
  /* end JR_THEME_V1 */
"""

s2 = s[:m.start()] + "\n" + MARK + "\n" + css + "\n" + s[m.start():]
p.write_text(s2, encoding="utf-8")
print("OK: injected JR_THEME_V1 into static/index.html")

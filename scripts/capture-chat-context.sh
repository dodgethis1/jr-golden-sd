#!/usr/bin/env bash
set -euo pipefail

cd /opt/jr-pi-toolkit/golden-sd || exit 1

label="${1:-context}"
label="$(printf '%s' "$label" | tr -cs 'A-Za-z0-9._-' '_' | sed 's/^_\\+//; s/_\\+$//')"

ts="$(date +%Y%m%d-%H%M%S)"
out="docs/chat-context/captures/${ts}-${label}.md"

printf '<!-- captured=%s host=%s -->\n' "$(date -Is)" "$(hostname)" > "$out"

echo "Paste the ChatGPT first context post now. End with Ctrl-D." >&2
cat >> "$out"

echo "SAVED: $out"

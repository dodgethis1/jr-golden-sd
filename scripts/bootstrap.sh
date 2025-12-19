#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.." || exit 1

echo "=== JR Golden SD: bootstrap ==="
echo "repo: $(pwd)"

# Pick python
PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "ERROR: python not found: $PY" >&2
  exit 1
fi

echo "python: $($PY -V 2>&1)"

# Create venv if missing
if [ ! -x ".venv/bin/python" ]; then
  echo "Creating venv: .venv"
  "$PY" -m venv .venv
fi

echo "Upgrading pip/setuptools/wheel..."
.venv/bin/python -m pip install -U pip setuptools wheel >/dev/null

# Install deps
if [ -f "requirements.txt" ]; then
  echo "Installing requirements.txt..."
  .venv/bin/python -m pip install -r requirements.txt
elif [ -f "pyproject.toml" ]; then
  echo "Installing from pyproject.toml (editable)..."
  .venv/bin/python -m pip install -e .
else
  echo "ERROR: no requirements.txt or pyproject.toml found. Don't know what to install." >&2
  exit 1
fi

echo
echo "=== sanity import ==="
.venv/bin/python - <<'PY'
import flask
print("OK: flask import:", flask.__version__)
PY

echo
echo "OK: bootstrap complete"

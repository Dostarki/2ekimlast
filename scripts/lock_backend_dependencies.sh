#!/usr/bin/env bash
# Resolve only application dependencies, never the shared development environment.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
venv="$(mktemp -d)"
trap 'rm -rf "$venv"' EXIT
python3 -m venv "$venv"
"$venv/bin/python" -m pip install --only-binary=:all: \
  -c "$root/backend/requirements.txt" -r "$root/backend/requirements.in"
"$venv/bin/python" -m pip check
"$venv/bin/python" -m pip freeze > "$root/backend/requirements.txt"
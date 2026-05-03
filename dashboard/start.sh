#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

_pick_python() {
  if [[ -n "${PYTHON_BIN:-}" ]]; then
    printf '%s' "$PYTHON_BIN"
    return 0
  fi
  if [[ -x "$ROOT/hermes-agent/.venv/bin/python3" ]]; then
    printf '%s' "$ROOT/hermes-agent/.venv/bin/python3"
    return 0
  fi
  if [[ -x "$ROOT/.venv/bin/python3" ]]; then
    printf '%s' "$ROOT/.venv/bin/python3"
    return 0
  fi
  command -v python3
}

PYTHON_BIN="$(_pick_python)"

"$PYTHON_BIN" -m pip install -r "$ROOT/requirements.txt"
exec "$PYTHON_BIN" "$ROOT/dashboard/api.py"

#!/usr/bin/env bash
set -euo pipefail

cd /mnt/c/Users/ASUS/HermesVolta
PYTHON_BIN="${PYTHON_BIN:-/mnt/c/Users/ASUS/HermesVolta/hermes-agent/.venv/bin/python3}"

"$PYTHON_BIN" -m pip install fastapi uvicorn python-multipart
exec "$PYTHON_BIN" dashboard/api.py

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
OS_NAME="$(uname -s)"

echo "Installing Hermes Volta dependencies from: $ROOT"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is required. Install Python 3 and re-run this script." >&2
  exit 1
fi

install_linux_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    echo "Detected Linux with apt. Installing ngspice and KiCad..."
    sudo apt-get update
    sudo apt-get install -y ngspice libngspice0 kicad
  else
    echo "Warning: apt-get not found. Install ngspice, libngspice, and kicad manually." >&2
  fi
}

install_macos_packages() {
  if command -v brew >/dev/null 2>&1; then
    echo "Detected macOS with Homebrew. Installing ngspice and KiCad..."
    brew update
    brew install ngspice kicad
  else
    echo "Warning: Homebrew not found. Install Homebrew, ngspice, and KiCad manually." >&2
  fi
}

case "$OS_NAME" in
  Linux)
    install_linux_packages
    ;;
  Darwin)
    install_macos_packages
    ;;
  *)
    echo "Warning: unsupported OS '$OS_NAME'. Install ngspice and KiCad manually." >&2
    ;;
esac

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip setuptools wheel
python -m pip install "numpy<2" matplotlib PySpice skidl requests

mkdir -p outputs
mkdir -p "$HOME/.hermes/skills"
rm -rf "$HOME/.hermes/skills/volta"
cp -R skills/volta "$HOME/.hermes/skills/volta"

chmod +x skills/volta/scripts/install_deps.sh

cat <<'MSG'

Hermes Volta install complete.

Next steps:
  1. Activate the environment:
     source .venv/bin/activate
  2. Verify Ngspice/PySpice:
     python3 -c "from PySpice.Spice.Netlist import Circuit; print('PySpice OK')"
  3. Run a Volta pipeline smoke test:
     python3 - <<'PY'
from sim.faraday_pipeline import run
print(run("RC_LOWPASS", R=1600, C=1e-7, supply_v=5.0, L=1e-2, fc=1000, description="install smoke test"))
PY

Skill copied to ~/.hermes/skills/volta
MSG

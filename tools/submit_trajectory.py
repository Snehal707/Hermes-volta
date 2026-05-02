"""Submit or bundle Hermes Volta ShareGPT trajectory files."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path("/mnt/c/Users/ASUS/HermesVolta")
TRAJECTORY_DIR = PROJECT_ROOT / "outputs" / "trajectories"
BUNDLE_PATH = PROJECT_ROOT / "outputs" / "trajectories_bundle.jsonl"


def trajectory_files() -> list[Path]:
    if not TRAJECTORY_DIR.exists():
        return []
    return sorted(TRAJECTORY_DIR.glob("*.json"))


def write_bundle(files: list[Path], bundle_path: Path = BUNDLE_PATH) -> Path:
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    with bundle_path.open("w", encoding="utf-8") as out:
        for path in files:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")
    return bundle_path


def submit_to_hermes(files: list[Path]) -> bool:
    hermes = shutil.which("hermes")
    if not hermes or not files:
        return False
    command = [hermes, "rl", "submit", *[str(path) for path in files]]
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError:
        return False
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip())
    return completed.returncode == 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Submit or bundle Hermes Volta RL trajectory files.")
    parser.add_argument("--bundle-only", action="store_true", help="Skip hermes rl submit and only write JSONL bundle.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    files = trajectory_files()
    if not files:
        print(f"No trajectory files found in {TRAJECTORY_DIR}")
        return 0
    submitted = False if args.bundle_only else submit_to_hermes(files)
    bundle = write_bundle(files)
    if submitted:
        print(f"Submitted {len(files)} trajectory files via hermes rl submit.")
    else:
        print(f"Saved {len(files)} trajectories to {bundle} for manual submission.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Post Hermes Volta design summaries to an optional webhook."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

_REPO_BOOT = Path(__file__).resolve().parents[1]
if str(_REPO_BOOT) not in sys.path:
    sys.path.insert(0, str(_REPO_BOOT))

from sim.volta_paths import project_root_path

PROJECT_ROOT = project_root_path()
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
ENV_PATHS = [PROJECT_ROOT / ".env", Path.home() / ".hermes" / ".env"]
LOG_PATH = OUTPUTS_DIR / "webhook.log"


def _load_env() -> None:
    for path in ENV_PATHS:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _log(message: str) -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")


def _extract(pattern: str, text: str, default: str = "") -> str:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else default


def _parse_component(text: str, ref: str) -> str:
    match = re.search(rf"^\s*{re.escape(ref)}\s+\|\s*([^|]+)\|", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def parse_report(report_path: Path) -> dict[str, Any]:
    text = report_path.read_text(encoding="utf-8")
    output_dir = str(report_path.parent)
    circuit_type = _extract(r"^Circuit type:\s*(.+)$", text)
    target_fc = _extract(r"^\s*Target fc:\s*(.+?)\s*Hz$", text)
    actual_fc = _extract(r"^\s*Actual fc:\s*(.+?)\s*Hz$", text)
    error = _extract(r"^\s*Error:\s*(.+?)%$", text)
    status = _extract(r"^\s*Result:\s*(.+)$", text)
    return {
        "circuit_type": circuit_type,
        "fc": target_fc,
        "actual_fc": actual_fc,
        "error": error,
        "R": _parse_component(text, "R1"),
        "C": _parse_component(text, "C1"),
        "status": status,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "output_dir": output_dir,
        "report": str(report_path),
    }


def post_webhook(payload: dict[str, Any], url: str) -> tuple[int, str]:
    request = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body[:500]


def resolve_report_path(design_folder: str | None) -> Path:
    if design_folder:
        path = Path(design_folder)
        if not path.is_absolute():
            if path.parts and path.parts[0] == "outputs":
                path = PROJECT_ROOT / path
            else:
                path = OUTPUTS_DIR / path
        return path / "cutoff_report.txt" if path.is_dir() else path
    return OUTPUTS_DIR / "cutoff_report.txt"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send a Hermes Volta design report to VOLTA_WEBHOOK_URL.")
    parser.add_argument("design_folder", nargs="?", help="Design output folder or cutoff_report.txt path.")
    args = parser.parse_args(argv)

    _load_env()
    url = os.environ.get("VOLTA_WEBHOOK_URL", "").strip()
    if not url:
        return 0

    report_path = resolve_report_path(args.design_folder)
    if not report_path.exists():
        _log(f"skip missing_report report={report_path}")
        return 0

    try:
        payload = parse_report(report_path)
        status, body = post_webhook(payload, url)
        _log(f"posted status={status} circuit={payload.get('circuit_type')} fc={payload.get('fc')} body={body!r}")
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
        _log(f"error {type(exc).__name__}: {exc}")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

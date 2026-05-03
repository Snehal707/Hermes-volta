"""Portable project root and optional Hermes-Agent venv paths for Hermes Volta.

Resolve the repo root with (in order) ``VOLTA_PROJECT_ROOT``, ``HERMES_VOLTA_ROOT``,
or by inferring ``<repo>/sim/volta_paths.py`` → repo parent.

Hermes-Agent checkout site-packages override: ``VOLTA_SITE_PACKAGES``.
Python executable override: ``VOLTA_PYTHON``, ``HERMES_AGENT_PYTHON``.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def project_root_path() -> Path:
    """Absolute path to the Hermes Volta repository root."""
    for key in ("VOLTA_PROJECT_ROOT", "HERMES_VOLTA_ROOT"):
        raw = os.environ.get(key)
        if raw:
            return Path(raw).expanduser().resolve()
    here = Path(__file__).resolve()
    # sim/volta_paths.py → parents[1] == repo root
    return here.parent.parent


def optional_hermes_agent_venv_site_packages(root: Path | None = None) -> Path | None:
    """Return ``hermes-agent/.venv`` site-packages if present."""
    env = os.environ.get("VOLTA_SITE_PACKAGES") or os.environ.get("VOLTA_VENV_SITE_PACKAGES")
    if env:
        p = Path(env).expanduser().resolve()
        return p if p.is_dir() else None
    base = root or project_root_path()
    venv = base / "hermes-agent" / ".venv"
    if not venv.is_dir():
        return None
    win_sp = venv / "Lib" / "site-packages"
    if win_sp.is_dir():
        return win_sp
    lib = venv / "lib"
    if lib.is_dir():
        # Prefer newer pythonX.Y names over plain pythonXY.
        candidates = sorted(lib.glob("python*"), key=lambda p: p.name, reverse=True)
        for pydir in candidates:
            cand = pydir / "site-packages"
            if cand.is_dir():
                return cand
    return None


def prepend_sim_import_helpers(root: Path | None = None) -> Path:
    """Prepend bundled venv site-packages (if any) and project root to ``sys.path``."""
    repo = root or project_root_path()
    sp = optional_hermes_agent_venv_site_packages(repo)
    if sp is not None:
        ssp = str(sp)
        if ssp not in sys.path:
            sys.path.insert(0, ssp)
    srepo = str(repo)
    if srepo not in sys.path:
        sys.path.insert(0, srepo)
    return repo


def hermes_agent_venv_python(repo: Path | None = None) -> Path | None:
    """Path to ``hermes-agent/.venv`` interpreter if it exists."""
    base = repo or project_root_path()
    venv = base / "hermes-agent" / ".venv"
    if not venv.is_dir():
        return None
    win = venv / "Scripts" / "python.exe"
    if win.is_file():
        return win.resolve()
    for name in ("python3", "python"):
        ux = venv / "bin" / name
        if ux.is_file():
            return ux.resolve()
    return None


def project_local_venv_python(repo: Path | None = None) -> Path | None:
    """Path to repo-local ``.venv`` (from install_deps.sh) if present."""
    base = repo or project_root_path()
    win = base / ".venv" / "Scripts" / "python.exe"
    if win.is_file():
        return win.resolve()
    ux = base / ".venv" / "bin" / "python3"
    if ux.is_file():
        return ux.resolve()
    ux_py = base / ".venv" / "bin" / "python"
    if ux_py.is_file():
        return ux_py.resolve()
    return None


def preferred_python_exe(repo: Path | None = None) -> Path:
    """Interpreter to run Volta pipelines: env, hermes-agent venv, .venv, or current."""
    for key in ("VOLTA_PYTHON", "HERMES_AGENT_PYTHON"):
        raw = os.environ.get(key)
        if raw:
            p = Path(raw).expanduser().resolve()
            if p.is_file():
                return p
    base = repo or project_root_path()
    bundled = hermes_agent_venv_python(base)
    if bundled is not None:
        return bundled
    local = project_local_venv_python(base)
    if local is not None:
        return local
    return Path(sys.executable).resolve()

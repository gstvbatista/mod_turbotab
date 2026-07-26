"""
Pacote principal do projeto Mod TurboTables em Python.
"""

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _fallback_version() -> str:
    """Read version straight from pyproject.toml for uninstalled checkouts."""
    pyproject = Path(__file__).resolve().parent / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return "0.0.0"
    match = re.search(r'(?m)^version = "([^"]+)"', text)
    return match.group(1) if match else "0.0.0"


try:
    __version__ = version("turbotab")
except PackageNotFoundError:
    __version__ = _fallback_version()

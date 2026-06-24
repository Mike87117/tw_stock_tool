"""Compatibility namespace package for local src-layout execution.

This lets ``import tw_stock_tool...`` work from the repository root without
requiring ``pip install -e .`` first.
"""

from __future__ import annotations

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
_SRC_PACKAGE_DIR = _PACKAGE_DIR.parent / "src" / "tw_stock_tool"

if _SRC_PACKAGE_DIR.exists():
    __path__.append(str(_SRC_PACKAGE_DIR))

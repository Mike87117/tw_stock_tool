"""Shared subprocess helper with one explicit, locale-independent IO contract.

Child processes are always decoded as strict UTF-8 and are told to emit UTF-8,
so Chinese CLI output is byte-identical on Windows (cp950/cp1252 consoles) and
on Linux. Decoding is intentionally strict: a mojibake or malformed stream is a
real defect and must fail loudly instead of being silently repaired.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

CHILD_ENCODING = "utf-8"


def run_repo_python(
    *args: str,
    extra_pythonpath: tuple[str | Path, ...] = (),
    include_repository_root: bool = True,
    suppress_bytecode: bool = True,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    python_path = [str(path) for path in extra_pythonpath]
    if include_repository_root:
        python_path.append(str(_REPOSITORY_ROOT))
    python_path.append(str(_REPOSITORY_ROOT / "src"))
    if environment.get("PYTHONPATH"):
        python_path.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(python_path)
    environment["PYTHONIOENCODING"] = CHILD_ENCODING
    if suppress_bytecode:
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, *args],
        cwd=_REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding=CHILD_ENCODING,
        check=False,
    )

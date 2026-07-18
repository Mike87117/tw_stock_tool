from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run_repo_python(
    *args: str,
    extra_pythonpath: tuple[str | Path, ...] = (),
    include_repository_root: bool = True,
    suppress_bytecode: bool = True,
    errors: str | None = "replace",
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    python_path = [str(path) for path in extra_pythonpath]
    if include_repository_root:
        python_path.append(str(_REPOSITORY_ROOT))
    python_path.append(str(_REPOSITORY_ROOT / "src"))
    if environment.get("PYTHONPATH"):
        python_path.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(python_path)
    if suppress_bytecode:
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
    options = {
        "cwd": _REPOSITORY_ROOT,
        "env": environment,
        "capture_output": True,
        "text": True,
        "check": False,
    }
    if errors is not None:
        options["errors"] = errors
    return subprocess.run([sys.executable, *args], **options)

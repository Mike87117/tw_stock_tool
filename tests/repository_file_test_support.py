"""Enumerate repository files without auditing Git metadata or virtualenvs."""

from collections.abc import Iterator
import os
from pathlib import Path


def iter_repository_files(root: Path) -> Iterator[Path]:
    """Prune virtualenvs by their marker, including environments with custom names."""
    for directory, directories, files in os.walk(root):
        parent = Path(directory)
        directories[:] = [
            name for name in directories
            if name != ".git" and not (parent / name / "pyvenv.cfg").is_file()
        ]
        for name in files:
            yield parent / name

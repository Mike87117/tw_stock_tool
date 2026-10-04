from pathlib import Path
import os
import shutil
from tempfile import mkdtemp


class CsvExportRecoveryError(OSError):
    """Publication failed and recovery files must be retained for manual restore."""

    def __init__(self, recovery_directory, publication_error, rollback_errors):
        self.recovery_directory = recovery_directory
        self.publication_error = publication_error
        self.rollback_errors = tuple(rollback_errors)
        super().__init__(
            f"CSV export failed: {publication_error}. Recovery was incomplete; "
            f"original backups and staged files were retained at {recovery_directory}."
        )

def write_text_report(
    content: str,
    path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Write text content to a file, returning the absolute path."""
    p = Path(path).resolve()
    if p.exists() and not overwrite:
        raise FileExistsError(f"File already exists: {p}")

    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w" if overwrite else "x", encoding="utf-8", newline="") as f:
        f.write(content)

    return p

def write_csv_bundle(
    csv_bundle: dict[str, str],
    output_dir: str | Path,
    *,
    basename: str = "simulated_paper_trading",
    overwrite: bool = False,
) -> dict[str, Path]:
    """Write a bundle of CSV strings to a directory, returning a dict of absolute paths."""
    required_keys = {"summary", "orders", "fills"}
    provided_keys = set(csv_bundle.keys())

    if provided_keys != required_keys:
        missing = required_keys - provided_keys
        extra = provided_keys - required_keys
        msg = []
        if missing:
            msg.append(f"missing keys: {missing}")
        if extra:
            msg.append(f"extra keys: {extra}")
        raise ValueError("Invalid CSV bundle: " + ", ".join(msg))

    return write_csv_files(csv_bundle, output_dir, basename=basename, overwrite=overwrite)


def csv_target_paths(keys, output_dir, basename):
    if type(basename) is not str:
        raise ValueError("basename must be an exact str instance")
    if not basename or basename.isspace() or basename in (".", ".."):
        raise ValueError("basename must be a nonempty filename")
    if "/" in basename or "\\" in basename or ":" in basename:
        raise ValueError("basename must not contain path separators or a drive prefix")
    directory = Path(output_dir).resolve()
    paths = {key: (directory / f"{basename}_{key}.csv").resolve() for key in keys}
    if any(path.parent != directory for path in paths.values()):
        raise ValueError("basename escapes output directory")
    return paths


def write_csv_files(csv_bundle, output_dir, *, basename, overwrite=False):
    paths = csv_target_paths(csv_bundle, output_dir, basename)
    if not overwrite:
        for path in paths.values():
            if path.exists():
                raise FileExistsError(f"File already exists: {path}")
    directory = Path(output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    staging = Path(mkdtemp(prefix=".csv-export-", dir=directory))
    retain_recovery_files = False
    try:
        staged = {}
        backups = {}
        for key, content in csv_bundle.items():
            staged[key] = write_text_report(content, staging / paths[key].name)
            if overwrite and paths[key].exists():
                backup = staging / f"{key}.backup"
                shutil.copy2(paths[key], backup)
                backups[key] = backup

        published = []
        try:
            for key, target in paths.items():
                identity = staged[key].stat()
                if overwrite:
                    os.replace(staged[key], target)
                else:
                    os.link(staged[key], target)
                published.append((key, identity))
        except BaseException as publication_error:
            # Undo only files still owned by this export. A concurrent replacement
            # must not be deleted or restored over.
            rollback_errors = []
            for key, identity in reversed(published):
                target = paths[key]
                try:
                    try:
                        current = target.stat()
                    except FileNotFoundError:
                        continue
                    if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
                        continue
                    if key in backups:
                        os.replace(backups[key], target)
                    else:
                        target.unlink()
                except OSError as rollback_error:
                    rollback_errors.append((target, rollback_error))
            if rollback_errors:
                retain_recovery_files = True
                raise CsvExportRecoveryError(staging, publication_error, rollback_errors) from publication_error
            raise
    finally:
        if not retain_recovery_files:
            if staging.resolve().parent != directory:
                raise ValueError("CSV staging directory must stay within output directory.")
            shutil.rmtree(staging)
    return paths

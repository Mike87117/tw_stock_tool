from pathlib import Path

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
    with open(p, "w" if overwrite else "x", encoding="utf-8") as f:
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
    for key, content in csv_bundle.items():
        write_text_report(content, paths[key], overwrite=overwrite)
    return paths

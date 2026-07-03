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
    with open(p, "w", encoding="utf-8") as f:
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

    dir_path = Path(output_dir).resolve()

    target_paths = {
        "summary": dir_path / f"{basename}_summary.csv",
        "orders": dir_path / f"{basename}_orders.csv",
        "fills": dir_path / f"{basename}_fills.csv",
    }

    # Check for existing files before writing any
    if not overwrite:
        for p in target_paths.values():
            if p.exists():
                raise FileExistsError(f"File already exists: {p}")

    dir_path.mkdir(parents=True, exist_ok=True)

    for key, content in csv_bundle.items():
        with open(target_paths[key], "w", encoding="utf-8") as f:
            f.write(content)

    return target_paths

# Phase 55.3D closeout

Phase 55.3D adds the offline, read-only `twstock run` CLI.

- `twstock run list --workspace PATH` lists catalog entries, including damaged runs.
- `twstock run inspect FULL-UUID --workspace PATH` requires an exact lowercase UUID v4 and shows manifest metadata plus catalog findings.
- Queries open only existing Workspace roots and `runs/` directories; no missing directories, manifests, artifacts, cache, or output files are created.
- Artifact content is never opened. There is no JSON output, reproduce, delete, cleanup, retention, GUI, or database catalog capability.

Exit codes are 0 for successful queries, 1 for controlled Workspace/catalog/lookup errors, and 2 for argparse errors.

## Final evidence

- Previous reviewed head: `3d97f687ce9f03b79056f4e02b639cd941bcc4c8`
- Final implementation head: `2cf2acdbaca7ee9d3d1d8eae39d22a001d7d4ec4`
- Local Python: 3.12.10
- Phase 55.3D focused tests: 42 passed; 2 skipped locally because Windows symlink privilege is unavailable.
- Unified CLI tests: 11 passed.
- Existing `twstock` CLI tests: 56 passed.
- Full suite: 2,326 passed; 7 skipped locally.
- Package/import/compile smoke: installed `twstock` help commands, required imports, and `python -m compileall src` passed.
- GitHub Actions evidence: runs `30702289235` and `30702290678` both passed `test` and `package-smoke` on Python 3.11 and Python 3.12.

## Known limitations

- Local real-symlink tests remain skipped when Windows symlink privilege is unavailable; mocked reparse-point coverage and GitHub Actions coverage remain active.
- The run CLI intentionally remains offline and read-only; JSON output, reproduce, deletion, cleanup, retention, artifact preview, database, GUI, and workflow migration are outside this phase.

Next phase: Phase 55.3E.

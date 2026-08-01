# Phase 55.3D closeout

Phase 55.3D adds the offline, read-only `twstock run` CLI.

- `twstock run list --workspace PATH` lists catalog entries, including damaged runs.
- `twstock run inspect FULL-UUID --workspace PATH` requires an exact lowercase UUID v4 and shows manifest metadata plus catalog findings.
- Queries open only existing Workspace roots and `runs/` directories; no missing directories, manifests, artifacts, cache, or output files are created.
- Artifact content is never opened. There is no JSON output, reproduce, delete, cleanup, retention, GUI, or database catalog capability.

Exit codes are 0 for successful queries, 1 for controlled Workspace/catalog/lookup errors, and 2 for argparse errors. Phase 55.3E remains the next phase.

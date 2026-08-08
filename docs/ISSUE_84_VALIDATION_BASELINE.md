# Issue #84 - Validation baseline restoration (B1, B2, B4, B9)

Maintenance/correctness work. It does **not** change the Phase 56 product
roadmap; Phase 56.3 Recommendation Evidence remains the next product phase.

Baseline: `750a9a2decc8ea67fc9050086f6dddedc5c6b763` (PR #75, Phase 56.2).

These four defects shared one property: each made a green result mean less than
it appeared to. This document records the contracts that replaced them.

## B1 - `twstock doctor` contract

**Root cause.** `REQUIRED_CLI_FILES` still listed the root wrappers retired in
Cleanup 4A/4B (see [root wrapper removal record](archive/root-wrapper-removal.md),
42 removed / 0 remaining), and both `check_required_files()` and
`check_requirements_file()` defaulted their base directory to
`Path(__file__).resolve().parent` - `src/tw_stock_tool/utils/`. Every run
reported 9 FAIL and exited 1.

**Contract now.** `doctor` is an **end-user environment checker first**. It must
return a correct verdict for an installed distribution with no checkout.

| Check | Installed distribution | Source checkout |
| --- | --- | --- |
| Python version | yes | yes |
| Third-party imports | yes | yes |
| Writable cache/output directories | yes | yes |
| `Package version` | version from `importlib.metadata` | version from `pyproject.toml` |
| `requirements.txt` | not emitted | resolved from the repository root |

`find_repository_root()` identifies a checkout by requiring **both** layout
markers (`pyproject.toml` next to `src/tw_stock_tool`) and returns `None`
otherwise, so repository-only checks are skipped rather than failed. The
removed root-wrapper inventory was not replaced with another stale file list.

## B2 - Unified CLI help ownership

**Root cause.** `_add_passthrough_parser()` defaulted to `forward_help=False`,
i.e. `add_help=True`, so argparse answered `--help` on the wrapper parser before
the underlying CLI ever saw it. 19 of 23 passthrough routes printed an
option-less stub. Both CI and the unit suite asserted only exit status 0 and the
presence of `usage:`, which the stub satisfies.

**Contract now.** A passthrough command delegates every argument to an
underlying CLI, so it delegates `--help` too. `_add_passthrough_parser()` builds
parsers with `add_help=False` unconditionally and `parse_known_args()` forwards
the flag. There is no per-route opt-in left to forget.

Wrapper-owned help is now an explicit, closed set of routes that genuinely have
no underlying parser:

| Route | Owner | Why |
| --- | --- | --- |
| `stock-list` | wrapper | grouping node; its leaves forward |
| `gui` | wrapper | takes no arguments, and answering here keeps `twstock gui --help` from importing Tk |

Every other public route - including `stock-list update` and
`stock-list smoke-check`, which previously had wrapper help through direct
`add_parser()` calls - forwards.

**Safety wording is preserved.** Each underlying parser already carried the same
research-only description as its wrapper registration, so forwarding does not
drop scope or disclaimer text; `test_safety_scope_text_survives_help_forwarding`
pins this for all seven described routes.

**Testing.** Exit status plus `usage:` cannot distinguish real help from the
stub, so every route now pins a **command-specific marker** owned by the
underlying parser (`analyze` -> `--save-chart`, `walk-forward` ->
`--train-days`, ...). The marker table is declared once per layer in
`tests/test_track_p2_1_...py` (`Route.help_marker`) and
`scripts/package_smoke.py` (`HELP_MARKERS`), and a test asserts the two agree
and that the smoke covers every public route. A new route cannot be added
without deciding what its `--help` must prove.

The `--help` path now executes the underlying `main()` rather than a stub, so a
regression test asserts that `sklearn`, `matplotlib` and `mplfinance` are still
absent from `sys.modules` afterwards, preserving the PR #81 lazy-import
boundary.

## B4 - Subprocess decoding contract

**Root cause.** `run_repo_python()` used `text=True` with no `encoding`, so
child output was decoded with the host ANSI code page. On a cp950 Windows host
the repository's Chinese CLI output either became mojibake (`errors="replace"`,
the default) or killed the reader thread with `UnicodeDecodeError` and left
`stdout` as `None` (`errors=None`, used by C5.1). Three tests failed locally
while GitHub Actions stayed green on Ubuntu.

**Contract now.** One contract for all callers, no per-call knob:

* child env sets `PYTHONIOENCODING=utf-8`;
* the parent decodes with `encoding="utf-8"`;
* decoding is **strict** - the `errors` parameter was removed rather than
  defaulted to `"replace"`, because repairing malformed output turns a real
  defect into a passing assertion.

This supersedes the `errors` parameter described in
[Track P3.2 §7-8](TRACK_P3_2_SHARED_SUBPROCESS_TEST_HELPER.md).
`test_non_ascii_child_output_round_trips_independently_of_host_code_page`
asserts exact round-tripping of Chinese stdout and stderr with a legacy code
page forced into the environment, so it fails on a UTF-8 host too if the
contract regresses.

## B9 - Installed-package smoke isolation

**Root cause.** The repository root ships `tw_stock_tool/__init__.py`, a
compatibility namespace shim appending `src/tw_stock_tool` to `__path__`. CI ran
`python -c "import tw_stock_tool"` from the checkout, where the working
directory is on `sys.path`, so the smoke resolved the working tree and proved
nothing about the wheel just installed.

**Contract now.** `scripts/package_smoke.py` is the single reusable entrypoint.
It relocates to a temporary directory, strips checkout entries from the child
`PYTHONPATH`, and asserts:

1. `tw_stock_tool.__file__`, every `__path__` entry, and `twstock_cli.__file__`
   resolve **outside** the checkout;
2. `importlib.metadata.version("tw-stock-tool")` equals the `pyproject.toml`
   version;
3. the console entrypoint and `python -m tw_stock_tool.cli.twstock_cli` both work;
4. all 29 public routes emit their command-specific help marker (this is the
   CI-side gate for B2).

CI additionally runs `twstock doctor` from `$RUNNER_TEMP`, which is the
installed-context acceptance criterion for B1.

The shim is intentionally **not** removed - that is a packaging-architecture
decision outside this scope. The goal is that the smoke can no longer be fooled
by it. `tests/test_package_smoke_isolation.py` proves the shim still shadows an
in-tree import and that the isolation check actually fires rather than passing
vacuously.

## Out of scope

Issue #84 items B3, B5, B6, B7, B8, B10a, B10b and B10c were not addressed here
and remain open.

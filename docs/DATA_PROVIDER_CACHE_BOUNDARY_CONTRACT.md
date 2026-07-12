# Data Provider/Cache Boundary Contract

## A. Inventory outcome

**DATA_PROVIDER_CACHE_CONTRACT_INVENTORIED_EXTRACTION_NOT_AUTHORIZED**

`download_tw_stock()` remains the stable orchestration facade. Provider, cache, normalization, diagnostics, and orchestration coexist in `data_loader.py`. Existing tests protect many behaviors but are not a complete extraction contract. Track B2 must add missing characterization before any production change; the Track A stack remains HOLD and unchanged. **No data-provider or cache extraction is authorized by Track B1.**

## B. Scope and boundary terminology

| Term | Meaning |
|---|---|
| Public loader facade | `download_tw_stock` public orchestration call. |
| Provider adapter | yfinance or official-source fetch boundary. |
| Official fallback | TWSE/TPEx fetch after eligible yfinance failures. |
| Provider candidate | attempted source for a resolved symbol. |
| Symbol candidate | `.TW` or `.TWO` resolved market symbol. |
| Runtime cache | loader-owned path, freshness, read/write, and stale policy. |
| Cache administration | CSV listing, summary, and deletion in `cache_utils.py`. |
| Fresh cache | eligible current-session cache by Taiwan market-close rule. |
| Stale cache | bounded fallback after live failure. |
| Force refresh | bypasses both cache-read stages. |
| Cache identity | symbol, period, interval, and auto-adjust filename inputs. |
| Output normalization | OHLCV/schema/index preparation. |
| Error translation | aggregated `DataLoaderError` result. |
| Diagnostic side effect | stdout/stderr status or warning. |
| Patch surface | tracked direct call or monkeypatch target. |
| Compatibility wrapper | root module forwarding package module. |
| Characterization test | deterministic observable-behavior test. |
| Extraction seam | candidate cohesive code movement boundary. |
| Orchestration | candidate/provider/cache/error coordination. |
| Policy change | intentional behavior change requiring approval. |
| Behavior-preserving refactor | move preserving imports, patches, output, errors, timing, identity. |

`cache_utils.py` is cache administration, not runtime cache-selection policy; `cache_manager.py` is its CLI facade. Underscore names may still be patch or external surfaces. B1 inventories current behavior rather than redesigning it.

## C. Public loader API contract

`download_tw_stock(stock_id, period="1y", interval="1d", auto_adjust=None, force_refresh=False, verbose=False) -> tuple[pd.DataFrame, str]`

| Contract element | Current behavior | Default | Validation | Observable side effect | Caller dependency | Compatibility risk | Authority required for change |
|---|---|---|---|---|---|---|---|
| stock_id | source identifier | required | loader validation | candidate attempts | analysis/CLI | high | production |
| period | history window | `1y` | valid-period set | cache identity | callers | high | production |
| interval | bar interval | `1d` | valid-interval set | provider eligibility | callers | high | production |
| auto_adjust | provider adjustment flag | config when None | boolean resolution | filename/fallback gate | callers | high | production |
| force_refresh | bypass cache reads | false | boolean path | live attempts | CLI/tests | high | production |
| verbose | status messages | false | boolean path | stdout status | CLI | medium | production |
| returned DataFrame | normalized OHLCV | n/a | usable data | dataframe | analysis | high | production |
| returned resolved symbol | successful market symbol | n/a | candidate success | tuple element | callers | high | production |
| raised DataLoaderError | unified failures | n/a | aggregate failure | exception text | CLI/tests | high | production |
| stdout behavior | verbose-only loader status | quiet | n/a | status lines | CLI | medium | production |
| stderr behavior | stale warning always emitted | n/a | live failure/stale | warning | users/tests | high | production |
| cache side effects | read/write CSV possible | n/a | path/freshness | filesystem | tests | high | production |

`auto_adjust=None` resolves through `DEFAULT_AUTO_ADJUST`; the return is a two-item tuple; successful symbol is returned; cache-write failure does not invalidate live data; stale-cache use warns on stderr; verbose adds status without unsuppressing yfinance noise. Defaults, tuple shape, resolution, exceptions, or output are compatibility changes.

## D. Input validation and symbol-resolution contract

| Concern | Current behavior | Evidence | Caller-visible result | Characterization coverage | Change risk |
|---|---|---|---|---|---|
| Blank stock ID | rejected | loader test | DataLoaderError | COVERED | high |
| Whitespace trimming | stripped | source | normalized candidate | PARTIALLY_COVERED | medium |
| Uppercase normalization | uppercased | source | uppercase symbol | PARTIALLY_COVERED | medium |
| `.TW`/`.TWO` removal during validation | base examined | source | suffix accepted | PARTIALLY_COVERED | high |
| Base has digit | required | loader test | invalid format error | COVERED | high |
| Valid period | enforced | source | DataLoaderError | PARTIALLY_COVERED | high |
| Valid interval | enforced | source | DataLoaderError | PARTIALLY_COVERED | high |
| Unsuffixed order | `.TW`, then `.TWO` | loader test | attempted order | COVERED | high |
| Explicit `.TW` | no `.TWO` crossover | loader test | one market | COVERED | high |
| Explicit `.TWO` | no `.TW` crossover | loader test | one market | COVERED | high |
| Mixed-case suffix | uppercase then explicit path | source | resolved suffix | NOT_COVERED | medium |
| `00632R`-like identifier | accepted if digit exists | source | valid candidate | PARTIALLY_COVERED | medium |
| Tried-symbol reporting | included on no-data | loader test | error detail | COVERED | high |
| Original ID in errors | error retains input context | source | diagnostic | PARTIALLY_COVERED | medium |

Candidate order is observable; validation does not establish that a security exists.

## E. Provider and fallback execution contract

| Stage | Entry condition | Provider or operation | Order | Success behavior | Failure behavior | Observable contract | Current test coverage |
|---|---|---|---|---|---|---|---|
| Fresh-cache check | each candidate, not forced | runtime cache | before live | return cache | record read issue | cache-first | COVERED |
| First yfinance candidate | candidate exists | yfinance `.TW`/explicit | 1 | normalize/write/return | aggregate | first candidate | COVERED |
| Second yfinance candidate | unsuffixed first failed | yfinance `.TWO` | 2 | normalize/write/return | aggregate | TW then TWO | COVERED |
| yfinance empty DataFrame | empty return | yfinance | per candidate | none | aggregate | empty is failure | COVERED |
| yfinance exception | raised | yfinance | per candidate | none | aggregate | quiet error | COVERED |
| auto_adjust=True after failure | true | no official path | after yfinance | stale stage | aggregate | official skipped | COVERED |
| auto_adjust=False eligibility | false | official path | after all yfinance | attempt official | aggregate | gate | COVERED |
| TWSE official fallback | `.TW` candidate | TWSE | before TPEx candidate | normalize/write/return | aggregate | 1d only | COVERED |
| TPEx monthly fallback | `.TWO` candidate | TPEx monthly | per TWO official | normalize/write/return | latest quote fallback | separate parser | COVERED |
| TPEx latest-quote fallback | no monthly rows | TPEx quote | after monthly | return latest | aggregate | quote endpoint | COVERED |
| Official interval limit | non-1d | official | path gate | none | DataLoaderError | 1d only | COVERED |
| Official candidate order | yfinance exhausted | TWSE then TPEx by candidate | after live | return first success | aggregate | no reorder | PARTIALLY_COVERED |
| Provider success cache write | normalized live success | runtime cache | before return | write then return | collect write error | nonfatal write | COVERED |
| Provider success return | usable normalized data | loader | terminal | tuple return | n/a | resolved symbol | COVERED |
| All live failed | all candidates exhausted | aggregation | before stale | none | unified error/stale | aggregate | COVERED |
| Stale-cache stage | live failure, not forced | runtime cache | final | read/return if age valid | aggregate/raise | stale last | COVERED |

All yfinance candidates precede official fallback; official fallback only occurs when `auto_adjust` is false. TWSE/TPEx official paths support `1d`; an unsuffixed symbol can reach TWSE then TPEx; TPEx monthly rows may fall back to latest quote. Official data is not guaranteed complete/current/investment grade. Extraction must not reorder attempts or change aggregation.

## F. Runtime cache lifecycle contract

| Cache concern | Current behavior | Source module | Observable output or side effect | Failure behavior | Patch/config dependency | Characterization status | Extraction risk |
|---|---|---|---|---|---|---|---|
| Cache directory source | configured `CACHE_DIR` | config/loader | selected directory | n/a | env/patch | COVERED | high |
| Filename construction | symbol_period_interval_adjusted-bool.csv | loader | CSV path | n/a | CACHE_DIR | PARTIALLY_COVERED | high |
| Slash sanitization | slash becomes underscore | loader | safe filename | n/a | helper | NOT_COVERED | medium |
| Period identity | filename component | loader | separate cache | n/a | helper | PARTIALLY_COVERED | high |
| Interval identity | filename component | loader | separate cache | n/a | helper | PARTIALLY_COVERED | high |
| auto_adjust identity | filename component | loader | separate cache | n/a | helper | PARTIALLY_COVERED | high |
| Fresh existence | path must exist | loader | cache branch | live fallback | `_is_cache_fresh` | COVERED | high |
| Same-day requirement | local Taipei date | loader | freshness | live fallback | time | PARTIALLY_COVERED | high |
| Before-close freshness | current-date cache fresh | loader | cache hit | live fallback | time | COVERED | high |
| After-14:30 freshness | mtime must meet 14:30 | loader | cache hit | live fallback | time | COVERED | high |
| CSV read | pandas CSV/index parse | loader | DataFrame | aggregate error | `_read_cache` | COVERED | high |
| Index restoration | index named Date | loader | normalized index | DataLoaderError | read/prepare | PARTIALLY_COVERED | high |
| Write directory | parent mkdir | loader | CSV write | collected error | `_write_cache` | COVERED | medium |
| Write failure | nonfatal | loader | error aggregation | return live data | patch | COVERED | high |
| Fresh read failure | live fallback | loader | aggregated detail | continue | patch | COVERED | high |
| Force/fresh | bypass fresh read | loader | live attempt | normal errors | parameter | COVERED | high |
| Force/stale | bypass stale fallback | loader | raises after live | no stale | parameter | COVERED | high |
| Stale discovery | existing candidate cache | loader | final cache path | aggregate | path | COVERED | high |
| Stale age | mtime days | loader | age text | aggregate | `_get_cache_age_days` | COVERED | high |
| Maximum stale age | config limit | config/loader | bounded reuse | reject | env/config | COVERED | high |
| Over-age rejection | age exceeds max | loader | error detail | raise | patch | COVERED | high |
| Accepted stale warning | stderr warning | loader | warning/return | n/a | stderr | COVERED | high |
| Stale read failure | aggregate then raise | loader | error detail | unified failure | patch | NOT_COVERED | high |
| Administrative list | CSV files only | cache_utils | list | empty list | cache_dir arg | COVERED | medium |
| Administrative summary | CSV metadata frame | cache_utils | summary | empty frame | cache_dir arg | COVERED | medium |
| Administrative clear | deletes selected CSV | cache_utils | count | skip absent | cache_dir arg | COVERED | high |

Before 14:30 Asia/Taipei, a current-local-date cache is fresh; at/after 14:30 its mtime must meet that day’s 14:30 threshold. Forced live fetches may write cache. Stale cache follows live failure only and is rejected over `MAX_STALE_CACHE_DAYS`. `cache_utils.py` operates on CSV files in its selected directory; no runtime-policy merge is proposed.

## G. Data normalization and return contract

| Data concern | Current contract | Transformation | Failure behavior | Downstream dependency | Existing test evidence | Missing characterization |
|---|---|---|---|---|---|---|
| MultiIndex flattening | flattened | column level selection | missing columns error | analysis | COVERED | variants |
| Required OHLCV | Open/High/Low/Close/Volume | select/order | DataLoaderError | backtesting | COVERED | source variants |
| Exact column order | Open High Low Close Volume | reorder | n/a | callers | COVERED | cache/live comparison |
| Missing OHLC rows | dropped | dropna OHLC | empty error | analysis | COVERED | mixed cases |
| Volume | retained | numeric source column | missing error | reports | PARTIALLY_COVERED | null policy |
| Empty usable data | rejected | post-drop check | DataLoaderError | callers | COVERED | official empty |
| DatetimeIndex | accepted | preserve | n/a | time series | PARTIALLY_COVERED | timezone |
| Index conversion | convertible index parsed | `to_datetime` | invalid error | cache | COVERED | edge formats |
| Invalid index | rejected | validation | DataLoaderError | callers | COVERED | cache corrupt |
| Index name | `Date` | assign name | n/a | CSV/tests | PARTIALLY_COVERED | cache read |
| Duplicate official dates | deduplicated | Date dedupe | n/a | official data | PARTIALLY_COVERED | explicit test |
| Official-date sorting | ascending | sort Date | n/a | time series | PARTIALLY_COVERED | explicit test |
| Period-start filtering | official rows filtered | start bound | empty error | period contract | PARTIALLY_COVERED | boundaries |
| `1d` row limiting | no intraday limit path | period/provider logic | n/a | callers | NOT_COVERED | exact bound |
| `5d` row limiting | provider period behavior | provider result | n/a | callers | NOT_COVERED | exact bound |
| Returned symbol identity | successful candidate | tuple element | n/a | callers | COVERED | cache/live |
| Cache/live equivalence | normalized frames | same prepare path | errors | callers | PARTIALLY_COVERED | frame equivalence |

Output columns are exactly `Open`, `High`, `Low`, `Close`, `Volume`; OHLC-null rows are removed; index must become datetime-compatible and is named `Date`; official rows are deduplicated/sorted. Cache/live tests establish frame equivalence, not byte identity.

## H. Diagnostics, errors, and concurrency contract

| Diagnostic/error surface | Current behavior | Output channel | Concurrency requirement | Caller-visible | Test coverage | Extraction requirement |
|---|---|---|---|---|---|---|
| DataLoaderError | unified loader exception | exception | n/a | yes | COVERED | preserve type |
| Unified no-data error | tried symbols/reasons | exception | n/a | yes | COVERED | preserve aggregation |
| Tried-symbol list | attempted candidates listed | exception | n/a | yes | COVERED | preserve order |
| Per-attempt aggregation | errors appended | exception | n/a | yes | COVERED | preserve text |
| Cache-read detail | read failure appended | exception | n/a | yes | COVERED | preserve |
| Cache-write detail | write failure appended | error list | n/a | indirectly | COVERED | nonfatal |
| Official-fallback detail | provider failure appended | exception | n/a | yes | PARTIALLY_COVERED | preserve |
| Stale rejection detail | age/max appended | exception | n/a | yes | COVERED | preserve |
| yfinance stdout suppression | redirected quiet | suppressed | global lock | yes | COVERED | retain lock |
| yfinance stderr suppression | redirected quiet | suppressed | global lock | yes | COVERED | retain lock |
| Logger restoration | restored on raise | logger | lock scope | indirect | PARTIALLY_COVERED | characterize |
| console_io_lock | serializes redirection | n/a | mandatory | indirect | COVERED | retain |
| yfinance `threads=False` | provider argument | quiet call | n/a | indirect | PARTIALLY_COVERED | preserve |
| Verbose fresh-cache | from cache status | stdout | n/a | yes | PARTIALLY_COVERED | exact text |
| Verbose live-download | downloaded status | stdout | n/a | yes | PARTIALLY_COVERED | exact text |
| Verbose official fallback | fallback status | stdout | n/a | yes | PARTIALLY_COVERED | exact text |
| Verbose stale-cache | stale status | stdout | n/a | yes | PARTIALLY_COVERED | exact text |
| Mandatory stale warning | warning despite quiet | stderr | n/a | yes | COVERED | exact channel |

Suppression redirects process-global stdout/stderr and remains serialized; logger state must restore even on provider errors. Error text is a compatibility surface until deliberately changed; write errors are collected but valid downloaded data returns.

## I. Caller, wrapper, and patch-surface inventory

### Direct and indirect runtime callers

| Tracked file | Imported surface | Direct or indirect use | Arguments supplied | Return values consumed | Error handling | Compatibility dependency |
|---|---|---|---|---|---|---|
| analysis/analysis.py | download_tw_stock | direct `analyze_stock` | stock/period/interval | df,symbol | caller flow | tuple/schema |
| analysis/scanner.py | analyze_stock | indirect scanner | scan inputs | analysis dict | catches workflow errors | loader via analysis |
| cli/price_data_smoke_check.py | data_loader.download_tw_stock | direct | symbol/options | df,symbol | report failure | tuple/error |
| cli/clean_stocks.py | download_tw_stock | direct | stock/period | df,symbol | invalid handling | resolution |
| utils/verify_batch.py | download_tw_stock | direct | stock/period/interval | df,symbol | batch errors | tuple/schema |
| cli/main.py | DataLoaderError | indirect dispatch | CLI command | exception | catches | exception type |
| GUI/service callers | analysis/scanner workflows | indirect | UI inputs | analysis result | workflow handling | loader contract |
| report/ML/batch tracked callers | analysis path or verify_batch | indirect | workflow inputs | frames/results | workflow handling | schema |

### Wrapper and import surfaces

| Surface | Target | Re-export behavior | Executable behavior | Test evidence | External-use uncertainty | Required preservation |
|---|---|---|---|---|---|---|
| Root data_loader.py | package loader | wrapper module | import facade | wrapper tests | unknown | module identity |
| Root cache_utils.py | package cache_utils | wrapper module | import facade | cache tests | unknown | functions |
| Root cache_manager.py | package manager | wrapper module | CLI forwarding | CLI tests | unknown | main behavior |
| Package submodule imports | data package | direct submodules | n/a | source/tests | unknown | paths |
| `tw_stock_tool.data.__init__` | package init | limited exports | n/a | source | unknown | initializer |
| CLI cache command | cache_manager | command dispatch | administration CLI | cache tests | unknown | CLI output |
| README/documented imports | data loader/cache docs | documented usage | n/a | docs | unknown | examples |

### Patch and monkeypatch surfaces

| Surface | Current patch/call location | Why used | Extraction break risk | Compatibility strategy required later |
|---|---|---|---|---|
| CACHE_DIR | test_data_loader/config tests | isolate cache | high | delegate/config patch |
| yf.download | test_data_loader | deterministic provider | high | preserve adapter patch |
| requests.get | provider tests | deterministic official data | high | preserve patch |
| _is_cache_fresh | test_data_loader | choose cache stage | high | delegate |
| _read_cache | test_data_loader | failure/cache data | high | delegate |
| _write_cache | test_data_loader | nonfatal write | high | delegate |
| _get_cache_age_days | test_data_loader | stale policy | high | delegate |
| _download_twse_stock | test_data_loader | fallback behavior | high | preserve |
| _download_tpex_stock | test_data_loader | fallback behavior | high | preserve |
| _download_official_stock | test_data_loader | official gate | high | preserve |
| _download_yfinance_quiet | test_data_loader/scanner | quiet provider | high | preserve |
| pd.Timestamp.now | freshness tests | deterministic time | high | inject/delegate |

A private name can still be an effective test or external patch surface.

## J. Existing test coverage and characterization gaps

**CHARACTERIZATION_GAPS_REMAIN_BEFORE_EXTRACTION**

| Behavior | Existing test | Coverage status | Missing edge case | Required before extraction | Recommended Track B2 action |
|---|---|---|---|---|---|
| Fresh cache read/write | test_download_writes... | COVERED | identity variants | yes | filename cases |
| Force refresh | test_force_refresh... | COVERED | write after force | yes | add |
| TWSE fallback | test_twse_fallback... | COVERED | order | yes | add |
| TPEx fallback | test_tpex_fallback... | COVERED | parsing | yes | add |
| `.TW` then `.TWO` | test_numeric_symbol... | COVERED | errors | yes | add |
| Explicit `.TW` | test_explicit_tw... | COVERED | case | yes | add |
| Explicit `.TWO` | test_explicit_two... | COVERED | case | yes | add |
| Auto-adjust gate | test_auto_adjust... | COVERED | aggregation | yes | add |
| Quiet yfinance | test...suppresses_output | COVERED | logger restore | yes | add |
| Concurrent quiet | test...thread_safe | COVERED | exception restore | yes | add |
| Unified no-data | test_no_data_error... | COVERED | text order | yes | add |
| Cache-read failure | test_cache_read_failure... | COVERED | corrupt stale | yes | add |
| Cache-write failure | test_yfinance_cache... | COVERED | message | yes | add |
| Official write failure | test_official_fallback... | COVERED | message | yes | add |
| Official interval | test_official_fallback_interval... | COVERED | TPEx | yes | add |
| Invalid input | test_validate_inputs... | COVERED | trimming | yes | add |
| Invalid DataFrame index | test_prepare_ohlcv... | COVERED | cache path | yes | add |
| Market-close freshness | test_is_cache_fresh... | COVERED | exact boundary | yes | add |
| Stale acceptance | test_stale_cache... | COVERED | warning exact | yes | add |
| Stale age rejection | test_stale_cache_older... | COVERED | mtime failure | yes | add |
| Force stale bypass | test_force_refresh_bypasses... | COVERED | live write | yes | add |
| Cache administration | test_cache_utils | COVERED | non-CSV | no | add |
| Root-wrapper identity | wrapper tests | COVERED | patch behavior | yes | add |
| Direct caller shape | analysis/CLI tests | PARTIALLY_COVERED | all callers | yes | inventory tests |
| Logger restoration | quiet tests | PARTIALLY_COVERED | exception | yes | add |
| Cache filename identity | loader tests | PARTIALLY_COVERED | slash/options | yes | add |
| Before-close freshness | market-close test | COVERED | timezone | yes | add |
| After-close freshness | market-close test | COVERED | exact 14:30 | yes | add |
| Corrupt fresh/live success | read-failure test | PARTIALLY_COVERED | real corrupt CSV | yes | add |
| Corrupt stale aggregation | none | NOT_COVERED | read failure | yes | add |
| Official attempt order | partial fallback tests | PARTIALLY_COVERED | all candidates | yes | add |
| TPEx latest quote | provider tests | PARTIALLY_COVERED | no monthly rows | yes | add |
| Exact columns | loader tests | COVERED | cached frame | yes | add |
| MultiIndex normalization | loader tests | COVERED | levels | yes | add |
| Missing OHLC removal | loader tests | COVERED | mixed nulls | yes | add |
| Index conversion | loader tests | COVERED | timezone | yes | add |
| Verbose strings | none | NOT_COVERED | all statuses | yes | add |
| Stale-warning channel | stale tests | PARTIALLY_COVERED | exact stderr | yes | add |

Live smoke checks are not deterministic CI characterization.

## K. Boundary decomposition candidates

| Candidate seam | Cohesion | Current dependencies | Patch-surface risk | Behavior risk | Test readiness | Compatibility strategy | Suggested order | B1 decision |
|---|---|---|---|---|---|---|---|---|
| Runtime cache path/read/write helpers | high | loader/config/pandas | high | medium | partial | delegates | 1 | PROPOSED_FIRST |
| Runtime freshness/staleness policy | high | time/config/loader | high | high | partial | preserve facade | 2 | DEFERRED |
| yfinance provider adapter | medium | lock/logger | high | high | partial | preserve quiet call | later | DEFERRED |
| TWSE provider adapter | medium | requests/parsing | high | high | partial | preserve helper | later | REQUIRES_MORE_EVIDENCE |
| TPEx provider adapter | medium | monthly/quote parsing | high | high | partial | preserve helper | later | REQUIRES_MORE_EVIDENCE |
| Official parsing utilities | medium | dates/numbers | medium | high | partial | characterize | later | DEFERRED |
| Data normalization helpers | high | loader/callers | medium | high | partial | preserve output | later | DEFERRED |
| Error aggregation | medium | all stages | high | high | partial | preserve text/order | later | REQUIRES_MORE_EVIDENCE |
| Full orchestration extraction | low | all concerns | high | high | incomplete | none now | never first | REJECTED_AS_FIRST_STEP |
| Merge runtime cache into cache_utils.py | low | admin/runtime mismatch | high | high | incomplete | keep separate | never first | REJECTED_AS_FIRST_STEP |

The cache-runtime proposal is cohesive and deterministic-testable while keeping `data_loader.py` facade, but existing patch points, `CACHE_DIR`, time, filename identity, and warning behavior need characterization. It is not production authorization.

## L. Proposed first extraction and Track B2 entry gate

**PROPOSED_FIRST_EXTRACTION_CACHE_RUNTIME_HELPERS_PENDING_CHARACTERIZATION**

The future seam is only `_cache_path`, `_is_cache_fresh`, `_get_cache_age_days`, `_read_cache`, and `_write_cache`; no destination filename is selected. Any future extraction keeps `download_tw_stock` and root wrappers, preserves patch delegates, `CACHE_DIR`, filenames, market-close/force/stale behavior, stderr warnings, nonfatal write failures, post-read normalization, separation from administration, and a rollback plan.

| Gate | Current status | Existing evidence | Missing evidence | Blocking | Required Track B2 test |
|---|---|---|---|---|---|
| Cache filename characterization | PARTIAL_EXISTING_EVIDENCE | cache tests | slash/options | yes | identity matrix |
| CACHE_DIR monkeypatch | COVERED | loader tests | wrapper patch | yes | wrapper patch |
| Same-day before-close freshness | COVERED | market-close test | timezone | yes | timezone case |
| Same-day after-close freshness | COVERED | market-close test | exact boundary | yes | 14:30 case |
| Prior-day cache | PARTIAL_EXISTING_EVIDENCE | freshness source | deterministic test | yes | prior-day |
| Exact 14:30 boundary | NOT_COVERED | threshold code | equality test | yes | boundary |
| Time-zone behavior | PARTIAL_EXISTING_EVIDENCE | Taipei source | conversion test | yes | timezone |
| Cache read index restoration | PARTIAL_EXISTING_EVIDENCE | prepare path | direct CSV | yes | read result |
| Cache read normalization | PARTIAL_EXISTING_EVIDENCE | shared prepare | cache frame | yes | equivalent frame |
| Corrupt fresh fallback | PARTIAL_EXISTING_EVIDENCE | read-failure | corrupt CSV | yes | corrupt fresh |
| Cache write failure | COVERED | write tests | exact aggregation | yes | message |
| Stale cache accepted | COVERED | stale tests | exact warning | yes | stderr |
| Stale cache rejected | COVERED | age test | edge threshold | yes | max boundary |
| Stale mtime failure | NOT_COVERED | source | deterministic failure | yes | stat error |
| Stale read failure | NOT_COVERED | source | aggregation | yes | corrupt stale |
| Force fresh bypass | COVERED | force test | write success | yes | force write |
| Force stale bypass | COVERED | force stale test | aggregation | yes | force stale |
| Successful force write | NOT_COVERED | source | deterministic write | yes | force write |
| Warning stderr | PARTIAL_EXISTING_EVIDENCE | stale test | exact channel/text | yes | capture stderr |
| Verbose output | NOT_COVERED | source | status strings | yes | capture stdout |
| Root-wrapper patch behavior | NOT_COVERED | wrapper existence | monkeypatch | yes | wrapper delegate |
| Full-suite regression gate | COVERED | current suite | B2 change run | yes | full suite |

**No production extraction may begin until the blocking Track B2 characterization gates are complete and reviewed.**

## M. Recommended next phase and non-goals

Recommend exactly **Track B2 ??Data Provider/Cache Boundary Characterization Tests**. B2 should start from final B1 HEAD, add deterministic tests only, fill blocking cache-runtime gaps, preserve production code, confirm the proposed seam remains viable, produce a precise extraction contract, remain HOLD, and not begin extraction.

B1 does not modify production code, add tests, extract cache/provider helpers, add modules, change cache policy/provider order/official fallback/symbol resolution/DataFrame output/errors/diagnostics, modify wrappers or Track A documents, merge or retarget PRs, start Track B2, or start Phase A9.

# Track C2.3.1 Risk and Guard Finite-Number Validation

## Repository

- Branch: `track-c2-research-correctness-fixes`
- Baseline commit: `a06499974074c807766741ffbbde9d730fb4f6ad`
- Final commit is recorded in the execution report.

## Problem statement

Risk snapshot monetary fields, Risk monetary/exposure rule limits, and Guard reference prices accepted some non-finite values. NaN and Infinity could therefore bypass sign-only validation and reach risk decisions or derived arithmetic.

## Approved contracts

Positive finite values are required for `RiskInputSnapshot.price`, `max_order_notional`, `max_position_notional`, `max_total_exposure`, and the Guard reference price. Non-negative finite values are required for `RiskInputSnapshot.cash`, `current_position_notional`, and `total_exposure`; zero remains valid for those fields. Boolean, wrong-type, NaN, positive Infinity, and negative Infinity inputs are rejected. Existing integer contracts are unchanged.

## Implementation summary

`RiskInputSnapshot` now performs type and boolean checks before standard-library `math.isfinite` checks on its four scoped monetary fields. Risk rules use one private helper for the three positive finite monetary/exposure limits. The Guard validates its reference price as numeric, non-boolean, finite, and strictly positive before constructing `RiskInputSnapshot` or calling the risk provider.

No public signatures, dataclass fields, derived formulas, decision comparisons, metadata keys, rejection reasons, or integer validation contracts changed. No dependency was added.

## Validation matrix

| Boundary | NaN | +Infinity | -Infinity | Boolean | Wrong type | Valid boundary |
| -- | -- | -- | -- | -- | -- | -- |
| Risk price | Reject | Reject | Reject | Reject | Reject | Positive finite accepted |
| Risk cash/current notional/total exposure | Reject | Reject | Reject | Reject | Reject | `0.0` accepted |
| Three Risk monetary limits | Reject | Reject | Reject | Reject | Reject | Positive finite decisions unchanged |
| Guard reference price | Reject | Reject | Reject | Reject | Reject | Finite integer and float accepted |

The Guard fail-fast test proves a NaN reference price raises `SimulatedPaperTradingGuardError` before the risk decision provider is called.

## Changed files

- `src/tw_stock_tool/risk/models.py`
- `src/tw_stock_tool/risk/rules.py`
- `src/tw_stock_tool/simulated_paper_trading_guard/adapter.py`
- `tests/test_risk_models.py`
- `tests/test_risk_rules.py`
- `tests/test_simulated_paper_trading_guard_adapter.py`
- `tests/test_track_c1_research_correctness.py`
- `docs/TRACK_C1_RESEARCH_CORRECTNESS_CHARACTERIZATION.md`
- `docs/TRACK_C2_3_1_RISK_GUARD_FINITE_VALIDATION.md`

## Expected-failure transition

- Before Track C2.3.1: 8
- Resolved in Track C2.3.1: 3
- After Track C2.3.1: 5

## Tests executed

- `py -m unittest tests.test_risk_models`
- `py -m unittest tests.test_risk_rules`
- `py -m unittest tests.test_simulated_paper_trading_guard_adapter`
- `py -m unittest tests.test_track_c1_research_correctness`
- Combined targeted suite for all four modules
- `py -m unittest discover -s tests`
- Direct rejection checks for all scoped NaN and Infinity cases

## Non-goals

This phase does not change Paper Trading fill/portfolio validation, portfolio arithmetic, Backtest validation, other Guard modules, portfolio-exposure-provider validation, integer limit contracts, metrics, CLI exit behavior, Analysis, ML, public wrappers, project configuration, or CI.

## Remaining Track C2 work

1. Paper Trading finite-number validation.
2. Backtest finite-number validation.
3. Interval-aware metrics.
4. Unified CLI nonzero exit behavior.

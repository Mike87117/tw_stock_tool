"""Regressions for Issue #84 B3 and B10a.

B3  - an all-winning backtest produces profit_factor = +inf, which the artifact
      serializer rejected as non-finite, so a legitimate result could not be
      exported.
B10a - when a position was still open on the final bar and the final close was
      unusable (<= 0), the EOD close was skipped but final equity was still
      forced to cash, silently dropping the holding.

Both are driven through the real production path (run_backtest_result), not by
hand-constructing a BacktestResult, so they prove the reachable behavior.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from tw_stock_tool.backtesting.backtest import BacktestError, run_backtest, run_backtest_result
from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.backtesting.serialization import (
    BACKTEST_RESULT_SCHEMA_VERSION,
    BacktestResultSerializationError,
    deserialize_backtest_result,
    export_backtest_result_json,
    load_backtest_result_json,
    serialize_backtest_result,
)
from tw_stock_tool.backtesting.serialization_files import (
    export_backtest_result_json_file,
    load_backtest_result_json_file,
)


def _frame(closes: list[float], signals: list[str], opens: list[float] | None = None) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return pd.DataFrame(
        {
            "Open": list(opens if opens is not None else closes),
            "Close": list(closes),
            "Signal": list(signals),
        },
        index=index,
    )


def all_winning_result() -> BacktestResult:
    """One closed trade, positive PnL, no losing trade -> unbounded profit factor."""
    return run_backtest_result(
        _frame(
            closes=[10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
            signals=["BUY", "HOLD", "HOLD", "SELL", "HOLD", "HOLD"],
            opens=[10.0, 10.0, 11.0, 12.0, 13.0, 14.0],
        )
    )


def wins_and_losses_result() -> BacktestResult:
    """At least one winning and one losing closed trade -> finite profit factor."""
    return run_backtest_result(
        _frame(
            closes=[10.0, 12.0, 14.0, 14.0, 9.0, 6.0, 6.0, 6.0],
            signals=["BUY", "HOLD", "SELL", "BUY", "HOLD", "SELL", "HOLD", "HOLD"],
            opens=[10.0, 10.0, 12.0, 14.0, 14.0, 9.0, 6.0, 6.0],
        )
    )


def no_trade_result() -> BacktestResult:
    """No entry signal at all -> no trades."""
    return run_backtest_result(_frame(closes=[10.0, 11.0, 12.0], signals=["HOLD", "HOLD", "HOLD"]))


class ProfitFactorArtifactContractTest(unittest.TestCase):
    """B3: unbounded profit factor must survive the artifact round trip."""

    def test_all_winning_backtest_is_reachable_and_unbounded(self) -> None:
        result = all_winning_result()

        self.assertGreater(result.trade_count, 0)
        self.assertTrue((result.trades["PnL"] > 0).all(), "fixture must contain only winning trades")
        self.assertTrue(math.isinf(result.profit_factor))
        self.assertGreater(result.profit_factor, 0)

    def test_all_winning_backtest_serializes_as_null_profit_factor(self) -> None:
        payload = serialize_backtest_result(all_winning_result())

        self.assertIsNone(payload["summary"]["profit_factor"])
        self.assertEqual(payload["schema_version"], BACKTEST_RESULT_SCHEMA_VERSION)

    def test_all_winning_backtest_json_is_standards_compliant(self) -> None:
        text = export_backtest_result_json(all_winning_result())

        # No Infinity/NaN literals; json.loads with a strict constant hook
        # rejects them outright, which plain json.loads would not.
        def _reject(constant: str) -> None:
            raise AssertionError(f"non-standard JSON constant emitted: {constant}")

        reloaded = json.loads(text, parse_constant=_reject)
        self.assertIsNone(reloaded["summary"]["profit_factor"])
        for banned in ("Infinity", "-Infinity", "NaN"):
            self.assertNotIn(banned, text)

    def test_all_winning_backtest_round_trip_restores_unbounded_meaning(self) -> None:
        original = all_winning_result()

        restored = load_backtest_result_json(export_backtest_result_json(original))

        self.assertTrue(math.isinf(restored.profit_factor))
        self.assertGreater(restored.profit_factor, 0)
        self.assertEqual(restored.trade_count, original.trade_count)

    def test_finite_profit_factor_is_unchanged_by_the_new_encoding(self) -> None:
        original = wins_and_losses_result()
        self.assertTrue(math.isfinite(original.profit_factor))
        self.assertGreater(original.profit_factor, 0)

        payload = serialize_backtest_result(original)
        self.assertEqual(payload["summary"]["profit_factor"], original.profit_factor)

        restored = deserialize_backtest_result(payload)
        self.assertEqual(restored.profit_factor, original.profit_factor)

    def test_no_trade_stays_zero_and_is_distinguishable_from_unbounded(self) -> None:
        original = no_trade_result()
        self.assertEqual(original.trade_count, 0)
        self.assertEqual(original.profit_factor, 0.0)

        payload = serialize_backtest_result(original)
        self.assertEqual(payload["summary"]["profit_factor"], 0.0)
        self.assertIsNotNone(payload["summary"]["profit_factor"])

        restored = deserialize_backtest_result(payload)
        self.assertEqual(restored.profit_factor, 0.0)
        self.assertFalse(math.isinf(restored.profit_factor))

    def test_unbounded_and_no_trade_encode_to_different_json_values(self) -> None:
        unbounded = serialize_backtest_result(all_winning_result())["summary"]["profit_factor"]
        no_trades = serialize_backtest_result(no_trade_result())["summary"]["profit_factor"]

        self.assertIsNone(unbounded)
        self.assertEqual(no_trades, 0.0)
        self.assertNotEqual(unbounded, no_trades)

    def test_end_to_end_artifact_file_export_and_reload(self) -> None:
        original = all_winning_result()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "backtest.json"

            export_backtest_result_json_file(original, path)
            on_disk = json.loads(path.read_text(encoding="utf-8"))
            reloaded = load_backtest_result_json_file(path)

        self.assertIsNone(on_disk["summary"]["profit_factor"])
        self.assertTrue(math.isinf(reloaded.profit_factor))
        self.assertEqual(reloaded.trade_count, original.trade_count)

    def test_legacy_dict_still_reports_infinity(self) -> None:
        """run_backtest()'s historical contract must not change."""
        legacy = run_backtest(
            _frame(
                closes=[10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
                signals=["BUY", "HOLD", "HOLD", "SELL", "HOLD", "HOLD"],
                opens=[10.0, 10.0, 11.0, 12.0, 13.0, 14.0],
            )
        )

        self.assertTrue(math.isinf(legacy["Profit Factor"]))


class ProfitFactorMalformedValueTest(unittest.TestCase):
    """B3 must not weaken the finite-number rule for anything else."""

    def _result(self) -> BacktestResult:
        return no_trade_result()

    def test_nan_profit_factor_is_still_rejected(self) -> None:
        result = self._result()
        result.profit_factor = float("nan")
        with self.assertRaisesRegex(BacktestResultSerializationError, "profit_factor"):
            serialize_backtest_result(result)

    def test_negative_infinite_profit_factor_is_still_rejected(self) -> None:
        result = self._result()
        result.profit_factor = float("-inf")
        with self.assertRaisesRegex(BacktestResultSerializationError, "profit_factor"):
            serialize_backtest_result(result)

    def test_bool_profit_factor_is_still_rejected(self) -> None:
        result = self._result()
        result.profit_factor = True
        with self.assertRaisesRegex(BacktestResultSerializationError, "must be numeric, got bool"):
            serialize_backtest_result(result)

    def test_other_fields_still_reject_non_finite_values(self) -> None:
        cases = (
            ("initial_capital", float("nan")),
            ("initial_capital", float("inf")),
            ("final_capital", float("inf")),
            ("final_capital", float("-inf")),
            ("sharpe_ratio", float("nan")),
            ("sortino_ratio", float("inf")),
            ("total_return_pct", float("nan")),
            ("max_drawdown_pct", float("-inf")),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                result = self._result()
                setattr(result, field, value)
                with self.assertRaisesRegex(BacktestResultSerializationError, "must be finite"):
                    serialize_backtest_result(result)


class ProfitFactorSchemaVersionTest(unittest.TestCase):
    """B3 bumped the schema; version 1 artifacts must still read correctly."""

    def test_current_schema_version_is_two(self) -> None:
        self.assertEqual(BACKTEST_RESULT_SCHEMA_VERSION, 2)

    def test_version_one_artifact_with_finite_profit_factor_still_loads(self) -> None:
        payload = serialize_backtest_result(wins_and_losses_result())
        expected = payload["summary"]["profit_factor"]
        payload["schema_version"] = 1

        restored = deserialize_backtest_result(payload)

        self.assertEqual(restored.profit_factor, expected)

    def test_version_one_artifact_rejects_null_profit_factor(self) -> None:
        """null was never a legal v1 value, so v1 must not silently accept it."""
        payload = serialize_backtest_result(all_winning_result())
        self.assertIsNone(payload["summary"]["profit_factor"])
        payload["schema_version"] = 1

        with self.assertRaisesRegex(BacktestResultSerializationError, "must be numeric in schema_version 1"):
            deserialize_backtest_result(payload)

    def test_version_two_artifact_accepts_null_profit_factor(self) -> None:
        payload = serialize_backtest_result(all_winning_result())
        payload["schema_version"] = 2

        self.assertTrue(math.isinf(deserialize_backtest_result(payload).profit_factor))


class TerminalPositionAccountingTest(unittest.TestCase):
    """B10a: a returned BacktestResult never carries an open position."""

    @staticmethod
    def _held_to_final_bar(final_close: float) -> pd.DataFrame:
        """BUY on bar 0, no exit signal, so shares are still held on the last bar."""
        return _frame(
            closes=[10.0, 11.0, 12.0, 13.0, final_close],
            signals=["BUY", "HOLD", "HOLD", "HOLD", "HOLD"],
            opens=[10.0, 10.0, 11.0, 12.0, 13.0],
        )

    def test_positive_final_close_still_closes_at_eod(self) -> None:
        result = run_backtest_result(self._held_to_final_bar(20.0))

        self.assertEqual(result.trade_count, 1)
        self.assertEqual(result.trades.iloc[-1]["Exit Reason"], "SELL_EOD")
        self.assertEqual(len(result.trades), result.trade_count)
        self.assertAlmostEqual(float(result.equity_curve.iloc[-1]), result.final_capital, places=9)
        self.assertGreater(result.final_capital, 0.0)

    def test_zero_final_close_fails_closed(self) -> None:
        with self.assertRaises(BacktestError) as raised:
            run_backtest_result(self._held_to_final_bar(0.0))

        self.assertIn("0", str(raised.exception))

    def test_negative_final_close_fails_closed(self) -> None:
        with self.assertRaises(BacktestError) as raised:
            run_backtest_result(self._held_to_final_bar(-5.0))

        self.assertIn("-5", str(raised.exception))

    def test_unusable_final_close_no_longer_reports_a_cash_only_result(self) -> None:
        """The old behavior returned a fabricated near-total loss with no trades."""
        for final_close in (0.0, -5.0):
            with self.subTest(final_close=final_close):
                with self.assertRaises(BacktestError):
                    run_backtest_result(self._held_to_final_bar(final_close))

    def test_non_finite_final_close_still_fails_at_input_validation(self) -> None:
        for final_close in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(final_close=final_close):
                with self.assertRaisesRegex(BacktestError, "finite numeric value"):
                    run_backtest_result(self._held_to_final_bar(final_close))

    def test_unusable_final_close_without_open_position_is_unaffected(self) -> None:
        """Fail-closed is scoped to the terminal position, not to prices generally."""
        result = run_backtest_result(
            _frame(
                closes=[10.0, 12.0, 14.0, 0.0],
                signals=["BUY", "HOLD", "SELL", "HOLD"],
                opens=[10.0, 10.0, 12.0, 14.0],
            )
        )

        self.assertEqual(result.trade_count, 1)
        self.assertEqual(result.trades.iloc[-1]["Exit Reason"], "SELL")

    def test_legacy_run_backtest_propagates_the_same_failure(self) -> None:
        with self.assertRaises(BacktestError):
            run_backtest(self._held_to_final_bar(0.0))


class TerminalAccountingInvariantTest(unittest.TestCase):
    """Every successfully returned result must be internally consistent."""

    CASES = {
        "eod_close": ([10.0, 11.0, 12.0, 13.0, 20.0], ["BUY", "HOLD", "HOLD", "HOLD", "HOLD"]),
        "signal_exit": ([10.0, 12.0, 14.0, 14.0, 15.0], ["BUY", "HOLD", "SELL", "HOLD", "HOLD"]),
        "wins_and_losses": (
            [10.0, 12.0, 14.0, 14.0, 9.0, 6.0, 6.0, 6.0],
            ["BUY", "HOLD", "SELL", "BUY", "HOLD", "SELL", "HOLD", "HOLD"],
        ),
        "no_trades": ([10.0, 11.0, 12.0], ["HOLD", "HOLD", "HOLD"]),
    }

    def test_final_capital_matches_terminal_equity_and_trade_records(self) -> None:
        for name, (closes, signals) in self.CASES.items():
            with self.subTest(case=name):
                opens = [closes[0], *closes[:-1]]
                result = run_backtest_result(_frame(closes=closes, signals=signals, opens=opens))

                self.assertAlmostEqual(
                    float(result.equity_curve.iloc[-1]),
                    result.final_capital,
                    places=9,
                    msg="terminal equity must equal final capital once the position is closed",
                )
                self.assertEqual(len(result.trades), result.trade_count)
                self.assertEqual(len(result.equity_curve), len(closes))
                self.assertTrue(math.isfinite(result.final_capital))
                self.assertAlmostEqual(
                    result.total_return_pct,
                    (result.final_capital / result.initial_capital) * 100 - 100,
                    places=9,
                    msg="total return must be derived from the same final capital",
                )

    def test_eod_trade_costs_are_applied(self) -> None:
        result = run_backtest_result(
            _frame(
                closes=[10.0, 11.0, 12.0, 13.0, 20.0],
                signals=["BUY", "HOLD", "HOLD", "HOLD", "HOLD"],
                opens=[10.0, 10.0, 11.0, 12.0, 13.0],
            ),
            initial_capital=100000.0,
            fee_rate=0.001425,
            tax_rate=0.003,
        )

        trade = result.trades.iloc[-1]
        shares = int(trade["Shares"])
        exit_price = float(trade["Exit Price"])
        gross = shares * exit_price
        expected_net = gross - gross * 0.001425 - gross * 0.003
        entry_gross = shares * float(trade["Entry Price"])
        expected_cost = entry_gross + entry_gross * 0.001425

        self.assertEqual(trade["Exit Reason"], "SELL_EOD")
        self.assertAlmostEqual(float(trade["PnL"]), expected_net - expected_cost, places=6)


if __name__ == "__main__":
    unittest.main()

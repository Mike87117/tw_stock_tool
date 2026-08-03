import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import numpy as np
import pandas as pd

from tw_stock_tool.application.universe_qualification import (
    UniverseQualificationRequest,
    evaluate_universe_qualification,
    run_universe_qualification,
)
from tw_stock_tool.application.workspace_execution import WorkspaceRunLifecycle
from tw_stock_tool.application.universe_qualification import publish_universe_qualification
from tw_stock_tool.qualification import load_strategy_qualification_json


def _frame(size=20, close=None):
    index = pd.date_range("2020-01-01", periods=size)
    values = np.asarray(close if close is not None else np.arange(1.0, size + 1.0))
    return pd.DataFrame({"Open": values, "Close": values}, index=index)


def _request(symbol_data, benchmark=None, **kwargs):
    return UniverseQualificationRequest(
        str(uuid4()), "2026-01-01T00:00:00Z", "ma_cross", symbol_data,
        benchmark, train_days=10, test_days=5,
        parameter_options={"short_window": (2, 3), "long_window": (4,)}, **kwargs,
    )


class UniverseQualificationTests(unittest.TestCase):
    def test_parameter_selection_uses_train_only(self):
        first = _frame()
        second = _frame(close=np.r_[np.arange(1.0, 11.0), np.arange(100.0, 110.0)])

        def fake_backtest(frame, strategy, params, *args):
            is_train = len(frame) == 10
            return {
                "Total Return %": 10.0 if is_train and params["short_window"] == 2 else 1.0,
                "Sharpe Ratio": 10.0 if is_train and params["short_window"] == 2 else 1.0,
                "Trade Count": 1, "Max Drawdown %": 0.0,
            }

        with patch("tw_stock_tool.application.universe_qualification._run_strategy_backtest", side_effect=fake_backtest):
            one = evaluate_universe_qualification(_request({"2330": first}))
            two = evaluate_universe_qualification(_request({"2330": second}))
        self.assertEqual(one.symbols[0].windows[0].parameters, two.symbols[0].windows[0].parameters)
        self.assertEqual(one.symbols[0].windows[0].parameters, {"short_window": 2, "long_window": 4})

    def test_ordering_and_partial_failure_are_deterministic(self):
        result = evaluate_universe_qualification(_request({"bad": pd.DataFrame(), "b": _frame(), "a": _frame()}))
        self.assertEqual(tuple(item.symbol for item in result.symbols), ("a", "b", "bad"))
        self.assertGreater(result.qualification.request.metrics.partial_failure_count, 0)
        self.assertEqual(result.decision, "REJECTED")

    def test_higher_cost_stress_failure_rejects(self):
        def expensive_backtest(frame, strategy, params, *args):
            fee = args[5]
            return {
                "Total Return %": -1.0 if fee > 0.001425 else 1.0,
                "Sharpe Ratio": 1.0, "Trade Count": 1, "Max Drawdown %": 0.0,
            }

        request = _request({"2330": _frame()}, _frame())
        with patch("tw_stock_tool.application.universe_qualification._run_strategy_backtest", side_effect=expensive_backtest):
            result = evaluate_universe_qualification(request)
        self.assertFalse(result.qualification.request.metrics.cost_stress_pass)
        self.assertEqual(result.decision, "REJECTED")
        self.assertIn("cost_stress_failure", result.qualification.decision.reason_codes)

    def test_missing_benchmark_and_insufficient_sample_fail_closed(self):
        result = evaluate_universe_qualification(_request({"2330": _frame()}))
        metrics = result.qualification.request.metrics
        self.assertFalse(metrics.benchmark_available)
        self.assertIn("benchmark_missing", result.qualification.decision.reason_codes)
        self.assertIn("insufficient_oos_observations", result.qualification.decision.reason_codes)

    def test_artifact_round_trip_relocation_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as source, tempfile.TemporaryDirectory() as destination:
            request = _request({"2330": _frame()}, _frame())
            result = run_universe_qualification(request, workspace_root=source)
            run_dir = next(Path(source).glob("runs/*/*/*"))
            qualification = run_dir / "artifacts" / "strategy_qualification.json"
            self.assertEqual(load_strategy_qualification_json(qualification.read_text()), result.qualification)
            relocated = Path(destination) / "runs" / run_dir.relative_to(Path(source) / "runs")
            relocated.parent.mkdir(parents=True)
            import shutil
            shutil.copytree(run_dir, relocated)
            self.assertEqual((relocated / result.manifest.artifacts[0].path).read_text(), qualification.read_text())
            lifecycle = WorkspaceRunLifecycle.begin(source, "universe-oos-evaluation")
            existing = lifecycle.artifacts_directory / "strategy_qualification.json"
            existing.write_text("do not overwrite", encoding="utf-8")
            with self.assertRaises(Exception):
                publish_universe_qualification(result, lifecycle)
            self.assertEqual(existing.read_text(encoding="utf-8"), "do not overwrite")


if __name__ == "__main__":
    unittest.main()

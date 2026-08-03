import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import numpy as np
import pandas as pd

from tw_stock_tool.application.universe_qualification import (
    UniverseQualificationRequest,
    UniverseEvidenceSerializationError,
    build_universe_oos_evidence,
    deserialize_universe_oos_evidence,
    evaluate_universe_qualification,
    export_universe_oos_evidence_json,
    load_universe_oos_evidence_json,
    publish_universe_qualification,
    run_universe_qualification,
)
from tw_stock_tool.application.workspace_execution import WorkspaceRunLifecycle
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

        with patch("tw_stock_tool.application.universe_qualification.run_strategy_backtest", side_effect=fake_backtest):
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
        with patch("tw_stock_tool.application.universe_qualification.run_strategy_backtest", side_effect=expensive_backtest):
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
            shutil.copytree(run_dir, relocated)
            self.assertEqual((relocated / result.manifest.artifacts[0].path).read_text(), qualification.read_text())
            lifecycle = WorkspaceRunLifecycle.begin(source, "universe-oos-evaluation")
            existing = lifecycle.artifacts_directory / "strategy_qualification.json"
            existing.write_text("do not overwrite", encoding="utf-8")
            with self.assertRaises(Exception):
                publish_universe_qualification(result, lifecycle)
            self.assertEqual(existing.read_text(encoding="utf-8"), "do not overwrite")


    def test_step_overlap_and_bad_indexes_fail_closed(self):
        with self.assertRaises(ValueError):
            _request({"2330": _frame()}, step_days=4)
        unsorted = _frame().iloc[::-1]
        duplicate = _frame()
        duplicate.index = duplicate.index.where(np.arange(len(duplicate)) != 1, duplicate.index[0])
        for frame in (unsorted, duplicate):
            result = evaluate_universe_qualification(_request({"2330": frame}))
            self.assertFalse(result.qualification.request.metrics.data_leakage_free)
            self.assertEqual(result.symbols[0].error_code, "symbol_evaluation_failed")

    def test_train_test_overlap_is_rejected(self):
        frame = _frame()
        windows = [(1, frame.iloc[:10], frame.iloc[8:13])]
        with patch("tw_stock_tool.application.universe_qualification.split_windows", return_value=windows):
            result = evaluate_universe_qualification(_request({"2330": frame}))
        self.assertFalse(result.qualification.request.metrics.data_leakage_free)
        self.assertEqual(result.symbols[0].error_code, "symbol_evaluation_failed")

    def test_benchmark_uses_test_dates_and_fails_closed_when_shifted(self):
        shifted = _frame()
        shifted.index = shifted.index + pd.Timedelta(days=100)
        result = evaluate_universe_qualification(_request({"2330": _frame()}, shifted))
        self.assertFalse(result.qualification.request.metrics.benchmark_available)
        self.assertIsNotNone(result.symbols[0].windows[0].benchmark_error)

    def test_manifest_failure_and_partial_counts_and_window_provenance(self):
        with tempfile.TemporaryDirectory() as root:
            failed = run_universe_qualification(_request({"bad": pd.DataFrame()}), workspace_root=root)
            self.assertEqual((failed.manifest.status, failed.manifest.success_count, failed.manifest.failure_count, failed.manifest.partial_count), ("failure", 0, 1, 0))
            mixed = run_universe_qualification(_request({"good": _frame(), "bad": pd.DataFrame()}), workspace_root=root)
            self.assertEqual((mixed.manifest.status, mixed.manifest.success_count, mixed.manifest.failure_count, mixed.manifest.partial_count), ("partial", 1, 1, 0))
            self.assertTrue(all(source.source_kind == "provided" for source in mixed.manifest.data_sources))
            def fail_tests(frame, strategy, params, *args):
                if len(frame) == 5 and frame.index[0].day == 16:
                    raise RuntimeError("test failure")
                return {"Total Return %": 1.0, "Sharpe Ratio": 1.0, "Trade Count": 1, "Max Drawdown %": 0.0}
            with patch("tw_stock_tool.application.universe_qualification.run_strategy_backtest", side_effect=fail_tests):
                partial_window = run_universe_qualification(_request({"good": _frame()}), workspace_root=root)
            self.assertEqual((partial_window.manifest.status, partial_window.manifest.success_count, partial_window.manifest.failure_count, partial_window.manifest.partial_count), ("partial", 0, 0, 1))
            self.assertTrue(any("window=2:window_evaluation_failed:test failure" in error for error in partial_window.manifest.errors))

    def test_publication_rolls_back_on_reference_and_manifest_failure(self):
        with tempfile.TemporaryDirectory() as root:
            result = evaluate_universe_qualification(_request({"2330": _frame()}))
            for method in ("artifact_reference", "publish"):
                lifecycle = WorkspaceRunLifecycle.begin(root, "universe-oos-evaluation")
                patcher = patch.object(WorkspaceRunLifecycle, method, side_effect=RuntimeError(method))
                with patcher, self.assertRaises(RuntimeError):
                    publish_universe_qualification(result, lifecycle)
                self.assertFalse((lifecycle.artifacts_directory / "strategy_qualification.json").exists())
                self.assertFalse((lifecycle.artifacts_directory / "universe_oos_evidence.json").exists())

    def test_universe_evidence_strict_round_trip_and_rejection(self):
        result = evaluate_universe_qualification(_request({"2330": _frame()}))
        artifact = build_universe_oos_evidence(result)
        text = export_universe_oos_evidence_json(artifact)
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(load_universe_oos_evidence_json(text), artifact)
        payload = json.loads(text)
        payload["unknown"] = True
        with self.assertRaises(UniverseEvidenceSerializationError):
            deserialize_universe_oos_evidence(payload)
        with self.assertRaises(UniverseEvidenceSerializationError):
            load_universe_oos_evidence_json('{"schema_version":"1.0","schema_version":"1.0"}')
        with self.assertRaises(UniverseEvidenceSerializationError):
            load_universe_oos_evidence_json(text.replace("0.0", "NaN", 1))

    def test_parameter_neighborhood_stability_is_explicit(self):
        def fake_factory(neighbor_return):
            def fake(frame, strategy, params, *args):
                train = len(frame) == 10
                selected = params["short_window"] == 2
                value = 10.0 if train and selected else 1.0 if train else (2.0 if selected else neighbor_return)
                return {"Total Return %": value, "Sharpe Ratio": value, "Trade Count": 1, "Max Drawdown %": 0.0}
            return fake
        with patch("tw_stock_tool.application.universe_qualification.run_strategy_backtest", side_effect=fake_factory(1.0)):
            stable = evaluate_universe_qualification(_request({"2330": _frame()}))
        self.assertTrue(stable.symbols[0].windows[0].neighborhood_parameters)
        self.assertTrue(stable.symbols[0].windows[0].parameter_stable)
        with patch("tw_stock_tool.application.universe_qualification.run_strategy_backtest", side_effect=fake_factory(3.0)):
            unstable = evaluate_universe_qualification(_request({"2330": _frame()}))
        self.assertFalse(unstable.symbols[0].windows[0].parameter_stable)
        self.assertFalse(unstable.qualification.request.metrics.parameter_stable)

    def test_request_snapshots_inputs_and_source_ids(self):
        frame = _frame()
        options = {"short_window": [2, 3], "long_window": [4]}
        source_ids = (str(uuid4()), str(uuid4()))
        request = UniverseQualificationRequest(str(uuid4()), "2026-01-01T00:00:00Z", "ma_cross", {"2330": frame}, train_days=10, test_days=5, parameter_options=options, source_run_ids=tuple(reversed(source_ids)))
        result = evaluate_universe_qualification(request)
        frame.iloc[0, 0] = 999999
        options["short_window"].append(99)
        artifact = build_universe_oos_evidence(result)
        self.assertEqual(load_universe_oos_evidence_json(export_universe_oos_evidence_json(artifact)), artifact)
        self.assertEqual(tuple(sorted(source_ids)), request.source_run_ids)


if __name__ == "__main__":
    unittest.main()

import json
from collections.abc import Mapping
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
    UniverseQualificationError,
    CONCENTRATION_RULE,
    WindowEvidence,
    aggregate_universe_evidence,
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


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


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

    def test_failure_and_mixed_evidence_strict_round_trip(self):
        failed = evaluate_universe_qualification(_request({"bad": pd.DataFrame()}))
        failed_artifact = build_universe_oos_evidence(failed)
        self.assertEqual(load_universe_oos_evidence_json(export_universe_oos_evidence_json(failed_artifact)), failed_artifact)

        def fail_second_test(frame, strategy, params, *args):
            if len(frame) == 5 and frame.index[0].day == 16:
                raise RuntimeError("second test failed")
            return {"Total Return %": 1.0, "Sharpe Ratio": 1.0, "Trade Count": 1, "Max Drawdown %": 0.0}

        with patch("tw_stock_tool.application.universe_qualification.run_strategy_backtest", side_effect=fail_second_test):
            mixed = evaluate_universe_qualification(_request({"good": _frame(), "bad": pd.DataFrame()}))
        mixed_artifact = build_universe_oos_evidence(mixed)
        self.assertEqual(load_universe_oos_evidence_json(export_universe_oos_evidence_json(mixed_artifact)), mixed_artifact)
        self.assertFalse(next(item for item in mixed.symbols if item.symbol == "good").windows[-1].valid)

    def test_canonical_aggregation_rejects_forged_symbol_and_qualification_metrics(self):
        result = evaluate_universe_qualification(_request({"2330": _frame()}, _frame()))
        self.assertEqual(result.aggregate_metrics, aggregate_universe_evidence(result.symbols))
        payload = json.loads(export_universe_oos_evidence_json(build_universe_oos_evidence(result)))
        payload["symbols"][0]["oos_observations"] += 1
        with self.assertRaises(UniverseEvidenceSerializationError):
            deserialize_universe_oos_evidence(payload)
        payload = json.loads(export_universe_oos_evidence_json(build_universe_oos_evidence(result)))
        payload["qualification"]["request"]["metrics"]["oos_observations"] += 1
        with self.assertRaises(UniverseEvidenceSerializationError):
            deserialize_universe_oos_evidence(payload)

    def test_duplicate_windows_and_neighbor_contracts_are_rejected(self):
        result = evaluate_universe_qualification(_request({"2330": _frame()}, _frame()))
        payload = json.loads(export_universe_oos_evidence_json(build_universe_oos_evidence(result)))
        windows = payload["symbols"][0]["windows"]
        if len(windows) > 1:
            duplicate = dict(windows[1])
            duplicate["window"] = windows[0]["window"]
            windows.append(duplicate)
            with self.assertRaises(UniverseEvidenceSerializationError):
                deserialize_universe_oos_evidence(payload)
        payload = json.loads(export_universe_oos_evidence_json(build_universe_oos_evidence(result)))
        window = payload["symbols"][0]["windows"][0]
        window["neighborhood_errors"] = "not-a-list"
        with self.assertRaises(UniverseEvidenceSerializationError):
            deserialize_universe_oos_evidence(payload)
        payload = json.loads(export_universe_oos_evidence_json(build_universe_oos_evidence(result)))
        window = payload["symbols"][0]["windows"][0]
        window["neighborhood_returns_pct"] = []
        with self.assertRaises(UniverseEvidenceSerializationError):
            deserialize_universe_oos_evidence(payload)

    def test_parameter_stability_rule_handles_surface_cases(self):
        def fake_surface(selected_return, neighbor_return, fail_neighbor=False):
            def fake(frame, strategy, params, *args):
                train = len(frame) == 10
                selected = params["short_window"] == 2
                if fail_neighbor and not train and not selected:
                    raise RuntimeError("neighbor failed")
                value = 10.0 if train and selected else 1.0 if train else (selected_return if selected else neighbor_return)
                return {"Total Return %": value, "Sharpe Ratio": value, "Trade Count": 1, "Max Drawdown %": 0.0}
            return fake

        cases = ((10.0, 9.0, False, True), (10.0, -80.0, False, False), (-10.0, -80.0, False, False), (10.0, 9.0, True, False))
        for selected, neighbor, failed, expected in cases:
            with self.subTest(selected=selected, neighbor=neighbor, failed=failed), patch("tw_stock_tool.application.universe_qualification.run_strategy_backtest", side_effect=fake_surface(selected, neighbor, failed)):
                result = evaluate_universe_qualification(_request({"2330": _frame()}))
            self.assertEqual(result.symbols[0].windows[0].parameter_stable, expected)

    def test_provided_input_does_not_change_research_run_source_schema(self):
        with tempfile.TemporaryDirectory() as root:
            result = run_universe_qualification(_request({"2330": _frame()}), workspace_root=root)
        self.assertEqual(result.manifest.data_sources, ())
        self.assertTrue(result.manifest.config.workflow_options["provided_input"])
        self.assertFalse(result.manifest.config.auto_adjust)

    def test_cleanup_failure_surfaces_original_and_cleanup_paths(self):
        with tempfile.TemporaryDirectory() as root:
            result = evaluate_universe_qualification(_request({"2330": _frame()}))
            lifecycle = WorkspaceRunLifecycle.begin(root, "universe-oos-evaluation")
            with patch.object(WorkspaceRunLifecycle, "publish", side_effect=RuntimeError("publish failed")), patch.object(Path, "unlink", side_effect=OSError("unlink failed")):
                with self.assertRaisesRegex(UniverseQualificationError, "publication failed: publish failed; publication cleanup failed; possible orphaned paths"):
                    publish_universe_qualification(result, lifecycle)

    def test_json_chronology_and_cross_window_overlap_are_rejected(self):
        result = evaluate_universe_qualification(_request({"2330": _frame()}, _frame()))
        payload = json.loads(export_universe_oos_evidence_json(build_universe_oos_evidence(result)))
        first, second = payload["symbols"][0]["windows"][:2]
        first["train_start"] = "2020-01-01"
        with self.assertRaises(UniverseEvidenceSerializationError):
            deserialize_universe_oos_evidence(payload)
        payload = json.loads(export_universe_oos_evidence_json(build_universe_oos_evidence(result)))
        first, second = payload["symbols"][0]["windows"][:2]
        second["train_start"] = "2020-01-01T00:00:00Z"
        second["train_end"] = "2020-01-13T00:00:00Z"
        second["test_start"] = "2020-01-14T00:00:00Z"
        second["test_end"] = "2020-01-18T00:00:00Z"
        with self.assertRaises(UniverseEvidenceSerializationError):
            deserialize_universe_oos_evidence(payload)

    def test_stress_costs_must_be_strictly_higher(self):
        with self.assertRaises(ValueError):
            _request({"2330": _frame()}, fee_rate=0.001, tax_rate=0.001, stress_fee_rate=0.001, stress_tax_rate=0.001)
        with self.assertRaises(ValueError):
            _request({"2330": _frame()}, fee_rate=0.001, tax_rate=0.001, stress_fee_rate=0.0005, stress_tax_rate=0.002)
        request = _request({"2330": _frame()}, fee_rate=0.001, tax_rate=0.001, stress_fee_rate=0.001, stress_tax_rate=0.002)
        self.assertEqual((request.resolved_stress_fee_rate, request.resolved_stress_tax_rate), (0.001, 0.002))

    def test_invalid_price_rows_fail_closed_without_observations(self):
        invalid = _frame()
        invalid.iloc[10, invalid.columns.get_loc("Close")] = np.nan
        result = evaluate_universe_qualification(_request({"2330": invalid}))
        self.assertEqual(result.symbols[0].error_code, "symbol_evaluation_failed")
        self.assertEqual(result.aggregate_metrics.oos_observations, 0)

        invalid = _frame()
        invalid["Open"] = invalid["Open"].astype(object)
        invalid.iloc[10, invalid.columns.get_loc("Open")] = "not numeric"
        result = evaluate_universe_qualification(_request({"2330": invalid}))
        self.assertEqual(result.aggregate_metrics.oos_observations, 0)

    def test_exact_types_and_invalid_window_neighborhood_are_rejected(self):
        result = evaluate_universe_qualification(_request({"2330": _frame()}, _frame()))
        payload = json.loads(export_universe_oos_evidence_json(build_universe_oos_evidence(result)))
        symbol = payload["symbols"][0]
        symbol["oos_observations"] = True
        with self.assertRaises(UniverseEvidenceSerializationError):
            deserialize_universe_oos_evidence(payload)
        payload = json.loads(export_universe_oos_evidence_json(build_universe_oos_evidence(result)))
        payload["symbols"][0]["total_return_pct"] = True
        with self.assertRaises(UniverseEvidenceSerializationError):
            deserialize_universe_oos_evidence(payload)
        payload = json.loads(export_universe_oos_evidence_json(build_universe_oos_evidence(result)))
        payload["resolved_configuration"]["parameter_stability_rule"]["minimum_neighbor_coverage"] = True
        with self.assertRaises(UniverseEvidenceSerializationError):
            deserialize_universe_oos_evidence(payload)

        def fail_second(frame, strategy, params, *args):
            if len(frame) == 5 and frame.index[0].day == 16:
                raise RuntimeError("typed failure")
            return {"Total Return %": 1.0, "Sharpe Ratio": 1.0, "Trade Count": 1, "Max Drawdown %": 0.0}

        with patch("tw_stock_tool.application.universe_qualification.run_strategy_backtest", side_effect=fail_second):
            partial = evaluate_universe_qualification(_request({"2330": _frame()}))
        payload = json.loads(export_universe_oos_evidence_json(build_universe_oos_evidence(partial)))
        invalid = payload["symbols"][0]["windows"][1]
        invalid["neighborhood_parameters"] = [{"long_window": 4, "short_window": 3}]
        invalid["neighborhood_returns_pct"] = [None]
        invalid["neighborhood_errors"] = ["should be empty"]
        with self.assertRaises(UniverseEvidenceSerializationError):
            deserialize_universe_oos_evidence(payload)

    def test_resolved_configuration_round_trip_and_manifest_consistency(self):
        source_ids = (str(uuid4()), str(uuid4()))
        benchmark = _frame(close=np.arange(10.0, 30.0))
        request = _request({"2330": _frame()}, benchmark, source_run_ids=source_ids, auto_adjust=True, fee_rate=0.001, tax_rate=0.001, stress_fee_rate=0.001, stress_tax_rate=0.002, stop_loss_pct=2.0, take_profit_pct=3.0, max_hold_days=4, position_size=0.5)
        result = evaluate_universe_qualification(request)
        artifact = build_universe_oos_evidence(result)
        loaded = load_universe_oos_evidence_json(export_universe_oos_evidence_json(artifact))
        self.assertEqual(loaded.resolved_configuration, artifact.resolved_configuration)
        self.assertEqual(loaded.resolved_configuration.source_run_ids, request.source_run_ids)
        self.assertEqual(loaded.qualification.request.strategy.parameters["resolved_configuration"], artifact.qualification.request.strategy.parameters["resolved_configuration"])
        with tempfile.TemporaryDirectory() as root:
            published = run_universe_qualification(request, workspace_root=root)
        manifest_config = published.manifest.config.walk_forward
        self.assertEqual(_plain(manifest_config), artifact.resolved_configuration.to_payload())
        self.assertEqual(_plain(published.manifest.config.workflow_options["resolved_configuration"]), artifact.resolved_configuration.to_payload())
        self.assertEqual(list(published.manifest.config.workflow_options["resolved_configuration"]["source_run_ids"]), list(request.source_run_ids))
        self.assertEqual(dict(artifact.resolved_configuration.concentration_rule), dict(CONCENTRATION_RULE))

    def test_concentration_uses_non_cancelling_window_basis(self):
        def fake(frame, strategy, params, *args):
            if len(frame) == 10:
                value = 1.0
            elif frame["Close"].iloc[0] > 50:
                value = 1.0
            elif frame.index[0].day == 11:
                value = 10.0
            elif frame.index[0].day == 16:
                value = -10.0
            else:
                value = 1.0
            return {"Total Return %": value, "Sharpe Ratio": value, "Trade Count": 1, "Max Drawdown %": 0.0}

        with patch("tw_stock_tool.application.universe_qualification.run_strategy_backtest", side_effect=fake):
            result = evaluate_universe_qualification(_request({"a": _frame(), "b": _frame(close=np.arange(101.0, 121.0))}, _frame()))
        self.assertGreater(result.aggregate_metrics.symbol_concentration_pct, 80.0)
        self.assertEqual(dict(result.qualification.request.strategy.parameters["resolved_configuration"]["concentration_rule"]), dict(CONCENTRATION_RULE))

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

import unittest
from pathlib import Path
import sys
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tw_stock_tool.reports import daily_pipeline, daily_report


class RunConfigurationSnapshotTest(unittest.TestCase):
    def test_default_snapshot_is_ordered_and_scalar(self):
        snapshot = daily_pipeline.build_daily_pipeline_run_configuration(
            daily_pipeline.DailyPipelineConfig()
        )

        expected = {
            "Period": "1y",
            "Interval": "1d",
            "Signals": "BUY, WATCH",
            "Minimum Score": 4.0,
            "Candidate Top": 20,
            "Auto Adjust": False,
            "Force Refresh": False,
            "Backtest Enabled": False,
            "Backtest Top": 0,
            "Validation Strategy": "ma_cross",
            "Initial Capital": 100000,
            "Fee Rate": 0.001425,
            "Tax Rate": 0.003,
            "Position Size": 1.0,
            "Parameter Sweep Enabled": False,
            "Parameter Sweep Top": 0,
            "Parameter Sweep Sort By": "Sharpe Ratio",
            "Walk Forward Enabled": False,
            "Walk Forward Top": 0,
            "Train Days": 126,
            "Test Days": 63,
            "Effective Step Days": 63,
            "Walk Forward Sort By": "Train Sharpe Ratio",
        }
        self.assertEqual(snapshot, expected)
        self.assertEqual(list(snapshot), list(expected))
        self.assertEqual(snapshot["Signals"], "BUY, WATCH")
        self.assertEqual(snapshot["Candidate Top"], 20)
        self.assertIs(snapshot["Auto Adjust"], False)
        self.assertIs(snapshot["Backtest Enabled"], False)
        self.assertEqual(snapshot["Effective Step Days"], 63)
        for value in snapshot.values():
            self.assertNotIsInstance(value, (pd.DataFrame, pd.Series, dict, list))

    def test_custom_snapshot_preserves_none_and_explicit_step_days(self):
        config = daily_pipeline.DailyPipelineConfig(
            period="2y", interval="1wk", signals=("BUY",), top=None,
            auto_adjust=True, force_refresh=True, validate_top=4,
            validation_strategy="score", validation_initial_capital=200000,
            validation_fee_rate=0.001, validation_tax_rate=0.002,
            validation_position_size=0.5, parameter_sweep_top=3,
            parameter_sweep_sort_by="CAGR %", walk_forward_top=2,
            walk_forward_train_days=100, walk_forward_test_days=20,
            walk_forward_step_days=10, walk_forward_sort_by="Train CAGR %",
        )
        snapshot = daily_pipeline.build_daily_pipeline_run_configuration(config)
        expected = {
            "Period": "2y", "Interval": "1wk", "Signals": "BUY",
            "Minimum Score": 4.0, "Candidate Top": None,
            "Auto Adjust": True, "Force Refresh": True,
            "Backtest Enabled": True, "Backtest Top": 4,
            "Validation Strategy": "score", "Initial Capital": 200000,
            "Fee Rate": 0.001, "Tax Rate": 0.002, "Position Size": 0.5,
            "Parameter Sweep Enabled": True, "Parameter Sweep Top": 3,
            "Parameter Sweep Sort By": "CAGR %",
            "Walk Forward Enabled": True, "Walk Forward Top": 2,
            "Train Days": 100, "Test Days": 20, "Effective Step Days": 10,
            "Walk Forward Sort By": "Train CAGR %",
        }
        self.assertEqual(snapshot, expected)
        self.assertEqual(list(snapshot), list(expected))
        self.assertIsNone(snapshot["Candidate Top"])
        self.assertEqual(snapshot["Signals"], "BUY")
        self.assertIs(snapshot["Auto Adjust"], True)
        self.assertIs(snapshot["Force Refresh"], True)
        self.assertIs(snapshot["Backtest Enabled"], True)
        self.assertIs(snapshot["Parameter Sweep Enabled"], True)
        self.assertIs(snapshot["Walk Forward Enabled"], True)
        self.assertEqual(snapshot["Effective Step Days"], 10)

    def test_snapshot_validation_is_pure(self):
        config = daily_pipeline.DailyPipelineConfig(parameter_sweep_top=1)
        with patch.object(daily_pipeline, "AnalysisSession") as session:
            with self.assertRaisesRegex(ValueError, "parameter-sweep-top"):
                daily_pipeline.build_daily_pipeline_run_configuration(config)
        session.assert_not_called()



    def test_snapshot_builder_is_pure_for_valid_config(self):
        config = daily_pipeline.DailyPipelineConfig()
        with patch.object(daily_pipeline, "AnalysisSession") as session, \
             patch.object(daily_pipeline, "run_daily_report") as scan, \
             patch.object(daily_pipeline, "run_candidate_backtest_validation") as backtest, \
             patch.object(daily_pipeline, "run_candidate_parameter_sweep_validation") as sweep, \
             patch.object(daily_pipeline, "run_candidate_walk_forward_validation") as walk_forward, \
             patch.object(daily_pipeline, "build_daily_report_data") as build, \
             patch.object(daily_pipeline, "render_daily_report_markdown") as render:
            snapshot = daily_pipeline.build_daily_pipeline_run_configuration(config)

        self.assertEqual(snapshot, {
            "Period": "1y", "Interval": "1d", "Signals": "BUY, WATCH",
            "Minimum Score": 4.0, "Candidate Top": 20,
            "Auto Adjust": False, "Force Refresh": False,
            "Backtest Enabled": False, "Backtest Top": 0,
            "Validation Strategy": "ma_cross", "Initial Capital": 100000,
            "Fee Rate": 0.001425, "Tax Rate": 0.003, "Position Size": 1.0,
            "Parameter Sweep Enabled": False, "Parameter Sweep Top": 0,
            "Parameter Sweep Sort By": "Sharpe Ratio",
            "Walk Forward Enabled": False, "Walk Forward Top": 0,
            "Train Days": 126, "Test Days": 63, "Effective Step Days": 63,
            "Walk Forward Sort By": "Train Sharpe Ratio",
        })
        session.assert_not_called()
        scan.assert_not_called()
        backtest.assert_not_called()
        sweep.assert_not_called()
        walk_forward.assert_not_called()
        build.assert_not_called()
        render.assert_not_called()

    def test_pipeline_forwards_exact_snapshot_and_calls_builder_once(self):
        config = daily_pipeline.DailyPipelineConfig(progress=False)
        expected_snapshot = daily_pipeline.build_daily_pipeline_run_configuration(config)
        summary = pd.DataFrame([{"Stocks Scanned": 1}])
        candidates = pd.DataFrame()
        ranking = pd.DataFrame([{"Stock": "2330", "Status": "OK"}])
        captured = {}

        with patch.object(
            daily_pipeline,
            "build_daily_pipeline_run_configuration",
            return_value=expected_snapshot,
        ) as snapshot_builder, patch.object(
            daily_pipeline,
            "run_daily_report",
            return_value=(summary, candidates, ranking, None),
        ), patch.object(
            daily_pipeline,
            "build_daily_report_data",
            side_effect=lambda **kwargs: captured.update(kwargs)
            or {"Run Configuration": dict(kwargs["run_configuration"])},
        ), patch.object(
            daily_pipeline,
            "render_daily_report_markdown",
            return_value="# report",
        ):
            result = daily_pipeline.run_daily_research_pipeline(["2330"], config)

        snapshot_builder.assert_called_once_with(config)
        self.assertEqual(captured["run_configuration"], expected_snapshot)
        self.assertEqual(result.report_data["Run Configuration"], expected_snapshot)

    def test_pipeline_does_not_mutate_stage_inputs(self):
        config = daily_pipeline.DailyPipelineConfig(
            validate_top=1,
            parameter_sweep_top=1,
            walk_forward_top=1,
            progress=False,
        )
        summary = pd.DataFrame([{"Stocks Scanned": 1}])
        ranking = pd.DataFrame([{"Stock": "2330", "Status": "OK"}])
        candidates = pd.DataFrame([{"Stock": "2330", "Status": "OK"}])
        backtest = pd.DataFrame([{"Stock": "2330", "Status": "OK"}])
        sweep = pd.DataFrame([{"Stock": "2330", "Status": "OK"}])
        walk_forward = pd.DataFrame([{"Stock": "2330", "Status": "OK"}])
        backtest_limits = ["backtest limit"]
        sweep_limits = ["sweep limit"]
        walk_forward_limits = ["walk-forward limit"]

        config_before = config
        candidates_before = candidates.copy(deep=True)
        backtest_before = backtest.copy(deep=True)
        sweep_before = sweep.copy(deep=True)
        walk_forward_before = walk_forward.copy(deep=True)
        backtest_limits_before = list(backtest_limits)
        sweep_limits_before = list(sweep_limits)
        walk_forward_limits_before = list(walk_forward_limits)
        captured = {}

        with patch.object(
            daily_pipeline,
            "run_daily_report",
            return_value=(summary, candidates, ranking, None),
        ), patch.object(
            daily_pipeline,
            "run_candidate_backtest_validation",
            return_value=(backtest, backtest_limits),
        ), patch.object(
            daily_pipeline,
            "run_candidate_parameter_sweep_validation",
            return_value=(sweep, sweep_limits),
        ), patch.object(
            daily_pipeline,
            "run_candidate_walk_forward_validation",
            return_value=(walk_forward, walk_forward_limits),
        ), patch.object(
            daily_pipeline,
            "build_daily_pipeline_run_configuration",
            return_value={},
        ), patch.object(
            daily_pipeline,
            "build_daily_report_data",
            side_effect=lambda **kwargs: captured.update(kwargs) or {},
        ), patch.object(
            daily_pipeline,
            "render_daily_report_markdown",
            return_value="# report",
        ):
            daily_pipeline.run_daily_research_pipeline(["2330"], config)

        self.assertEqual(config, config_before)
        pd.testing.assert_frame_equal(candidates, candidates_before)
        pd.testing.assert_frame_equal(backtest, backtest_before)
        pd.testing.assert_frame_equal(sweep, sweep_before)
        pd.testing.assert_frame_equal(walk_forward, walk_forward_before)
        self.assertEqual(backtest_limits, backtest_limits_before)
        self.assertEqual(sweep_limits, sweep_limits_before)
        self.assertEqual(walk_forward_limits, walk_forward_limits_before)
        self.assertEqual(captured["risk_notes"], [
            "Candidate backtests use historical data and next-bar Open execution assumptions; "
            "historical results do not predict future performance.",
            "Parameter sweep results are historical in-sample search summaries across multiple parameter combinations. "
            "The displayed best result may reflect overfitting, does not change candidate ranking, is not passed into "
            "walk-forward validation, and does not predict future performance.",
            "Walk-forward results are historical out-of-sample research estimates. Parameters are selected on training windows and evaluated on later test windows; results do not predict future performance. Window fields represent observations (rows) in the current engine.",
        ])
        self.assertEqual(captured["data_limitations"], [
            "backtest limit", "sweep limit", "walk-forward limit",
        ])
class RunConfigurationReportTest(unittest.TestCase):
    def test_builder_copies_configuration_and_supports_none(self):
        config = {"Period": "2y", "Signals": "BUY, WATCH"}
        report = daily_report.build_daily_report_data(run_configuration=config)
        config["Period"] = "changed"
        self.assertEqual(report["Run Configuration"]["Period"], "2y")
        self.assertEqual(daily_report.build_daily_report_data()["Run Configuration"], {})

    def test_markdown_renders_configuration_in_order(self):
        report = daily_report.build_daily_report_data(
            run_configuration={
                "Period": "2y", "Interval": "1wk", "Signals": "BUY, WATCH",
                "Backtest Enabled": True, "Parameter Sweep Enabled": True,
                "Walk Forward Enabled": True, "Effective Step Days": 10,
            }
        )
        markdown = daily_report.render_daily_report_markdown(report)
        self.assertLess(markdown.index("## Report Metadata"), markdown.index("## Run Configuration"))
        self.assertLess(markdown.index("## Run Configuration"), markdown.index("## Report Highlights"))
        self.assertIn("- **Period**: 2y", markdown)
        self.assertIn("- **Backtest Enabled**: True", markdown)
        self.assertIn("- **Parameter Sweep Enabled**: True", markdown)
        self.assertIn("- **Walk Forward Enabled**: True", markdown)
        self.assertEqual(markdown.count("## Run Configuration"), 1)


class RunConfigurationPipelineTest(unittest.TestCase):
    def test_pipeline_forwards_snapshot_after_validation_stages(self):
        config = daily_pipeline.DailyPipelineConfig(progress=False)
        summary = pd.DataFrame([{"Stocks Scanned": 1}])
        candidates = pd.DataFrame()
        ranking = pd.DataFrame([{"Stock": "2330", "Status": "OK"}])
        captured = {}
        with patch.object(daily_pipeline, "run_daily_report", return_value=(summary, candidates, ranking, None)), \
             patch.object(daily_pipeline, "build_daily_report_data", side_effect=lambda **kwargs: captured.update(kwargs) or {"Run Configuration": dict(kwargs["run_configuration"])}), \
             patch.object(daily_pipeline, "render_daily_report_markdown", return_value="# report"):
            result = daily_pipeline.run_daily_research_pipeline(["2330"], config)

        self.assertEqual(captured["run_configuration"], result.report_data["Run Configuration"])
        self.assertEqual(result.report_data["Run Configuration"], captured["run_configuration"])
        self.assertEqual(list(daily_pipeline.DailyPipelineResult.__dataclass_fields__), [
            "summary_df", "candidates_df", "ranking_df", "backtest_highlights",
            "parameter_sweep_highlights", "walk_forward_highlights", "risk_notes",
            "data_limitations", "report_data", "markdown",
        ])


if __name__ == "__main__":
    unittest.main()

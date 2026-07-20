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

        self.assertEqual(list(snapshot), [
            "Period", "Interval", "Signals", "Minimum Score", "Candidate Top",
            "Auto Adjust", "Force Refresh", "Backtest Enabled", "Backtest Top",
            "Validation Strategy", "Initial Capital", "Fee Rate", "Tax Rate",
            "Position Size", "Parameter Sweep Enabled", "Parameter Sweep Top",
            "Parameter Sweep Sort By", "Walk Forward Enabled", "Walk Forward Top",
            "Train Days", "Test Days", "Effective Step Days", "Walk Forward Sort By",
        ])
        self.assertEqual(snapshot["Signals"], "BUY, WATCH")
        self.assertEqual(snapshot["Candidate Top"], 20)
        self.assertEqual(snapshot["Auto Adjust"], "No")
        self.assertEqual(snapshot["Backtest Enabled"], "No")
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
        self.assertEqual(snapshot["Candidate Top"], "All")
        self.assertEqual(snapshot["Signals"], "BUY")
        self.assertEqual(snapshot["Auto Adjust"], "Yes")
        self.assertEqual(snapshot["Force Refresh"], "Yes")
        self.assertEqual(snapshot["Backtest Enabled"], "Yes")
        self.assertEqual(snapshot["Parameter Sweep Enabled"], "Yes")
        self.assertEqual(snapshot["Walk Forward Enabled"], "Yes")
        self.assertEqual(snapshot["Effective Step Days"], 10)

    def test_snapshot_validation_is_pure(self):
        config = daily_pipeline.DailyPipelineConfig(parameter_sweep_top=1)
        with patch.object(daily_pipeline, "AnalysisSession") as session:
            with self.assertRaisesRegex(ValueError, "parameter-sweep-top"):
                daily_pipeline.build_daily_pipeline_run_configuration(config)
        session.assert_not_called()


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
                "Backtest Enabled": "Yes", "Effective Step Days": 10,
            }
        )
        markdown = daily_report.render_daily_report_markdown(report)
        self.assertLess(markdown.index("## Report Metadata"), markdown.index("## Run Configuration"))
        self.assertLess(markdown.index("## Run Configuration"), markdown.index("## Report Highlights"))
        self.assertIn("- **Period**: 2y", markdown)
        self.assertIn("- **Backtest Enabled**: Yes", markdown)


class RunConfigurationPipelineTest(unittest.TestCase):
    def test_pipeline_forwards_snapshot_after_validation_stages(self):
        config = daily_pipeline.DailyPipelineConfig(progress=False)
        summary = pd.DataFrame([{"Stocks Scanned": 1}])
        candidates = pd.DataFrame()
        ranking = pd.DataFrame([{"Stock": "2330", "Status": "OK"}])
        captured = {}
        with patch.object(daily_pipeline, "run_daily_report", return_value=(summary, candidates, ranking, None)), \
             patch.object(daily_pipeline, "build_daily_report_data", side_effect=lambda **kwargs: captured.update(kwargs) or {}), \
             patch.object(daily_pipeline, "render_daily_report_markdown", return_value="# report"):
            result = daily_pipeline.run_daily_research_pipeline(["2330"], config)

        self.assertEqual(captured["run_configuration"], result.run_configuration)
        self.assertEqual(result.report_data, {})
        self.assertEqual(result.run_configuration["Effective Step Days"], 63)


if __name__ == "__main__":
    unittest.main()

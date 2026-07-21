import unittest
from unittest.mock import Mock, patch
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tw_stock_tool.reports import daily_pipeline
from tw_stock_tool.analysis import analysis_session


class DailyPipelineConfigTest(unittest.TestCase):
    def test_defaults_are_immutable_and_match_cli_values(self):
        config = daily_pipeline.DailyPipelineConfig()
        self.assertEqual(config.signals, ("BUY", "WATCH"))
        self.assertIsInstance(config.signals, tuple)
        with self.assertRaises(Exception):
            config.signals += ("SELL",)

    def test_list_input_is_copied_and_normalized(self):
        signals = ["BUY", "WATCH"]
        config = daily_pipeline.DailyPipelineConfig(signals=signals)
        signals.append("SELL")
        self.assertEqual(config.signals, ("BUY", "WATCH"))

    def test_invalid_signal_values_are_rejected(self):
        for signals in (None, "BUY", [""], [1], ["BUY", " "]):
            with self.subTest(signals=signals):
                with self.assertRaisesRegex(ValueError, "signals must be an iterable"):
                    daily_pipeline.DailyPipelineConfig(signals=signals)

    def test_dependencies_and_finite_values_are_rejected(self):
        invalid = [
            daily_pipeline.DailyPipelineConfig(parameter_sweep_top=1),
            daily_pipeline.DailyPipelineConfig(validate_top=1, parameter_sweep_top=2),
            daily_pipeline.DailyPipelineConfig(validate_top=1, parameter_sweep_top=1, validation_strategy="macd"),
            daily_pipeline.DailyPipelineConfig(validate_top=1, parameter_sweep_top=1, parameter_sweep_sort_by="bad"),
            daily_pipeline.DailyPipelineConfig(validate_top=1, walk_forward_top=1, validation_strategy="macd"),
            daily_pipeline.DailyPipelineConfig(validate_top=1, walk_forward_top=1, walk_forward_sort_by="bad"),
            daily_pipeline.DailyPipelineConfig(validation_initial_capital=float("nan")),
            daily_pipeline.DailyPipelineConfig(validation_fee_rate=float("inf")),
            daily_pipeline.DailyPipelineConfig(validation_position_size=True),
            daily_pipeline.DailyPipelineConfig(walk_forward_train_days=0),
        ]
        for config in invalid:
            with self.subTest(config=config):
                with self.assertRaises(ValueError):
                    daily_pipeline.validate_daily_pipeline_config(config)

    def test_validation_does_not_call_external_services(self):
        with patch.object(daily_pipeline, "AnalysisSession") as session:
            daily_pipeline.validate_daily_pipeline_config(daily_pipeline.DailyPipelineConfig())
        session.assert_not_called()


class DailyPipelineRunnerTest(unittest.TestCase):
    def setUp(self):
        self.config = daily_pipeline.DailyPipelineConfig(
            validate_top=1,
            parameter_sweep_top=1,
            walk_forward_top=1,
            report_date="2025-01-02",
            progress=False,
        )
        self.summary = pd.DataFrame([{"Stocks Scanned": 1}])
        self.candidates = pd.DataFrame([{"Stock": "2330"}])
        self.ranking = pd.DataFrame([{"Stock": "2330", "Status": "OK"}])
        self.backtest = pd.DataFrame([{"Stock": "2330", "Status": "OK"}])
        self.sweep = pd.DataFrame([{"Stock": "2330", "Status": "ERROR"}])
        self.walk_forward = pd.DataFrame([{"Stock": "2330", "Status": "OK"}])

    def test_full_stage_order_result_and_messages(self):
        events = []
        provider = Mock(name="provider")
        order = []

        def scan(**kwargs):
            order.append("scan")
            self.assertIs(kwargs["analysis_provider"], provider)
            return self.summary, self.candidates, self.ranking, None

        def backtest(*args, **kwargs):
            order.append("backtest")
            self.assertIs(kwargs["analysis_provider"], provider)
            return self.backtest, ["backtest limit"]

        def sweep(*args, **kwargs):
            order.append("sweep")
            self.assertIs(kwargs["analysis_provider"], provider)
            return self.sweep, ["sweep limit"]

        def walk_forward(*args, **kwargs):
            order.append("walk-forward")
            self.assertIs(kwargs["analysis_provider"], provider)
            return self.walk_forward, ["walk limit"]

        def build(**kwargs):
            order.append("build")
            self.assertEqual(kwargs["report_date"], "2025-01-02")
            return {"Report Metadata": {"Date": "2025-01-02"}}

        with patch.object(daily_pipeline, "run_daily_report", side_effect=scan), \
             patch.object(daily_pipeline, "run_candidate_backtest_validation", side_effect=backtest), \
             patch.object(daily_pipeline, "run_candidate_parameter_sweep_validation", side_effect=sweep), \
             patch.object(daily_pipeline, "run_candidate_walk_forward_validation", side_effect=walk_forward), \
             patch.object(daily_pipeline, "build_daily_pipeline_run_configuration", side_effect=lambda config: order.append("configuration") or {"Period": config.period}), \
             patch.object(daily_pipeline, "build_daily_report_data", side_effect=build), \
             patch.object(daily_pipeline, "render_daily_report_markdown", side_effect=lambda data: order.append("render") or "# report"):
            result = daily_pipeline.run_daily_research_pipeline(
                (stock for stock in ["2330"]), self.config,
                analysis_provider=provider,
                status_callback=events.append,
            )

        self.assertEqual(order, ["scan", "backtest", "sweep", "walk-forward", "configuration", "build", "render"])
        self.assertEqual(result.markdown, "# report")
        self.assertIs(result.parameter_sweep_highlights, self.sweep)
        self.assertIs(result.walk_forward_highlights, self.walk_forward)
        self.assertEqual(result.data_limitations, ["backtest limit", "sweep limit", "walk limit"])
        self.assertTrue(any("Scanning" in message for message in events))
        self.assertTrue(any("Parameter sweep completed" in message for message in events))
        self.assertTrue(any("Walk-forward validation completed" in message for message in events))

    def test_report_date_empty_string_is_preserved(self):
        captured = {}
        with patch.object(
            daily_pipeline,
            "run_daily_report",
            return_value=(self.summary, self.candidates, self.ranking, None),
        ), patch.object(
            daily_pipeline, "build_daily_report_data", side_effect=lambda **kwargs: captured.update(kwargs) or {}
        ), patch.object(daily_pipeline, "render_daily_report_markdown", return_value="# report"):
            daily_pipeline.run_daily_research_pipeline(["2330"], daily_pipeline.DailyPipelineConfig(report_date=""))
        self.assertEqual(captured["report_date"], "")

    def test_report_date_none_uses_current_date(self):
        captured = {}
        with patch.object(
            daily_pipeline,
            "run_daily_report",
            return_value=(self.summary, self.candidates, self.ranking, None),
        ), patch.object(
            daily_pipeline, "build_daily_report_data", side_effect=lambda **kwargs: captured.update(kwargs) or {}
        ), patch.object(daily_pipeline, "render_daily_report_markdown", return_value="# report"), patch.object(
            daily_pipeline, "datetime"
        ) as clock:
            clock.now.return_value.strftime.return_value = "2026-07-20"
            daily_pipeline.run_daily_research_pipeline(["2330"], daily_pipeline.DailyPipelineConfig())
        self.assertEqual(captured["report_date"], "2026-07-20")

    def test_disabled_stages_have_required_empty_schemas_and_callback_none_is_quiet(self):
        with patch.object(
            daily_pipeline,
            "run_daily_report",
            return_value=(self.summary, self.candidates, self.ranking, None),
        ) as scan, patch.object(daily_pipeline, "build_daily_report_data", return_value={}), patch.object(
            daily_pipeline, "render_daily_report_markdown", return_value="# report"
        ) as render:
            result = daily_pipeline.run_daily_research_pipeline(["2330"], daily_pipeline.DailyPipelineConfig())
        scan.assert_called_once()
        render.assert_called_once()
        self.assertEqual(result.backtest_highlights.columns.tolist(), daily_pipeline.BACKTEST_HIGHLIGHT_COLUMNS)
        self.assertEqual(result.parameter_sweep_highlights.columns.tolist(), daily_pipeline.PARAMETER_SWEEP_HIGHLIGHT_COLUMNS)
        self.assertEqual(result.walk_forward_highlights.columns.tolist(), daily_pipeline.WALK_FORWARD_HIGHLIGHT_COLUMNS)

    def test_fatal_stage_errors_propagate(self):
        with patch.object(daily_pipeline, "run_daily_report", side_effect=RuntimeError("scan failed")):
            with self.assertRaisesRegex(RuntimeError, "scan failed"):
                daily_pipeline.run_daily_research_pipeline(["2330"], daily_pipeline.DailyPipelineConfig())

    def test_report_builder_error_propagates_and_skips_renderer(self):
        with patch.object(
            daily_pipeline,
            "run_daily_report",
            return_value=(self.summary, self.candidates, self.ranking, None),
        ), patch.object(daily_pipeline, "build_daily_report_data", side_effect=RuntimeError("build failed")), patch.object(
            daily_pipeline, "render_daily_report_markdown"
        ) as render:
            with self.assertRaisesRegex(RuntimeError, "build failed"):
                daily_pipeline.run_daily_research_pipeline(["2330"], daily_pipeline.DailyPipelineConfig())
        render.assert_not_called()

    def test_renderer_error_propagates(self):
        with patch.object(
            daily_pipeline,
            "run_daily_report",
            return_value=(self.summary, self.candidates, self.ranking, None),
        ), patch.object(daily_pipeline, "build_daily_report_data", return_value={}), patch.object(
            daily_pipeline, "render_daily_report_markdown", side_effect=RuntimeError("render failed")
        ):
            with self.assertRaisesRegex(RuntimeError, "render failed"):
                daily_pipeline.run_daily_research_pipeline(["2330"], daily_pipeline.DailyPipelineConfig())

    def test_empty_stock_iterable_is_rejected_before_provider(self):
        provider = Mock()
        with self.assertRaisesRegex(ValueError, "No stocks provided"):
            daily_pipeline.run_daily_research_pipeline([], daily_pipeline.DailyPipelineConfig(), analysis_provider=provider)
        provider.assert_not_called()

    def test_default_session_provider_is_shared_by_all_enabled_stages(self):
        provider = Mock(name="session_get")
        session = Mock()
        session.get = provider
        kwargs_seen = []
        with patch.object(daily_pipeline, "AnalysisSession", return_value=session), patch.object(
            daily_pipeline,
            "run_daily_report",
            return_value=(self.summary, self.candidates, self.ranking, None),
        ), patch.object(daily_pipeline, "run_candidate_backtest_validation", return_value=(self.backtest, []), side_effect=lambda *a, **kw: (kwargs_seen.append(kw["analysis_provider"]) or (self.backtest, []))), patch.object(
            daily_pipeline, "run_candidate_parameter_sweep_validation", return_value=(self.sweep, []), side_effect=lambda *a, **kw: (kwargs_seen.append(kw["analysis_provider"]) or (self.sweep, []))
        ), patch.object(daily_pipeline, "run_candidate_walk_forward_validation", return_value=(self.walk_forward, []), side_effect=lambda *a, **kw: (kwargs_seen.append(kw["analysis_provider"]) or (self.walk_forward, []))), patch.object(
            daily_pipeline, "build_daily_report_data", return_value={}
        ), patch.object(daily_pipeline, "render_daily_report_markdown", return_value="# report"):
            daily_pipeline.run_daily_research_pipeline(["2330"], self.config)
        self.assertEqual(len(kwargs_seen), 3)
        self.assertTrue(all(item is provider for item in kwargs_seen))

    def test_complete_pipeline_reuses_underlying_analyzer_with_force_refresh(self):
        for force_refresh in (False, True):
            with self.subTest(force_refresh=force_refresh):
                analyzer = Mock(return_value=Mock())
                config = daily_pipeline.DailyPipelineConfig(
                    validate_top=1,
                    parameter_sweep_top=1,
                    walk_forward_top=1,
                    force_refresh=force_refresh,
                    progress=False,
                )

                def use_provider(**kwargs):
                    kwargs["analysis_provider"]("2330")

                def scan(**kwargs):
                    use_provider(**kwargs)
                    return self.summary, self.candidates, self.ranking, None

                with patch.object(analysis_session, "analyze_stock", analyzer), patch.object(
                    daily_pipeline, "run_daily_report", side_effect=scan
                ), patch.object(
                    daily_pipeline,
                    "run_candidate_backtest_validation",
                    side_effect=lambda *args, **kwargs: (use_provider(**kwargs) or (self.backtest, [])),
                ), patch.object(
                    daily_pipeline,
                    "run_candidate_parameter_sweep_validation",
                    side_effect=lambda *args, **kwargs: (use_provider(**kwargs) or (self.sweep, [])),
                ), patch.object(
                    daily_pipeline,
                    "run_candidate_walk_forward_validation",
                    side_effect=lambda *args, **kwargs: (use_provider(**kwargs) or (self.walk_forward, [])),
                ), patch.object(daily_pipeline, "build_daily_report_data", return_value={}), patch.object(
                    daily_pipeline, "render_daily_report_markdown", return_value="# report"
                ):
                    daily_pipeline.run_daily_research_pipeline(["2330"], config)

                self.assertEqual(analyzer.call_count, 1)
                self.assertEqual(analyzer.call_args.kwargs["force_refresh"], force_refresh)


if __name__ == "__main__":
    unittest.main()

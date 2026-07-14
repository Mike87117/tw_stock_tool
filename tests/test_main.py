from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd

import main


class MainCliTest(unittest.TestCase):
    def test_cli_options_parse_stock_and_backtest_params(self) -> None:
        options = main._cli_options(
            [
                "--stock",
                "2330",
                "--period",
                "2y",
                "--interval",
                "1d",
                "--force-refresh",
                "--stop-loss",
                "8",
                "--take-profit",
                "20",
                "--max-hold-days",
                "30",
                "--position-size",
                "0.5",
                "--export-excel",
                "--save-chart",
            ]
        )

        self.assertEqual(options.stock_id, "2330")
        self.assertEqual(options.period, "2y")
        self.assertTrue(options.force_refresh)
        self.assertEqual(options.stop_loss_pct, 8)
        self.assertEqual(options.take_profit_pct, 20)
        self.assertEqual(options.max_hold_days, 30)
        self.assertEqual(options.position_size, 0.5)
        self.assertTrue(options.export_excel)
        self.assertTrue(options.save_chart)

    def test_cli_mode_calls_run_analysis(self) -> None:
        with patch.object(main, "run_analysis") as run_analysis:
            status = main.main(["--stock", "2330", "--period", "1y"])

        self.assertEqual(status, 0)
        run_analysis.assert_called_once()
        options = run_analysis.call_args.args[0]
        self.assertEqual(options.stock_id, "2330")
        self.assertEqual(options.period, "1y")

    def test_no_args_uses_interactive_mode(self) -> None:
        fake_options = main.MainOptions(stock_id="2330")
        with patch.object(main, "_interactive_options", return_value=fake_options) as interactive:
            with patch.object(main, "run_analysis") as run_analysis:
                status = main.main([])

        self.assertEqual(status, 0)
        interactive.assert_called_once()
        run_analysis.assert_called_once_with(fake_options)

    def test_run_analysis_result_propagates_weekly_interval(self) -> None:
        signal_df = pd.DataFrame(
            {"Open": [100.0], "Close": [100.0], "Signal": ["HOLD"]}
        )
        analysis = SimpleNamespace(signal_df=signal_df, symbol="2330.TW", summary={})
        options = main.MainOptions(stock_id="2330", interval="1wk")

        with TemporaryDirectory() as temp_dir, patch.object(
            main, "OUTPUT_DIR", Path(temp_dir)
        ), patch.object(main, "analyze_stock", return_value=analysis) as analyze_stock, patch.object(
            main, "run_backtest", return_value={}
        ) as run_backtest:
            main.run_analysis_result(options)

        analyze_stock.assert_called_once_with(
            "2330",
            period=main.DEFAULT_PERIOD,
            interval="1wk",
            auto_adjust=main.DEFAULT_AUTO_ADJUST,
            force_refresh=False,
        )
        run_backtest.assert_called_once_with(
            signal_df,
            initial_capital=main.INITIAL_CAPITAL,
            fee_rate=main.FEE_RATE,
            tax_rate=main.TAX_RATE,
            stop_loss_pct=options.stop_loss_pct,
            take_profit_pct=options.take_profit_pct,
            max_hold_days=options.max_hold_days,
            position_size=options.position_size,
            interval="1wk",
        )

    def test_run_analysis_result_propagates_default_daily_interval(self) -> None:
        signal_df = pd.DataFrame(
            {"Open": [100.0], "Close": [100.0], "Signal": ["HOLD"]}
        )
        analysis = SimpleNamespace(signal_df=signal_df, symbol="2330.TW", summary={})
        options = main.MainOptions(stock_id="2330")

        with TemporaryDirectory() as temp_dir, patch.object(
            main, "OUTPUT_DIR", Path(temp_dir)
        ), patch.object(main, "analyze_stock", return_value=analysis) as analyze_stock, patch.object(
            main, "run_backtest", return_value={}
        ) as run_backtest:
            main.run_analysis_result(options)

        analyze_stock.assert_called_once_with(
            "2330",
            period=main.DEFAULT_PERIOD,
            interval="1d",
            auto_adjust=main.DEFAULT_AUTO_ADJUST,
            force_refresh=False,
        )
        run_backtest.assert_called_once_with(
            signal_df,
            initial_capital=main.INITIAL_CAPITAL,
            fee_rate=main.FEE_RATE,
            tax_rate=main.TAX_RATE,
            stop_loss_pct=options.stop_loss_pct,
            take_profit_pct=options.take_profit_pct,
            max_hold_days=options.max_hold_days,
            position_size=options.position_size,
            interval="1d",
        )

    def test_validate_rejects_bad_position_size(self) -> None:
        with self.assertRaises(ValueError):
            main._validate_options(main.MainOptions(stock_id="2330", position_size=0))

    def test_runtime_validation_returns_one(self) -> None:
        output = StringIO()
        with redirect_stdout(output):
            status = main.main(["--stock", ""])

        self.assertEqual(status, 1)
        self.assertIn("錯誤：", output.getvalue())

    def test_unexpected_runtime_error_returns_one(self) -> None:
        output = StringIO()
        with patch.object(main, "run_analysis", side_effect=RuntimeError("controlled failure")), redirect_stdout(output):
            status = main.main(["--stock", "2330"])

        self.assertEqual(status, 1)
        self.assertIn("未預期錯誤：controlled failure", output.getvalue())

    def test_keyboard_interrupt_returns_one(self) -> None:
        output = StringIO()
        with patch.object(main, "run_analysis", side_effect=KeyboardInterrupt), redirect_stdout(output):
            status = main.main(["--stock", "2330"])

        self.assertEqual(status, 1)
        self.assertIn("已取消。", output.getvalue())


if __name__ == "__main__":
    unittest.main()

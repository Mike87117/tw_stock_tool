import unittest
from unittest.mock import patch

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
            main.main(["--stock", "2330", "--period", "1y"])

        run_analysis.assert_called_once()
        options = run_analysis.call_args.args[0]
        self.assertEqual(options.stock_id, "2330")
        self.assertEqual(options.period, "1y")

    def test_no_args_uses_interactive_mode(self) -> None:
        fake_options = main.MainOptions(stock_id="2330")
        with patch.object(main, "_interactive_options", return_value=fake_options) as interactive:
            with patch.object(main, "run_analysis") as run_analysis:
                main.main([])

        interactive.assert_called_once()
        run_analysis.assert_called_once_with(fake_options)

    def test_validate_rejects_bad_position_size(self) -> None:
        with self.assertRaises(ValueError):
            main._validate_options(main.MainOptions(stock_id="2330", position_size=0))


if __name__ == "__main__":
    unittest.main()

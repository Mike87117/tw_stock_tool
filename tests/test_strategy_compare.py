import unittest
from unittest.mock import patch

import pandas as pd

import strategy_compare
from analysis import StockAnalysis


def _fake_analysis() -> StockAnalysis:
    signal_df = pd.DataFrame(
        {
            "Open": [9.0, 11.0, 7.0],
            "Close": [10.0, 12.0, 8.0],
            "Signal": ["HOLD", "BUY", "SELL"],
            "Score": [0.0, 5.0, -3.0],
            "MA5": [9.0, 11.0, 9.0],
            "MA20": [10.0, 10.0, 10.0],
            "MACD": [0.0, 2.0, 0.0],
            "MACD_Signal": [1.0, 1.0, 1.0],
            "RSI": [50.0, 25.0, 75.0],
        },
        index=pd.date_range("2024-01-01", periods=3, freq="D"),
    )
    return StockAnalysis(
        stock_id="2330",
        symbol="2330.TW",
        raw_df=pd.DataFrame(),
        indicator_df=pd.DataFrame(),
        signal_df=signal_df,
        latest=signal_df.iloc[-1],
        summary={},
    )


class StrategyCompareTest(unittest.TestCase):
    def test_compare_strategies_passes_score_thresholds(self) -> None:
        captured = {}

        def fake_score_strategy(
            df: pd.DataFrame,
            buy_score: float | None = None,
            sell_score: float | None = None,
        ) -> pd.DataFrame:
            captured["buy_score"] = buy_score
            captured["sell_score"] = sell_score
            return df[["Open", "Close", "Signal"]].copy()

        fake_result = {
            "Total Return %": 1.0,
            "Buy and Hold Return %": 1.0,
            "CAGR %": 1.0,
            "Trade Count": 1,
            "Win Rate %": 100.0,
            "Max Drawdown %": 0.0,
            "Profit Factor": 1.0,
            "Sharpe Ratio": 0.0,
            "Sortino Ratio": 0.0,
        }

        strategies = {"score_strategy": fake_score_strategy}
        with patch.object(strategy_compare, "STRATEGIES", strategies):
            with patch.object(strategy_compare, "analyze_stock", return_value=_fake_analysis()):
                with patch.object(strategy_compare, "run_backtest", return_value=fake_result):
                    result = strategy_compare.compare_strategies(
                        "2330",
                        score_buy=4,
                        score_sell=-2,
                    )

        self.assertEqual(captured, {"buy_score": 4, "sell_score": -2})
        self.assertEqual(result.loc[0, "Strategy"], "score_strategy")

    def test_parse_args_accepts_score_thresholds(self) -> None:
        args = strategy_compare._parse_args(
            ["--stock", "2330", "--score-buy", "4", "--score-sell", "-2"]
        )

        self.assertEqual(args.score_buy, 4)
        self.assertEqual(args.score_sell, -2)

    def test_parse_args_accepts_output_excel(self) -> None:
        args = strategy_compare._parse_args(["--stock", "2330", "--output-excel"])
        self.assertEqual(args.output_excel, "")
        self.assertIsNone(getattr(args, "output", None))

    def test_parse_args_accepts_output_excel_custom_path(self) -> None:
        args = strategy_compare._parse_args(["--stock", "2330", "--output-excel", "custom.xlsx"])
        self.assertEqual(args.output_excel, "custom.xlsx")
        self.assertIsNone(getattr(args, "output", None))

    def test_parse_args_accepts_legacy_output(self) -> None:
        args = strategy_compare._parse_args(["--stock", "2330", "--output"])
        self.assertEqual(args.output, "")
        self.assertIsNone(getattr(args, "output_excel", None))

    def test_parse_args_fails_when_both_outputs_provided(self) -> None:
        import io
        from contextlib import redirect_stderr

        f = io.StringIO()
        with redirect_stderr(f):
            with self.assertRaises(SystemExit):
                strategy_compare._parse_args(["--stock", "2330", "--output", "--output-excel"])
        self.assertIn("Only one of --output or --output-excel may be used.", f.getvalue())

    def test_compare_strategies_uses_next_day_backtest_execution(self) -> None:
        signal_df = pd.DataFrame(
            {
                "Open": [100.0, 110.0, 120.0, 130.0],
                "Close": [100.0, 110.0, 120.0, 130.0],
                "Signal": ["BUY", "HOLD", "SELL", "HOLD"],
            },
            index=pd.date_range("2024-01-01", periods=4, freq="D"),
        )
        analysis = StockAnalysis(
            stock_id="2330",
            symbol="2330.TW",
            raw_df=pd.DataFrame(),
            indicator_df=pd.DataFrame(),
            signal_df=signal_df,
            latest=signal_df.iloc[-1],
            summary={},
        )

        def passthrough_strategy(df: pd.DataFrame, **_: object) -> pd.DataFrame:
            return df[["Open", "Close", "Signal"]].copy()

        with patch.object(strategy_compare, "STRATEGIES", {"score_strategy": passthrough_strategy}):
            with patch.object(strategy_compare, "analyze_stock", return_value=analysis):
                with patch.object(strategy_compare, "INITIAL_CAPITAL", 10000):
                    with patch.object(strategy_compare, "FEE_RATE", 0):
                        with patch.object(strategy_compare, "TAX_RATE", 0):
                            result = strategy_compare.compare_strategies("2330")

        # BUY at day 1 executes at day 2 open (110), then SELL at day 3
        # executes at day 4 open (130). Same-day execution would return 20%.
        self.assertEqual(result.loc[0, "Total Return %"], 18.0)

    @patch("pandas.DataFrame.to_excel")
    def test_export_strategy_compare_permission_error(self, mock_to_excel) -> None:
        from tw_stock_tool.reports.report import ReportError
        from pathlib import Path
        mock_to_excel.side_effect = PermissionError("locked")
        
        df = pd.DataFrame([{"Strategy": "ma_cross", "Total Return %": 10.0}])
        
        with self.assertRaises(ReportError) as cm:
            strategy_compare.export_strategy_compare(df, Path("test.xlsx"))
            
        self.assertIn("may be open", str(cm.exception))


    def test_no_banned_wording_in_cli_stdout(self) -> None:
        import sys
        from io import StringIO
        import tempfile
        from pathlib import Path
        
        banned_phrases = [
            "best strategy",
            "best parameters",
            "best result",
            "best total return",
            "best sharpe ratio",
            "winner",
            "recommended stocks",
            "buy recommendation",
            "sell recommendation",
            "investment recommendation",
            "investment opportunity",
            "best stocks to buy",
            "should buy",
            "safe to invest",
            "guaranteed profit",
            "guaranteed return",
            "guaranteed latest data"
        ]

        def passthrough_strategy(df: pd.DataFrame, **_: object) -> pd.DataFrame:
            return df[["Open", "Close", "Signal"]].copy()

        fake_result = {
            "Total Return %": 1.0,
            "Buy and Hold Return %": 1.0,
            "CAGR %": 1.0,
            "Trade Count": 1,
            "Win Rate %": 100.0,
            "Max Drawdown %": 0.0,
            "Profit Factor": 1.0,
            "Sharpe Ratio": 0.0,
            "Sortino Ratio": 0.0,
        }

        captured_output = StringIO()

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "compare.xlsx"
            with patch("sys.argv", ["strategy_compare.py", "--stock", "2330", "--output-excel", str(out_path)]):
                with patch.object(strategy_compare, "STRATEGIES", {"score_strategy": passthrough_strategy}):
                    with patch.object(strategy_compare, "analyze_stock", return_value=_fake_analysis()):
                        with patch.object(strategy_compare, "run_backtest", return_value=fake_result):
                            with patch("sys.stdout", captured_output):
                                strategy_compare.main()
        
        stdout_str = captured_output.getvalue().lower()
        
        # Positive assertions
        self.assertIn("strategy", stdout_str)
        self.assertIn("total return %", stdout_str)
        self.assertIn("cagr %", stdout_str)
        self.assertIn("sharpe ratio", stdout_str)
        
        # Negative assertions
        for phrase in banned_phrases:
            self.assertNotIn(phrase.lower(), stdout_str)

    def test_no_banned_wording_in_excel(self) -> None:
        import tempfile
        from pathlib import Path
        
        banned_phrases = [
            "best strategy",
            "best parameters",
            "best result",
            "best total return",
            "best sharpe ratio",
            "winner",
            "recommended stocks",
            "buy recommendation",
            "sell recommendation",
            "investment recommendation",
            "investment opportunity",
            "best stocks to buy",
            "should buy",
            "safe to invest",
            "guaranteed profit",
            "guaranteed return",
            "guaranteed latest data"
        ]

        fake_result = pd.DataFrame([{
            "Strategy": "score_strategy",
            "Total Return %": 1.0,
            "Buy and Hold Return %": 1.0,
            "CAGR %": 1.0,
            "Trade Count": 1,
            "Win Rate %": 100.0,
            "Max Drawdown %": 0.0,
            "Profit Factor": 1.0,
            "Sharpe Ratio": 0.0,
            "Sortino Ratio": 0.0,
        }])

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "compare.xlsx"
            strategy_compare.export_strategy_compare(fake_result, out_path)
            
            with pd.ExcelFile(out_path) as xls:
                # Positive assertions
                self.assertIn("Strategy_Compare", xls.sheet_names)
                
                # Negative assertions for sheet names
                for sheet in xls.sheet_names:
                    for phrase in banned_phrases:
                        self.assertNotIn(phrase.lower(), sheet.lower())
                        
                # Negative assertions for visible labels
                df = pd.read_excel(xls, sheet_name="Strategy_Compare")
                visible_str = df.astype(str).values.flatten().tolist() + list(df.columns)
                visible_str_lower = " ".join(visible_str).lower()
                
                # Positive assertions for column names
                self.assertIn("strategy", visible_str_lower)
                self.assertIn("total return %", visible_str_lower)
                self.assertIn("cagr %", visible_str_lower)
                self.assertIn("sharpe ratio", visible_str_lower)
                
                for phrase in banned_phrases:
                    self.assertNotIn(phrase.lower(), visible_str_lower)


if __name__ == "__main__":
    unittest.main()

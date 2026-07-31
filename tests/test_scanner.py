import argparse
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import sys
import time

import pandas as pd
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from tw_stock_tool.data import data_loader
from tw_stock_tool.analysis import scanner
from tw_stock_tool.cli import scan_stocks as scan_stocks_cli
from tw_stock_tool.cli import _research_run_cli as research_cli
from tw_stock_tool.analysis.analysis import StockAnalysis
from tw_stock_tool.analysis.scanner import ScanConfig, _filter_ok_rows, _sort_ok_rows, normalize_stock_ids, scan_stocks
from tw_stock_tool.application.research_run import SymbolRequest
from tw_stock_tool.research_run.models import ArtifactReference


def _fake_analysis(stock_id: str, score: float, signal: str) -> StockAnalysis:
    latest = pd.Series(
        {
            "Signal": signal,
            "Score": score,
            "Close": 100.0 + score,
            "MA5": 101.0,
            "MA20": 102.0,
            "MA60": 103.0,
            "RSI": 55.0,
            "MACD": 1.23,
            "MACD_Signal": 1.11,
            "K": 66.0,
            "D": 60.0,
            "BB_Upper": 120.0,
            "BB_Middle": 100.0,
            "BB_Lower": 80.0,
            "ATR": 3.5,
            "OBV": 123456.0,
            "Volume_Ratio": 1.25,
        },
        name=pd.Timestamp("2026-06-18"),
    )
    return StockAnalysis(
        stock_id=stock_id,
        symbol=f"{stock_id}.TW",
        raw_df=pd.DataFrame(),
        indicator_df=pd.DataFrame(),
        signal_df=pd.DataFrame([latest]),
        latest=latest,
        summary={"Analysis": f"{stock_id} analysis"},
    )


def _download_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [10.0, 11.0],
            "High": [12.0, 13.0],
            "Low": [9.0, 10.0],
            "Close": [11.0, 12.0],
            "Volume": [1000, 1100],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="D"),
    )


def _fake_scan_row(stock_id: str, status: str = "OK") -> dict[str, object]:
    return {
        "Rank": None,
        "Stock": stock_id,
        "Symbol": f"{stock_id}.TW" if status == "OK" else "",
        "Date": "2026-06-18" if status == "OK" else "",
        "Signal": "HOLD" if status == "OK" else "",
        "Score": 1.0 if status == "OK" else float("-inf"),
        "Close": 100.0 if status == "OK" else None,
        "MA5": 101.0 if status == "OK" else None,
        "MA20": 102.0 if status == "OK" else None,
        "MA60": 103.0 if status == "OK" else None,
        "RSI": 55.0 if status == "OK" else None,
        "MACD": 1.23 if status == "OK" else None,
        "MACD_Signal": 1.11 if status == "OK" else None,
        "K": 66.0 if status == "OK" else None,
        "D": 60.0 if status == "OK" else None,
        "BB_Upper": 120.0 if status == "OK" else None,
        "BB_Middle": 100.0 if status == "OK" else None,
        "BB_Lower": 80.0 if status == "OK" else None,
        "ATR": 3.5 if status == "OK" else None,
        "OBV": 123456.0 if status == "OK" else None,
        "Volume_Ratio": 1.25 if status == "OK" else None,
        "Analysis": f"{stock_id} analysis" if status == "OK" else "",
        "Status": status,
        "Error": "" if status == "OK" else "bad stock",
    }


class ScannerTest(unittest.TestCase):
    def test_normalize_stock_ids_removes_blank_comments_and_duplicates(self) -> None:
        self.assertEqual(
            normalize_stock_ids(["2330", "", " 2317 ", "# comment", "2330"]),
            ["2330", "2317"],
        )

    def test_scan_stocks_ranks_successful_rows_and_keeps_errors(self) -> None:
        def fake_analyze_stock(stock_id: str, **_: object) -> StockAnalysis:
            if stock_id == "9999":
                raise ValueError("bad stock")
            scores = {"2330": 5.5, "2317": 2.0}
            signals = {"2330": "BUY", "2317": "WATCH"}
            return _fake_analysis(stock_id, scores[stock_id], signals[stock_id])

        with patch.object(scanner, "analyze_stock", side_effect=fake_analyze_stock):
            result = scan_stocks(["2317", "9999", "2330"], config=ScanConfig(max_workers=2))

        self.assertEqual(result["Stock"].tolist(), ["2330", "2317", "9999"])
        self.assertEqual(result["Rank"].tolist()[:2], [1, 2])
        self.assertEqual(result.loc[0, "Score"], 5.5)
        self.assertEqual(result.loc[2, "Status"], "ERROR")
        self.assertIn("bad stock", result.loc[2, "Error"])

    def test_scan_stocks_reports_progress(self) -> None:
        progress = []

        with patch.object(
            scanner,
            "analyze_stock",
            side_effect=lambda stock_id, **_: _fake_analysis(stock_id, 1.0, "HOLD"),
        ):
            scan_stocks(
                ["2330", "2317"],
                config=ScanConfig(max_workers=1),
                progress_callback=lambda current, total, stock_id, status: progress.append(
                    (current, total, stock_id, status)
                ),
            )

        self.assertEqual(progress, [(1, 2, "2330", "OK"), (2, 2, "2317", "OK")])


    def test_scan_stocks_progress_completed_sequence_has_no_gaps(self) -> None:
        progress: list[tuple[int, int, str, str]] = []
        stocks = ["2330", "2317", "2454", "2308"]

        with patch.object(
            scanner,
            "scan_one_stock",
            side_effect=lambda stock_id, config: _fake_scan_row(stock_id),
        ):
            scan_stocks(
                stocks,
                config=ScanConfig(max_workers=4),
                progress_callback=lambda current, total, stock_id, status: progress.append(
                    (current, total, stock_id, status)
                ),
            )

        self.assertEqual(len(progress), len(stocks))
        self.assertEqual([item[0] for item in progress], [1, 2, 3, 4])
        self.assertTrue(all(item[1] == len(stocks) for item in progress))

    def test_scan_stocks_progress_print_not_swallowed_by_quiet_download(self) -> None:
        def noisy_download(symbol: str, *args, **kwargs) -> pd.DataFrame:
            print(f"HTTP Error 404: {symbol}")
            print(f"possibly delisted: {symbol}", file=sys.stderr)
            time.sleep(0.01)
            return _download_df()

        def fake_scan_one_stock(stock_id: str, config: ScanConfig) -> dict[str, object]:
            data_loader._download_yfinance_quiet(
                f"{stock_id}.TW",
                "1y",
                "1d",
                True,
            )
            return _fake_scan_row(stock_id)

        stocks = ["2330", "2317", "2454", "2308", "8069", "8299"]
        stdout = StringIO()
        stderr = StringIO()
        with patch.object(data_loader.yf, "download", side_effect=noisy_download):
            with patch.object(scanner, "scan_one_stock", side_effect=fake_scan_one_stock):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    scan_stocks(
                        stocks,
                        config=ScanConfig(max_workers=4),
                        progress_callback=lambda current, total, stock_id, status: print(
                            f"[{current}/{total}] {stock_id} {status}"
                        ),
                    )

        output = stdout.getvalue()
        self.assertEqual(stderr.getvalue(), "")
        self.assertNotIn("HTTP Error 404", output)
        self.assertNotIn("possibly delisted", stderr.getvalue())
        for current in range(1, len(stocks) + 1):
            self.assertIn(f"[{current}/{len(stocks)}]", output)

    def test_scan_stocks_filters_and_sorts(self) -> None:
        def fake_analyze_stock(stock_id: str, **_: object) -> StockAnalysis:
            scores = {"2330": 4.0, "2317": 1.0, "2454": 3.0}
            signals = {"2330": "BUY", "2317": "HOLD", "2454": "WATCH"}
            return _fake_analysis(stock_id, scores[stock_id], signals[stock_id])

        with patch.object(scanner, "analyze_stock", side_effect=fake_analyze_stock):
            result = scan_stocks(
                ["2317", "2454", "2330"],
                config=ScanConfig(
                    max_workers=1,
                    min_score=3,
                    signals=("BUY", "WATCH"),
                    top=1,
                ),
            )

        self.assertEqual(result["Stock"].tolist(), ["2330"])
        self.assertEqual(result.loc[0, "Rank"], 1)

    def test_filter_ok_rows_by_min_score_and_signals(self) -> None:
        df = pd.DataFrame(
            [
                {"Stock": "2330", "Signal": "BUY", "Score": 4, "Volume_Ratio": 1.0, "Close": 100},
                {"Stock": "2317", "Signal": "HOLD", "Score": 0, "Volume_Ratio": 2.0, "Close": 50},
            ]
        )

        result = _filter_ok_rows(df, ScanConfig(min_score=3, signals=("BUY",)))

        self.assertEqual(result["Stock"].tolist(), ["2330"])

    def test_filter_ok_rows_by_volume_ratio_and_close(self) -> None:
        df = pd.DataFrame(
            [
                {"Stock": "2330", "Signal": "BUY", "Score": 4, "Volume_Ratio": 1.6, "Close": 100},
                {"Stock": "2317", "Signal": "BUY", "Score": 4, "Volume_Ratio": 1.2, "Close": 20},
                {"Stock": "2454", "Signal": "BUY", "Score": 4, "Volume_Ratio": 2.0, "Close": 500},
            ]
        )

        result = _filter_ok_rows(
            df,
            ScanConfig(min_volume_ratio=1.5, min_close=50, max_close=200),
        )

        self.assertEqual(result["Stock"].tolist(), ["2330"])

    def test_scan_stocks_cli_parse_args_supports_auto_stock_list(self) -> None:
        args = scan_stocks_cli._parse_args([
            "--auto-stock-list",
            "--stock-market",
            "tpex",
            "--stock-list-output",
            "stocks.txt",
            "--allow-partial-stock-list",
        ])

        self.assertTrue(args.auto_stock_list)
        self.assertEqual(args.stock_market, "tpex")
        self.assertEqual(args.stock_list_output, "stocks.txt")
        self.assertTrue(args.allow_partial_stock_list)

    def test_scan_stocks_cli_auto_stock_list_calls_updater_and_has_priority(self) -> None:
        catalog = pd.DataFrame([
            {"Stock": "2330", "Name": "TSMC", "Market": "TWSE", "Type": "普通股"},
            {"Stock": "6488", "Name": "TPEX", "Market": "TPEX", "Type": "普通股"},
        ])
        normalized = pd.DataFrame([{"Stock": "2330"}, {"Stock": "6488"}])
        resolved = (SymbolRequest("2330", "2330.TW"), SymbolRequest("6488", "6488.TWO"))
        with patch.object(research_cli, "load_stock_market_catalog", return_value=catalog) as load:
            with patch.object(research_cli, "update_stock_list", return_value=(normalized, "stocks.txt")) as update:
                with patch.object(research_cli, "resolve_symbol_requests", return_value=resolved) as resolve:
                    result = research_cli.collect_symbol_requests(
                        stocks=["9999"],
                        file_path="ignored.txt",
                        auto_stock_list=True,
                        stock_market="all",
                        stock_list_output="stocks.txt",
                        allow_partial_stock_list=True,
                        stock_limit=None,
                        stock_sample=None,
                        random_state=42,
                    )
        self.assertEqual(result, resolved)
        load.assert_called_once_with(market="all", allow_partial=True)
        update.assert_called_once_with(
            market="all",
            output="stocks.txt",
            allow_partial=True,
            _preloaded_catalog=catalog,
        )
        resolve.assert_called_once_with(
            ("2330", "6488"),
            market_hint="all",
            catalog=catalog,
            allow_partial_catalog=True,
        )
    def test_scan_stocks_cli_applies_stock_limit(self) -> None:
        args = argparse.Namespace(
            auto_stock_list=False,
            file=None,
            stocks=["2330", "2317", "2454"],
            stock_limit=2,
            stock_sample=None,
            random_state=42,
        )
        resolved = (SymbolRequest("2330", "2330.TW"), SymbolRequest("2317", "2317.TW"))
        with patch.object(scan_stocks_cli, "collect_symbol_requests", return_value=resolved) as collect:
            result = scan_stocks_cli._collect_stock_ids(args)
        self.assertEqual(result, ["2330", "2317"])
        self.assertEqual(collect.call_args.kwargs["stock_limit"], 2)

    def test_scan_stocks_cli_applies_stock_sample(self) -> None:
        args = argparse.Namespace(
            auto_stock_list=False,
            file=None,
            stocks=["2330", "2317", "2454", "2308"],
            stock_limit=None,
            stock_sample=2,
            random_state=7,
        )
        resolved = (SymbolRequest("2330", "2330.TW"), SymbolRequest("2454", "2454.TW"))
        with patch.object(scan_stocks_cli, "collect_symbol_requests", return_value=resolved) as collect:
            first = scan_stocks_cli._collect_stock_ids(args)
            second = scan_stocks_cli._collect_stock_ids(args)
        self.assertEqual(first, ["2330", "2454"])
        self.assertEqual(second, first)
        self.assertEqual(collect.call_args.kwargs["stock_sample"], 2)
    def test_scan_stocks_cli_updater_failure_does_not_scan(self) -> None:
        args = argparse.Namespace(
            auto_stock_list=True,
            stock_market="all",
            stock_list_output="stocks.txt",
            allow_partial_stock_list=False,
        )
        with patch.object(scan_stocks_cli, "_parse_args", return_value=args):
            with patch.object(
                scan_stocks_cli,
                "collect_symbol_requests",
                side_effect=RuntimeError("updater down"),
            ):
                with patch.object(scan_stocks_cli, "run_scan") as run_mock:
                    with patch("builtins.print"):
                        scan_stocks_cli.main()
        run_mock.assert_not_called()
    def test_sort_ok_rows_supported_columns(self) -> None:
        df = pd.DataFrame(
            [
                {"Stock": "A", "Score": 1, "Volume_Ratio": 3, "RSI": 40, "Close": 10, "ATR": 1},
                {"Stock": "B", "Score": 2, "Volume_Ratio": 2, "RSI": 50, "Close": 20, "ATR": 2},
            ]
        )

        for column in ["Score", "Volume_Ratio", "RSI", "Close", "ATR"]:
            with self.subTest(column=column):
                result = _sort_ok_rows(df, column)
                expected = "A" if column == "Volume_Ratio" else "B"
                self.assertEqual(result.iloc[0]["Stock"], expected)

    def test_no_banned_wording_in_cli_stdout(self) -> None:
        banned_phrases = [
            "best stocks", "best stock", "recommended stocks",
            "recommended stock", "buy recommendation", "sell recommendation",
            "hold recommendation", "investment recommendation",
            "investment opportunity", "should buy", "should sell",
            "safe to invest", "strong buy", "winner", "guaranteed profit",
            "guaranteed return", "guaranteed latest data",
        ]
        result = SimpleNamespace(
            domain_result=pd.DataFrame([{
                "Status": "OK", "Score": 5, "Signal": "HOLD",
                "Close": 100, "Volume_Ratio": 1.2,
            }]),
            generated_artifacts=(
                ArtifactReference("scan_ranking_excel", "reports/ranking.xlsx", "application/octet-stream", None),
                ArtifactReference("scan_ranking_csv", "reports/ranking.csv", "text/csv", None),
                ArtifactReference("scan_ranking_html", "reports/ranking.html", "text/html", None),
            ),
        )
        symbols = (SymbolRequest("2330", "2330.TW"),)
        stdout = StringIO()
        with patch.object(scan_stocks_cli, "collect_symbol_requests", return_value=symbols):
            with patch.object(scan_stocks_cli, "run_scan", return_value=result):
                with patch.object(scan_stocks_cli, "_parse_args", return_value=scan_stocks_cli._parse_args(["--stocks", "2330"])):
                    with redirect_stdout(stdout):
                        scan_stocks_cli.main()
        output = stdout.getvalue().lower()
        self.assertIn("掃描完成", output)
        self.assertIn("成功", output)
        self.assertIn("excel:", output)
        for phrase in banned_phrases:
            self.assertNotIn(phrase, output)
if __name__ == "__main__":
    unittest.main()

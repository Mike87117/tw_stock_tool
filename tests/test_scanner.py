import pandas as pd
import unittest
from unittest.mock import patch

import scanner
from analysis import StockAnalysis
from scanner import ScanConfig, _filter_ok_rows, _sort_ok_rows, normalize_stock_ids, scan_stocks


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


if __name__ == "__main__":
    unittest.main()

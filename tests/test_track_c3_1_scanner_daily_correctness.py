import math
import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.analysis import analysis
from tw_stock_tool.analysis.scanner import ScanConfig, scan_stocks
from tw_stock_tool.reports.daily_report import (
    build_daily_report_data,
    build_data_limitations_from_ranking,
    run_daily_report,
)


def _ohlcv(kind: str, rows: int = 130) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    if kind == "rising":
        close = pd.Series([100.0 + i for i in range(rows)], index=index)
        high = close + 1.0
        low = close - 1.0
    else:
        close = pd.Series([100.0] * rows, index=index)
        high = close
        low = close
    return pd.DataFrame(
        {
            "Open": close,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": [1000.0] * rows,
        },
        index=index,
    )


def _mixed_download(stock_id: str, **_: object) -> tuple[pd.DataFrame, str]:
    if stock_id == "9999":
        raise RuntimeError("controlled download failure")
    kind = "rising" if stock_id == "2330" else "flat"
    return _ohlcv(kind), f"{stock_id}.TW"


class TrackC31ScannerDailyCorrectnessTest(unittest.TestCase):
    def test_continuous_rise_survives_real_analysis_and_scanner(self) -> None:
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(_ohlcv("rising"), "2330.TW"),
        ):
            ranking = scan_stocks(["2330"], config=ScanConfig(max_workers=1))

        row = ranking.iloc[0]
        self.assertEqual(row["Status"], "OK")
        self.assertEqual(row["Error"], "")
        self.assertEqual(row["RSI"], 100.0)
        self.assertEqual(row["Date"], "2024-05-09")
        self.assertEqual(row["Rank"], 1)
        for field in ("Score", "Volume_Ratio", "RSI", "Close", "ATR"):
            self.assertTrue(math.isfinite(float(row[field])), field)

    def test_zero_range_flat_price_observes_only_nonfinite_stochastic_fields(self) -> None:
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(_ohlcv("flat"), "2317.TW"),
        ):
            ranking = scan_stocks(["2317"], config=ScanConfig(max_workers=1))

        row = ranking.iloc[0]
        self.assertEqual(row["Status"], "OK")
        self.assertEqual(row["Error"], "")
        self.assertEqual(row["RSI"], 50.0)
        self.assertTrue(pd.isna(row["K"]))
        self.assertTrue(pd.isna(row["D"]))
        for field in ("Score", "Volume_Ratio", "RSI", "Close", "ATR"):
            self.assertTrue(math.isfinite(float(row[field])), field)

    def test_mixed_universe_isolates_failure_and_ranks_valid_rows(self) -> None:
        with patch.object(analysis, "download_tw_stock", side_effect=_mixed_download):
            ranking = scan_stocks(
                ["2317", "9999", "2330"],
                config=ScanConfig(max_workers=1),
            )

        self.assertEqual(ranking["Stock"].tolist(), ["2330", "2317", "9999"])
        self.assertEqual(ranking["Status"].tolist(), ["OK", "OK", "ERROR"])
        self.assertEqual(ranking["Rank"].tolist()[:2], [1, 2])
        self.assertTrue(pd.isna(ranking.iloc[2]["Rank"]))
        self.assertTrue(pd.isna(ranking.iloc[2]["Score"]))
        self.assertEqual(ranking.iloc[2]["Error"], "controlled download failure")

    def test_daily_report_builds_honest_mixed_universe_data(self) -> None:
        stock_ids = ["2317", "9999", "2330"]
        with patch.object(analysis, "download_tw_stock", side_effect=_mixed_download):
            summary, candidates, ranking, output = run_daily_report(
                stock_ids,
                signals=("BUY", "WATCH", "HOLD", "SELL"),
                min_score=-10.0,
                output=None,
                progress=False,
            )

        summary_row = summary.iloc[0]
        self.assertIsNone(output)
        self.assertEqual(summary_row["Stocks Scanned"], 3)
        self.assertEqual(summary_row["Candidates"], len(candidates))
        self.assertEqual(len(candidates), 2)
        self.assertNotIn("9999", candidates["Stock"].tolist())
        self.assertEqual(summary_row["BUY Count"], int((candidates["Signal"] == "BUY").sum()))
        self.assertEqual(
            summary_row["WATCH Count"],
            int((candidates["Signal"] == "WATCH").sum()),
        )
        self.assertEqual(summary_row["Average Score"], round(float(candidates["Score"].mean()), 2))
        self.assertEqual(
            summary_row["Average Volume Ratio"],
            round(float(candidates["Volume_Ratio"].mean()), 4),
        )
        self.assertEqual(ranking.iloc[-1]["Status"], "ERROR")
        limitations = build_data_limitations_from_ranking(ranking)
        self.assertEqual(limitations, ["9999: ERROR - controlled download failure"])
        report_data = build_daily_report_data(
            report_date="2026-07-14",
            stock_universe=stock_ids,
            screening_results=summary,
            watchlist_candidates=candidates,
            data_limitations=limitations,
        )
        self.assertEqual(report_data["Screening Summary"][0]["Stocks Scanned"], 3)
        self.assertEqual(len(report_data["Watchlist Candidates"]), 2)
        self.assertEqual(report_data["Data Limitations"], limitations)

    def test_scanner_propagates_existing_weekly_interval(self) -> None:
        calls: list[dict[str, object]] = []

        def download(stock_id: str, **kwargs: object) -> tuple[pd.DataFrame, str]:
            calls.append(kwargs)
            return _ohlcv("rising"), f"{stock_id}.TW"

        with patch.object(analysis, "download_tw_stock", side_effect=download):
            scan_stocks(
                ["2330"],
                config=ScanConfig(interval="1wk", max_workers=1),
            )

        self.assertEqual([call["interval"] for call in calls], ["1wk"])

    def test_daily_report_propagates_existing_weekly_interval(self) -> None:
        calls: list[dict[str, object]] = []

        def download(stock_id: str, **kwargs: object) -> tuple[pd.DataFrame, str]:
            calls.append(kwargs)
            return _ohlcv("rising"), f"{stock_id}.TW"

        with patch.object(analysis, "download_tw_stock", side_effect=download):
            run_daily_report(["2330"], interval="1wk", output=None, progress=False)

        self.assertEqual([call["interval"] for call in calls], ["1wk"])

    def test_empty_scanner_input_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            scan_stocks([], config=ScanConfig(max_workers=1))

    def test_all_failed_scanner_returns_structured_failure_rows(self) -> None:
        with patch.object(
            analysis,
            "download_tw_stock",
            side_effect=RuntimeError("controlled total failure"),
        ):
            ranking = scan_stocks(
                ["9999", "8888"],
                config=ScanConfig(max_workers=1),
            )

        self.assertEqual(ranking["Stock"].tolist(), ["8888", "9999"])
        self.assertTrue((ranking["Status"] == "ERROR").all())
        self.assertTrue(ranking["Rank"].isna().all())
        self.assertTrue(ranking["Score"].isna().all())
        self.assertEqual(ranking["Error"].tolist(), ["controlled total failure"] * 2)

    def test_all_failed_daily_report_has_zero_candidates_and_failure_details(self) -> None:
        with patch.object(
            analysis,
            "download_tw_stock",
            side_effect=RuntimeError("controlled total failure"),
        ):
            summary, candidates, ranking, output = run_daily_report(
                ["9999", "8888"],
                output=None,
                progress=False,
            )

        row = summary.iloc[0]
        self.assertIsNone(output)
        self.assertEqual(row["Stocks Scanned"], 2)
        self.assertEqual(row["Candidates"], 0)
        self.assertEqual(row["BUY Count"], 0)
        self.assertEqual(row["WATCH Count"], 0)
        self.assertEqual(row["Average Score"], 0.0)
        self.assertEqual(row["Average Volume Ratio"], 0.0)
        self.assertTrue(candidates.empty)
        self.assertTrue((ranking["Status"] == "ERROR").all())
        self.assertEqual(
            build_data_limitations_from_ranking(ranking),
            [
                "8888: ERROR - controlled total failure",
                "9999: ERROR - controlled total failure",
            ],
        )


if __name__ == "__main__":
    unittest.main()

import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pandas as pd

from tw_stock_tool.analysis.analysis import StockAnalysis
from tw_stock_tool.analysis.analysis_session import AnalysisSession
from tw_stock_tool.analysis.scanner import ScanConfig, scan_one_stock
from tw_stock_tool.backtesting import walk_forward
from tw_stock_tool.reports import daily_report


def _analysis(stock_id: str = "2330") -> StockAnalysis:
    latest = pd.Series(
        {
            "Signal": "BUY",
            "Score": 5.0,
            "Close": 100.0,
            "MA5": 101.0,
            "MA20": 102.0,
            "MA60": 103.0,
            "RSI": 55.0,
            "MACD": 1.0,
            "MACD_Signal": 0.5,
            "K": 60.0,
            "D": 55.0,
            "BB_Upper": 110.0,
            "BB_Middle": 100.0,
            "BB_Lower": 90.0,
            "ATR": 2.0,
            "OBV": 1000.0,
            "Volume_Ratio": 1.2,
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
        summary={"Analysis": "test"},
    )


class AnalysisSessionTest(unittest.TestCase):
    def test_normalizes_stock_id_and_memoizes_success(self) -> None:
        result = _analysis()
        analyzer = Mock(return_value=result)
        session = AnalysisSession(
            period="2y",
            interval="1wk",
            auto_adjust=True,
            force_refresh=True,
            analyzer=analyzer,
        )

        self.assertIs(session.get(" 2330 "), result)
        self.assertIs(session.get("2330"), result)
        analyzer.assert_called_once_with(
            stock_id="2330",
            period="2y",
            interval="1wk",
            auto_adjust=True,
            force_refresh=True,
        )

    def test_caches_failures_and_does_not_retry(self) -> None:
        analyzer = Mock(side_effect=ValueError("download failed"))
        session = AnalysisSession(
            period="1y", interval="1d", auto_adjust=False, force_refresh=False, analyzer=analyzer
        )

        for _ in range(2):
            with self.assertRaisesRegex(ValueError, "download failed"):
                session.get("2330")
        analyzer.assert_called_once()

    def test_same_stock_concurrent_calls_analyze_once(self) -> None:
        result = _analysis()
        calls = 0
        calls_guard = threading.Lock()

        def analyzer(**_: object) -> StockAnalysis:
            nonlocal calls
            with calls_guard:
                calls += 1
            return result

        session = AnalysisSession(
            period="1y", interval="1d", auto_adjust=False, force_refresh=False, analyzer=analyzer
        )
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda _: session.get("2330"), range(16)))

        self.assertEqual(calls, 1)
        self.assertTrue(all(item is result for item in results))


class AnalysisProviderBoundaryTest(unittest.TestCase):
    def test_scanner_uses_provider(self) -> None:
        result = _analysis()
        provider = Mock(return_value=result)

        row = scan_one_stock("2330", ScanConfig(analysis_provider=provider))

        provider.assert_called_once_with("2330")
        self.assertEqual(row["Status"], "OK")
        self.assertEqual(row["Stock"], "2330")

    def test_daily_report_forwards_provider_to_scan_config(self) -> None:
        provider = Mock(return_value=_analysis())
        ranking = pd.DataFrame()
        with patch.object(daily_report, "scan_stocks", return_value=ranking) as scan, patch.object(
            daily_report, "filter_candidates", return_value=pd.DataFrame()
        ), patch.object(daily_report, "build_summary", return_value=pd.DataFrame()), patch.object(
            daily_report, "export_daily_report", return_value=None
        ):
            daily_report.run_daily_report(["2330"], progress=False, analysis_provider=provider)

        self.assertIs(scan.call_args.kwargs["config"].analysis_provider, provider)

    def test_walk_forward_uses_precomputed_analysis(self) -> None:
        result = _analysis()
        with patch.object(walk_forward, "analyze_stock") as analyzer, patch.object(
            walk_forward, "split_windows", return_value=[]
        ):
            detail = walk_forward.run_walk_forward(
                "2330", strategy="score", train_days=2, test_days=1, analysis=result
            )

        analyzer.assert_not_called()
        self.assertIsInstance(detail, pd.DataFrame)

    def test_candidate_walk_forward_passes_provider_result_as_analysis(self) -> None:
        provider = Mock(return_value=_analysis())
        detail = pd.DataFrame(
            [
                {
                    "Window": 1,
                    "Test Total Return %": 1.0,
                    "Test CAGR %": 1.0,
                    "Test Sharpe Ratio": 1.0,
                    "Test Max Drawdown %": -1.0,
                    "Error": "",
                }
            ]
        )
        candidates = pd.DataFrame([{"Rank": 1, "Stock": "2330", "Signal": "BUY", "Score": 5.0, "Status": "OK"}])
        with patch.object(daily_report, "run_walk_forward", return_value=detail) as runner:
            daily_report.run_candidate_walk_forward_validation(
                candidates,
                walk_forward_top=1,
                strategy="score",
                period="1y",
                interval="1d",
                auto_adjust=False,
                force_refresh=False,
                train_days=2,
                test_days=1,
                step_days=1,
                sort_by="Train Sharpe Ratio",
                initial_capital=100000,
                fee_rate=0.001,
                tax_rate=0.003,
                position_size=1.0,
                analysis_provider=provider,
            )

        provider.assert_called_once_with("2330")
        self.assertIs(runner.call_args.kwargs["analysis"], provider.return_value)


if __name__ == "__main__":
    unittest.main()

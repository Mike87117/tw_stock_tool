import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, mock_open, patch

import pandas as pd

from tw_stock_tool.analysis.analysis_session import AnalysisSession
from tw_stock_tool.analysis.scanner import ScanConfig, scan_one_stock
from tw_stock_tool.cli import daily_report_cli
from tw_stock_tool.reports import daily_report

from tests.test_phase_50_3_analysis_reuse import _analysis


def _backtest_result() -> SimpleNamespace:
    return SimpleNamespace(
        start_date=pd.Timestamp("2024-01-01"),
        end_date=pd.Timestamp("2024-01-02"),
        total_return_pct=1.0,
        buy_hold_return_pct=0.5,
        trade_count=1,
        win_rate_pct=100.0,
        max_drawdown_pct=-1.0,
        sharpe_ratio=1.0,
    )


class AnalysisSessionReviewerGateTest(unittest.TestCase):
    def _session(self, analyzer):
        return AnalysisSession(
            period="1y",
            interval="1d",
            auto_adjust=False,
            force_refresh=True,
            analyzer=analyzer,
        )

    def test_concurrent_failure_is_cached_once(self) -> None:
        analyzer = Mock(side_effect=ValueError("provider failed"))
        session = self._session(analyzer)

        def call(_: int) -> str:
            try:
                session.get("2330")
            except ValueError as exc:
                return str(exc)
            return "unexpected success"

        with ThreadPoolExecutor(max_workers=8) as executor:
            errors = list(executor.map(call, range(16)))

        self.assertEqual(errors, ["provider failed"] * 16)
        analyzer.assert_called_once_with(
            stock_id="2330",
            period="1y",
            interval="1d",
            auto_adjust=False,
            force_refresh=True,
        )

    def test_different_stocks_can_be_cached_independently(self) -> None:
        results = {stock_id: _analysis(stock_id) for stock_id in ("2330", "2317")}
        analyzer = Mock(side_effect=lambda **kwargs: results[kwargs["stock_id"]])
        session = self._session(analyzer)

        with ThreadPoolExecutor(max_workers=2) as executor:
            actual = list(executor.map(session.get, ("2330", "2317")))

        self.assertIs(actual[0], results["2330"])
        self.assertIs(actual[1], results["2317"])
        self.assertEqual(analyzer.call_count, 2)


class Phase503ProviderReviewerGateTest(unittest.TestCase):
    def _validation_args(self) -> dict[str, object]:
        return {
            "period": "1y",
            "interval": "1d",
            "auto_adjust": False,
            "force_refresh": True,
            "initial_capital": 100000,
            "fee_rate": 0.001,
            "tax_rate": 0.003,
            "position_size": 1.0,
        }

    def test_scanner_provider_failure_preserves_error_row(self) -> None:
        provider = Mock(side_effect=ValueError("provider failed"))

        row = scan_one_stock("2330", ScanConfig(analysis_provider=provider))

        self.assertEqual(row["Stock"], "2330")
        self.assertEqual(row["Status"], "ERROR")
        self.assertEqual(row["Error"], "provider failed")
        provider.assert_called_once_with("2330")

    def test_backtest_provider_bypasses_module_analyzer(self) -> None:
        provider = Mock(return_value=_analysis())
        candidates = pd.DataFrame([{"Stock": "2330", "Signal": "BUY", "Score": 5.0}])
        with patch.object(daily_report, "analyze_stock") as fallback, patch.dict(
            daily_report.STRATEGIES, {"score_strategy": lambda frame: frame}, clear=False
        ), patch.object(daily_report, "run_backtest_result", return_value=_backtest_result()):
            highlights, limitations = daily_report.run_candidate_backtest_validation(
                candidates,
                validate_top=1,
                strategy="score",
                analysis_provider=provider,
                **self._validation_args(),
            )

        provider.assert_called_once_with("2330")
        fallback.assert_not_called()
        self.assertEqual(highlights.loc[0, "Status"], "OK")
        self.assertEqual(limitations, [])

    def test_one_session_reuses_analysis_across_scan_backtest_and_walk_forward(self) -> None:
        analyzer = Mock(return_value=_analysis())
        session = AnalysisSession(
            period="1y", interval="1d", auto_adjust=False, force_refresh=True, analyzer=analyzer
        )
        candidates = pd.DataFrame([{"Stock": "2330", "Signal": "BUY", "Score": 5.0}])
        detail = pd.DataFrame(
            [{
                "Window": 1,
                "Test Total Return %": 1.0,
                "Test CAGR %": 1.0,
                "Test Sharpe Ratio": 1.0,
                "Test Max Drawdown %": -1.0,
                "Error": "",
            }]
        )
        with patch.dict(
            daily_report.STRATEGIES, {"score_strategy": lambda frame: frame}, clear=False
        ), patch.object(daily_report, "run_backtest_result", return_value=_backtest_result()), patch.object(
            daily_report, "run_walk_forward", return_value=detail
        ):
            row = scan_one_stock("2330", ScanConfig(analysis_provider=session.get))
            backtests, _ = daily_report.run_candidate_backtest_validation(
                candidates,
                validate_top=1,
                strategy="score",
                analysis_provider=session.get,
                **self._validation_args(),
            )
            daily_report.run_candidate_walk_forward_validation(
                backtests,
                walk_forward_top=1,
                strategy="score",
                train_days=2,
                test_days=1,
                step_days=1,
                sort_by="Train Sharpe Ratio",
                analysis_provider=session.get,
                **self._validation_args(),
            )

        self.assertEqual(row["Status"], "OK")
        analyzer.assert_called_once_with(
            stock_id="2330",
            period="1y",
            interval="1d",
            auto_adjust=False,
            force_refresh=True,
        )


class DailyCliProviderReviewerGateTest(unittest.TestCase):
    def test_cli_passes_the_same_bound_provider_to_all_stages(self) -> None:
        session = Mock()
        ranking = pd.DataFrame()
        candidates = pd.DataFrame([{"Stock": "2330"}])
        backtests = pd.DataFrame([{"Status": "OK"}])
        walk_forwards = pd.DataFrame()
        with patch.object(sys, "argv", ["daily_report_cli.py", "--stocks", "2330", "--validate-top", "1", "--walk-forward-top", "1"]), patch.object(
            daily_report_cli, "AnalysisSession", return_value=session
        ) as session_class, patch.object(
            daily_report_cli, "run_daily_report", return_value=(ranking, candidates, ranking, None)
        ) as scan, patch.object(
            daily_report_cli, "run_candidate_backtest_validation", return_value=(backtests, [])
        ) as backtest, patch.object(
            daily_report_cli, "run_candidate_walk_forward_validation", return_value=(walk_forwards, [])
        ) as walk_forward_validation, patch.object(
            daily_report_cli, "build_data_limitations_from_ranking", return_value=[]
        ), patch.object(daily_report_cli, "build_daily_report_data", return_value={}), patch.object(
            daily_report_cli, "render_daily_report_markdown", return_value="# report"
        ), patch.object(Path, "mkdir"), patch("builtins.open", mock_open()):
            daily_report_cli.main()

        session_class.assert_called_once()
        provider = session.get
        self.assertIs(scan.call_args.kwargs["analysis_provider"], provider)
        self.assertIs(backtest.call_args.kwargs["analysis_provider"], provider)
        self.assertIs(walk_forward_validation.call_args.kwargs["analysis_provider"], provider)


if __name__ == "__main__":
    unittest.main()

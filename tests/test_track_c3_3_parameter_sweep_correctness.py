import inspect
import math
import unittest
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.analysis import analysis
from tw_stock_tool.backtesting import parameter_sweep
from tw_stock_tool.backtesting.backtest import run_backtest
from tw_stock_tool.backtesting.strategies import ma_cross_strategy, score_strategy
from tw_stock_tool.reports.parameter_sweep_report import build_parameter_sweep_report_data


FINITE_METRICS = (
    "Total Return %",
    "Buy and Hold Return %",
    "CAGR %",
    "Trade Count",
    "Win Rate %",
    "Max Drawdown %",
    "Sharpe Ratio",
    "Sortino Ratio",
)


def _ohlcv(kind: str = "wave", rows: int = 240) -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=rows, freq="D")
    if kind == "wave":
        close = [100.0 + (i % 40 if i % 40 < 20 else 40 - i % 40) for i in range(rows)]
    elif kind == "rsi":
        half = rows // 2
        close = [300.0 - i for i in range(half)] + [180.0 + i for i in range(rows - half)]
    elif kind == "rising":
        close = [100.0 + i for i in range(rows)]
    elif kind == "falling":
        close = [400.0 - i for i in range(rows)]
    else:
        close = [100.0] * rows
    close_series = pd.Series(close, index=index)
    return pd.DataFrame(
        {
            "Open": close_series,
            "High": close_series + 1.0,
            "Low": close_series - 1.0,
            "Close": close_series,
            "Volume": [1000.0] * rows,
        },
        index=index,
    )


def _assert_success_metrics(test: unittest.TestCase, result: pd.DataFrame) -> None:
    test.assertTrue((result["Error"] == "").all())
    for column in FINITE_METRICS:
        test.assertTrue(
            result[column].map(lambda value: math.isfinite(float(value))).all(),
            column,
        )


class TrackC33ParameterSweepCorrectnessTest(unittest.TestCase):
    def test_real_score_sweep_runs_analysis_strategies_backtests_and_ranking(self) -> None:
        source = _ohlcv()
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(source, "2330.TW"),
        ):
            analyzed = analysis.analyze_stock("2330")
            result = parameter_sweep.run_parameter_sweep(
                "2330",
                strategy="score",
                score_buy=(1, 2),
                score_sell=(-1, -2),
                sort_by="Sharpe Ratio",
                top=0,
            )

        expected_parameters = {
            f"buy_score={buy}, sell_score={sell}"
            for buy in (1, 2)
            for sell in (-1, -2)
        }
        self.assertGreaterEqual(analyzed.signal_df["Score"].nunique(), 3)
        self.assertEqual(len(result), 4)
        self.assertEqual(set(result["Parameters"]), expected_parameters)
        _assert_success_metrics(self, result)
        self.assertEqual(result["Rank"].tolist(), [1, 2, 3, 4])
        sharpe = result["Sharpe Ratio"].astype(float).tolist()
        self.assertEqual(sharpe, sorted(sharpe, reverse=True))

    def test_real_ma_sweep_executes_every_combination_and_top_after_sorting(self) -> None:
        source = _ohlcv()
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(source, "2330.TW"),
        ):
            analyzed = analysis.analyze_stock("2330")
            full = parameter_sweep.run_parameter_sweep(
                "2330",
                strategy="ma_cross",
                ma_short_windows=(3, 5),
                ma_long_windows=(15,),
                sort_by="Total Return %",
                top=0,
            )
            limited = parameter_sweep.run_parameter_sweep(
                "2330",
                strategy="ma_cross",
                ma_short_windows=(3, 5),
                ma_long_windows=(15,),
                sort_by="Total Return %",
                top=1,
            )

        expected = {
            "short_window=3, long_window=15",
            "short_window=5, long_window=15",
        }
        self.assertEqual(set(full["Parameters"]), expected)
        self.assertEqual(len(full), 2)
        _assert_success_metrics(self, full)
        for short in (3, 5):
            strategy_df = ma_cross_strategy(
                analyzed.signal_df,
                short_window=short,
                long_window=15,
            )
            self.assertTrue(strategy_df["Signal"].isin(["BUY", "SELL"]).any())
            direct = run_backtest(strategy_df.dropna(subset=["Close", "Signal"]))
            row = full[full["Parameters"] == f"short_window={short}, long_window=15"].iloc[0]
            self.assertEqual(row["Trade Count"], direct["Trade Count"])
            self.assertEqual(row["Total Return %"], direct["Total Return %"])
        self.assertEqual(len(limited), 1)
        self.assertEqual(limited.iloc[0]["Parameters"], full.iloc[0]["Parameters"])

    def test_real_rsi_sweep_preserves_c2_edges_and_threshold_parameters(self) -> None:
        source = _ohlcv("rsi")
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(source, "2454.TW"),
        ):
            analyzed = analysis.analyze_stock("2454")
            result = parameter_sweep.run_parameter_sweep(
                "2454",
                strategy="rsi",
                rsi_buy_below=(25, 35),
                rsi_sell_above=(65,),
                top=0,
            )

        self.assertTrue(analyzed.signal_df["RSI"].map(math.isfinite).all())
        self.assertLess(float(analyzed.signal_df["RSI"].min()), 30.0)
        self.assertGreater(float(analyzed.signal_df["RSI"].max()), 70.0)
        self.assertEqual(
            set(result["Parameters"]),
            {"buy_below=25, sell_above=65", "buy_below=35, sell_above=65"},
        )
        _assert_success_metrics(self, result)

        for kind, expected_rsi in (("rising", 100.0), ("falling", 0.0), ("flat", 50.0)):
            with patch.object(
                analysis,
                "download_tw_stock",
                return_value=(_ohlcv(kind), f"{kind}.TW"),
            ):
                edge = parameter_sweep.run_parameter_sweep(
                    kind,
                    strategy="rsi",
                    rsi_buy_below=(30,),
                    rsi_sell_above=(70,),
                    top=0,
                )
                edge_analysis = analysis.analyze_stock(kind)
            self.assertEqual(edge.iloc[0]["Error"], "", kind)
            self.assertEqual(float(edge_analysis.latest["RSI"]), expected_rsi, kind)

    def test_mixed_valid_invalid_rsi_parameters_keep_error_after_top_limit(self) -> None:
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(_ohlcv("rsi"), "2454.TW"),
        ):
            result = parameter_sweep.run_parameter_sweep(
                "2454",
                strategy="rsi",
                rsi_buy_below=(-1, 30),
                rsi_sell_above=(70,),
                top=1,
            )

        self.assertEqual(len(result), 2)
        success = result[result["Error"] == ""]
        errors = result[result["Error"] != ""]
        self.assertEqual(len(success), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(result.iloc[0]["Error"], "")
        self.assertNotEqual(result.iloc[1]["Error"], "")
        self.assertIn("0 <= buy_below", errors.iloc[0]["Error"])
        self.assertTrue(pd.isna(errors.iloc[0]["Rank"]))
        self.assertTrue(pd.isna(errors.iloc[0]["Sharpe Ratio"]))
        self.assertEqual(errors.iloc[0]["Parameters"], "buy_below=-1, sell_above=70")

    def test_all_invalid_rsi_parameters_return_only_structured_errors(self) -> None:
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(_ohlcv("rsi"), "2454.TW"),
        ):
            result = parameter_sweep.run_parameter_sweep(
                "2454",
                strategy="rsi",
                rsi_buy_below=(-2, -1),
                rsi_sell_above=(70,),
                top=0,
            )

        self.assertEqual(len(result), 2)
        self.assertTrue((result["Error"] != "").all())
        self.assertTrue(result["Rank"].isna().all())
        self.assertTrue(result[list(FINITE_METRICS)].isna().all().all())
        self.assertEqual(
            set(result["Parameters"]),
            {"buy_below=-2, sell_above=70", "buy_below=-1, sell_above=70"},
        )

    def test_nonfinite_open_reaches_backtest_and_becomes_one_error_per_combination(self) -> None:
        source = _ohlcv()
        contaminated_date = source.index[100]
        source.loc[contaminated_date, "Open"] = float("nan")
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(source, "2330.TW"),
        ):
            analyzed = analysis.analyze_stock("2330")
            result = parameter_sweep.run_parameter_sweep(
                "2330",
                strategy="score",
                score_buy=(1, 2),
                score_sell=(-1,),
                top=0,
            )

        self.assertIn(contaminated_date, analyzed.signal_df.index)
        self.assertTrue(pd.isna(analyzed.signal_df.loc[contaminated_date, "Open"]))
        self.assertEqual(len(result), 2)
        self.assertTrue((result["Error"] != "").all())
        self.assertTrue(result["Error"].str.contains("Open must be a finite numeric value").all())
        self.assertTrue(result["Rank"].isna().all())
        self.assertTrue(result[list(FINITE_METRICS)].isna().all().all())

    def test_real_sorting_ranking_and_top_variants_match_full_results(self) -> None:
        kwargs = dict(
            strategy="score",
            score_buy=(1, 2),
            score_sell=(-1, -2),
            sort_by="Sharpe Ratio",
        )
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(_ohlcv(), "2330.TW"),
        ):
            full = parameter_sweep.run_parameter_sweep("2330", top=0, **kwargs)
            negative = parameter_sweep.run_parameter_sweep("2330", top=-1, **kwargs)
            limited = parameter_sweep.run_parameter_sweep("2330", top=2, **kwargs)

        self.assertEqual(full["Rank"].tolist(), [1, 2, 3, 4])
        self.assertEqual(
            full["Sharpe Ratio"].astype(float).tolist(),
            sorted(full["Sharpe Ratio"].astype(float), reverse=True),
        )
        pd.testing.assert_frame_equal(negative, full)
        self.assertEqual(len(limited), 2)
        self.assertEqual(limited["Parameters"].tolist(), full["Parameters"].head(2).tolist())

    def test_equal_metric_ties_observe_stable_grid_order_without_contract(self) -> None:
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(_ohlcv(), "2330.TW"),
        ):
            result = parameter_sweep.run_parameter_sweep(
                "2330",
                strategy="score",
                score_buy=(99, 100),
                score_sell=(-99,),
                sort_by="Sharpe Ratio",
                top=0,
            )

        self.assertEqual(result["Sharpe Ratio"].nunique(), 1)
        self.assertEqual(
            result["Parameters"].tolist(),
            ["buy_score=99, sell_score=-99", "buy_score=100, sell_score=-99"],
        )
        self.assertEqual(result["Rank"].tolist(), [1, 2])

    def test_sweep_metrics_match_explicit_daily_canonical_backtest(self) -> None:
        source = _ohlcv()
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(source, "2330.TW"),
        ):
            analyzed = analysis.analyze_stock("2330")
            sweep = parameter_sweep.run_parameter_sweep(
                "2330",
                strategy="score",
                score_buy=(1,),
                score_sell=(-1,),
                top=0,
            )

        strategy_df = score_strategy(analyzed.signal_df, buy_score=1, sell_score=-1)
        daily = run_backtest(
            strategy_df.dropna(subset=["Close", "Signal"]),
            interval="1d",
        )
        self.assertEqual(sweep.iloc[0]["Sharpe Ratio"], daily["Sharpe Ratio"])
        self.assertEqual(sweep.iloc[0]["Sortino Ratio"], daily["Sortino Ratio"])
        self.assertIn(
            "interval",
            inspect.signature(parameter_sweep.run_parameter_sweep).parameters,
        )
        self.assertIn("auto_adjust", inspect.signature(parameter_sweep.run_parameter_sweep).parameters)
        self.assertIn("analysis", inspect.signature(parameter_sweep.run_parameter_sweep).parameters)

    def test_report_builder_selects_numeric_sharpe_not_first_or_error_row(self) -> None:
        with patch.object(
            analysis,
            "download_tw_stock",
            return_value=(_ohlcv("rsi"), "2454.TW"),
        ):
            real_result = parameter_sweep.run_parameter_sweep(
                "2454",
                strategy="rsi",
                rsi_buy_below=(-1, 30),
                rsi_sell_above=(70,),
                top=0,
            )

        error_first = real_result.iloc[::-1].reset_index(drop=True)
        report = build_parameter_sweep_report_data(error_first)
        pd.testing.assert_frame_equal(report["Results"], error_first)
        numeric_sharpe = pd.to_numeric(error_first["Sharpe Ratio"], errors="coerce")
        expected = error_first.loc[numeric_sharpe.idxmax()]
        self.assertNotEqual(error_first.iloc[0]["Error"], "")
        self.assertEqual(report["Best Row"]["Parameters"], expected["Parameters"])
        self.assertEqual(report["Best Row"]["Sharpe Ratio"], expected["Sharpe Ratio"])
        self.assertEqual(report["Top Results"].iloc[0]["Error"], "")

    def test_public_parameters_and_custom_grid_propagate_at_existing_boundaries(self) -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        def download(stock_id: str, **kwargs: object) -> tuple[pd.DataFrame, str]:
            calls.append((stock_id, kwargs))
            return _ohlcv(), f"{stock_id}.TW"

        with patch.object(analysis, "download_tw_stock", side_effect=download), patch.object(
            parameter_sweep,
            "run_backtest",
            wraps=run_backtest,
        ) as backtest_spy:
            result = parameter_sweep.run_parameter_sweep(
                " 2330 ",
                period="5y",
                strategy="score",
                force_refresh=True,
                initial_capital=200000.0,
                fee_rate=0.001,
                tax_rate=0.002,
                position_size=0.5,
                stop_loss_pct=5.0,
                take_profit_pct=10.0,
                max_hold_days=20,
                score_buy=(2,),
                score_sell=(-2,),
                top=0,
            )

        self.assertEqual(len(calls), 1)
        stock_id, download_kwargs = calls[0]
        self.assertEqual(stock_id, "2330")
        self.assertEqual(download_kwargs["period"], "5y")
        self.assertTrue(download_kwargs["force_refresh"])
        backtest_spy.assert_called_once()
        engine_kwargs = backtest_spy.call_args.kwargs
        self.assertEqual(engine_kwargs["initial_capital"], 200000.0)
        self.assertEqual(engine_kwargs["fee_rate"], 0.001)
        self.assertEqual(engine_kwargs["tax_rate"], 0.002)
        self.assertEqual(engine_kwargs["position_size"], 0.5)
        self.assertEqual(engine_kwargs["stop_loss_pct"], 5.0)
        self.assertEqual(engine_kwargs["take_profit_pct"], 10.0)
        self.assertEqual(engine_kwargs["max_hold_days"], 20)
        self.assertEqual(engine_kwargs["interval"], "1d")
        self.assertEqual(result.iloc[0]["Parameters"], "buy_score=2, sell_score=-2")
        self.assertEqual(result.iloc[0]["Error"], "")


if __name__ == "__main__":
    unittest.main()

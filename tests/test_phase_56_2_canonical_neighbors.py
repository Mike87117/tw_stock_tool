from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from tw_stock_tool.application.universe_qualification import (
    UniverseQualificationRequest,
    _neighbors,
    evaluate_universe_qualification,
)


class CanonicalQualificationNeighborTests(unittest.TestCase):
    def test_two_dimensional_neighbors_preserve_set_in_canonical_order(self):
        selected = {"short_window": 2, "long_window": 4}
        grid = (
            {"short_window": 2, "long_window": 4},
            {"short_window": 2, "long_window": 5},
            {"short_window": 3, "long_window": 4},
            {"short_window": 3, "long_window": 5},
        )

        actual = _neighbors(selected, grid)

        self.assertEqual(
            actual,
            (
                {"short_window": 3, "long_window": 4},
                {"short_window": 2, "long_window": 5},
                {"short_window": 3, "long_window": 5},
            ),
        )
        self.assertNotIn(selected, actual)
        self.assertEqual(
            {frozenset(item.items()) for item in actual},
            {
                frozenset({("short_window", 2), ("long_window", 5)}),
                frozenset({("short_window", 3), ("long_window", 4)}),
                frozenset({("short_window", 3), ("long_window", 5)}),
            },
        )

    def test_real_two_dimensional_universe_evaluation_keeps_windows_valid(self):
        index = pd.date_range("2025-01-01", periods=70, freq="D")
        close = np.linspace(100.0, 110.0, len(index))
        frame = pd.DataFrame({"Open": close, "Close": close}, index=index)
        benchmark = pd.DataFrame(
            {"Open": np.full(len(index), 100.0), "Close": np.full(len(index), 100.0)},
            index=index,
        )
        request = UniverseQualificationRequest(
            evaluation_id="523e4567-e89b-42d3-a456-426614174000",
            created_at="2025-04-01T00:00:00Z",
            strategy="ma_cross",
            symbol_data={symbol: frame for symbol in ("2303", "2317", "2330", "2454", "2881")},
            benchmark_data=benchmark,
            train_days=10,
            test_days=10,
            step_days=10,
            parameter_options={
                "short_window": (2, 3),
                "long_window": (4, 5),
            },
        )

        def fake_backtest(data, strategy, params, *args):
            preferred = {"short_window": 2, "long_window": 4}
            value = 10.0 if dict(params) == preferred else 8.0
            return {
                "Total Return %": value,
                "Sharpe Ratio": value,
                "Trade Count": 1,
                "Max Drawdown %": 5.0,
            }

        with patch(
            "tw_stock_tool.application.universe_qualification.run_strategy_backtest",
            side_effect=fake_backtest,
        ):
            result = evaluate_universe_qualification(request)

        self.assertEqual(result.qualification.decision.state, "PAPER_READY")
        self.assertTrue(all(symbol.evaluated for symbol in result.symbols))
        self.assertTrue(
            all(window.valid for symbol in result.symbols for window in symbol.windows)
        )
        self.assertNotIn(
            "window_evaluation_failed",
            {
                window.error_code
                for symbol in result.symbols
                for window in symbol.windows
                if window.error_code is not None
            },
        )
        first_window = result.symbols[0].windows[0]
        self.assertEqual(
            tuple(dict(item) for item in first_window.neighborhood_parameters),
            (
                {"long_window": 4, "short_window": 3},
                {"long_window": 5, "short_window": 2},
                {"long_window": 5, "short_window": 3},
            ),
        )


if __name__ == "__main__":
    unittest.main()

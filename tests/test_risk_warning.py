import unittest
import pandas as pd
import numpy as np

from tw_stock_tool.scanners.risk_warning import detect_risk_warning

class TestRiskWarning(unittest.TestCase):
    def test_missing_close_returns_error(self):
        df = pd.DataFrame({"Volume": [100]})
        result = detect_risk_warning(df)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "error")

    def test_score_below_threshold_returns_none(self):
        df = pd.DataFrame({"Close": [100]}, index=[pd.Timestamp("2024-01-01")])
        result = detect_risk_warning(df, min_score=2.0)
        self.assertIsNone(result)

    def test_rsi_over_80_and_close_below_ma(self):
        # RSI > 80 (+1), close < MA20 (+1) -> score 2.0
        df = pd.DataFrame({
            "Close": [100],
            "MA20": [110],
            "MA60": [90],
            "RSI14": [85]
        }, index=[pd.Timestamp("2024-01-01")])
        result = detect_risk_warning(df, min_score=2.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.score, 2.0)
        self.assertIn("rsi_over_80", result.risks)
        self.assertIn("close_below_ma20", result.risks)
        self.assertNotIn("close_below_ma60", result.risks)

    def test_abnormal_volume_down_day(self):
        # 20 rows. Volume ratio >= 1.5, close < prev_close (+1)
        # close < ma60 (+1) -> 2.0
        volumes = [100] * 19 + [160]
        closes = [100] * 19 + [90]
        df = pd.DataFrame({
            "Close": closes,
            "Volume": volumes,
            "MA60": [95] * 20
        }, index=pd.date_range("2024-01-01", periods=20))
        
        result = detect_risk_warning(df, min_score=2.0)
        self.assertIsNotNone(result)
        self.assertIn("abnormal_volume_down_day", result.risks)
        self.assertIn("close_below_ma60", result.risks)

    def test_large_drawdown_recently(self):
        # 20 rows. High is 100, last close is 89 (>10% drop) (+1.5)
        # close < ma20 (+1) -> 2.5
        closes = [100] * 19 + [89]
        df = pd.DataFrame({
            "Close": closes,
            "MA20": [95] * 20
        }, index=pd.date_range("2024-01-01", periods=20))
        
        result = detect_risk_warning(df, min_score=2.0)
        self.assertIsNotNone(result)
        self.assertIn("large_drawdown_10pct", result.risks)

    def test_volume_spike_but_close_weak(self):
        # vol ratio >= 2.0 and close <= prev_close (+1.5)
        # rsi > 80 (+1) -> 2.5
        volumes = [100] * 19 + [300]
        closes = [100] * 19 + [100]
        df = pd.DataFrame({
            "Close": closes,
            "Volume": volumes,
            "RSI": [85] * 20
        }, index=pd.date_range("2024-01-01", periods=20))
        
        result = detect_risk_warning(df, min_score=2.0)
        self.assertIsNotNone(result)
        self.assertIn("volume_spike_but_close_weak", result.risks)
        self.assertIn("rsi_over_80", result.risks)

if __name__ == "__main__":
    unittest.main()

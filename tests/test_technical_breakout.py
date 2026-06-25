import unittest
import pandas as pd
import numpy as np

from tw_stock_tool.scanners.technical_breakout import detect_technical_breakout

class TestTechnicalBreakout(unittest.TestCase):
    def test_missing_close_returns_error(self):
        df = pd.DataFrame({"Volume": [100]})
        result = detect_technical_breakout(df)
        self.assertIsNotNone(result)
        self.assertEqual(result.status, "error")

    def test_score_below_threshold_returns_none(self):
        df = pd.DataFrame({"Close": [100]}, index=[pd.Timestamp("2024-01-01")])
        result = detect_technical_breakout(df, min_score=3.0)
        self.assertIsNone(result)

    def test_close_above_ma_and_macd(self):
        # close > MA20 (+1), close > MA60 (+1), MACD > 0 (+1) = score 3
        df = pd.DataFrame({
            "Close": [100],
            "MA20": [90],
            "MA60": [80],
            "MACD": [1.5]
        }, index=[pd.Timestamp("2024-01-01")])
        result = detect_technical_breakout(df, min_score=3.0)
        self.assertIsNotNone(result)
        self.assertEqual(result.score, 3.0)
        self.assertIn("close_above_ma20", result.signals)
        self.assertIn("close_above_ma60", result.signals)
        self.assertIn("macd_positive_or_turning", result.signals)

    def test_break_20d_high(self):
        # 20 rows. Close is increasing. Last row breaks high (+1.5)
        # Close > MA20 (+1), Close > MA60 (+1) -> score 3.5
        closes = list(range(80, 100))
        df = pd.DataFrame({
            "Close": closes,
            "MA20": [70] * 20,
            "MA60": [60] * 20,
        }, index=pd.date_range("2024-01-01", periods=20))
        
        result = detect_technical_breakout(df, min_score=3.0)
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.score, 3.5)
        self.assertIn("close_break_20d_high", result.signals)

    def test_volume_spike_and_rsi_healthy(self):
        # Volume ratio >= 1.5 (+1.5), RSI between 50-70 (+1) -> 2.5
        # plus MACD turning (+1) -> 3.5
        volumes = [100] * 19 + [200]
        df = pd.DataFrame({
            "Close": [100] * 20,
            "Volume": volumes,
            "RSI14": [None] * 19 + [60],
            "MACD": [1.0] * 18 + [1.0, 2.0]
        }, index=pd.date_range("2024-01-01", periods=20))
        
        result = detect_technical_breakout(df, min_score=3.0)
        self.assertIsNotNone(result)
        self.assertIn("volume_ratio_20d_spike", result.signals)
        self.assertIn("rsi_healthy", result.signals)
        self.assertIn("macd_positive_or_turning", result.signals)

if __name__ == "__main__":
    unittest.main()

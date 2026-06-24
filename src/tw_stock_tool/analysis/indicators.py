import numpy as np
import pandas as pd


class IndicatorError(Exception):
    pass


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _stochastic_kd(
    df: pd.DataFrame,
    period: int = 9,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> tuple[pd.Series, pd.Series]:
    low_n = df["Low"].rolling(period).min()
    high_n = df["High"].rolling(period).max()
    rsv = (df["Close"] - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1 / k_smooth, adjust=False).mean()
    d = k.ewm(alpha=1 / d_smooth, adjust=False).mean()
    return k, d


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift(1)).abs()
    lc = (df["Low"] - df["Close"].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) < 30:
        raise IndicatorError("資料筆數不足，至少需要 30 筆以上才能穩定計算指標。")

    out = df.copy()
    out["MA5"] = out["Close"].rolling(5).mean()
    out["MA20"] = out["Close"].rolling(20).mean()
    out["MA60"] = out["Close"].rolling(60).mean()
    out["MA120"] = out["Close"].rolling(120).mean()

    out["RSI"] = _rsi(out["Close"], 14)

    ema12 = out["Close"].ewm(span=12, adjust=False).mean()
    ema26 = out["Close"].ewm(span=26, adjust=False).mean()
    out["MACD"] = ema12 - ema26
    out["MACD_Signal"] = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_Hist"] = out["MACD"] - out["MACD_Signal"]

    out["K"], out["D"] = _stochastic_kd(out)

    out["BB_Middle"] = out["Close"].rolling(20).mean()
    bb_std = out["Close"].rolling(20).std()
    out["BB_Upper"] = out["BB_Middle"] + 2 * bb_std
    out["BB_Lower"] = out["BB_Middle"] - 2 * bb_std

    out["ATR"] = _atr(out, 14)
    out["OBV"] = _obv(out["Close"], out["Volume"])

    out["Volume_MA20"] = out["Volume"].rolling(20).mean()
    out["Volume_Ratio"] = out["Volume"] / out["Volume_MA20"].replace(0, np.nan)
    return out

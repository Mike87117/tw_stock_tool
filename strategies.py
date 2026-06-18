import pandas as pd


def _with_signal(df: pd.DataFrame, signal: pd.Series) -> pd.DataFrame:
    out = df.copy()
    out["Signal"] = signal
    return out[["Close", "Signal"]]


def score_strategy(df: pd.DataFrame) -> pd.DataFrame:
    if "Signal" not in df.columns:
        raise ValueError("score_strategy 需要 Signal 欄位。")
    return df[["Close", "Signal"]].copy()


def ma_cross_strategy(
    df: pd.DataFrame,
    short_window: int = 5,
    long_window: int = 20,
) -> pd.DataFrame:
    if short_window <= 0 or long_window <= 0:
        raise ValueError("MA 週期必須大於 0。")
    if short_window >= long_window:
        raise ValueError("短期 MA 週期必須小於長期 MA 週期。")

    short_ma = df["Close"].rolling(short_window).mean()
    long_ma = df["Close"].rolling(long_window).mean()
    prev_short = short_ma.shift(1)
    prev_long = long_ma.shift(1)
    signal = pd.Series("HOLD", index=df.index, dtype=object)
    signal[(prev_short <= prev_long) & (short_ma > long_ma)] = "BUY"
    signal[(prev_short >= prev_long) & (short_ma < long_ma)] = "SELL"
    return _with_signal(df, signal)


def macd_strategy(df: pd.DataFrame) -> pd.DataFrame:
    prev_macd = df["MACD"].shift(1)
    prev_signal = df["MACD_Signal"].shift(1)
    signal = pd.Series("HOLD", index=df.index, dtype=object)
    signal[(prev_macd <= prev_signal) & (df["MACD"] > df["MACD_Signal"])] = "BUY"
    signal[(prev_macd >= prev_signal) & (df["MACD"] < df["MACD_Signal"])] = "SELL"
    return _with_signal(df, signal)


def rsi_strategy(
    df: pd.DataFrame,
    buy_below: float = 30,
    sell_above: float = 70,
) -> pd.DataFrame:
    if not 0 <= buy_below < sell_above <= 100:
        raise ValueError("RSI 參數需符合 0 <= buy_below < sell_above <= 100。")

    signal = pd.Series("HOLD", index=df.index, dtype=object)
    signal[df["RSI"] < buy_below] = "BUY"
    signal[df["RSI"] > sell_above] = "SELL"
    return _with_signal(df, signal)


STRATEGIES = {
    "score_strategy": score_strategy,
    "ma_cross_strategy": ma_cross_strategy,
    "macd_strategy": macd_strategy,
    "rsi_strategy": rsi_strategy,
}

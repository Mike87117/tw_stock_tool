import pandas as pd


def _with_signal(df: pd.DataFrame, signal: pd.Series) -> pd.DataFrame:
    out = df.copy()
    out["Signal"] = signal
    return out[["Close", "Signal"]]


def score_strategy(
    df: pd.DataFrame,
    buy_score: float | None = None,
    sell_score: float | None = None,
) -> pd.DataFrame:
    if "Close" not in df.columns:
        raise ValueError("score_strategy requires Close column.")

    if buy_score is None and sell_score is None:
        if "Signal" not in df.columns:
            raise ValueError("score_strategy requires Signal column when score thresholds are not set.")
        return df[["Close", "Signal"]].copy()

    if buy_score is None or sell_score is None:
        raise ValueError("buy_score and sell_score must be set together.")
    if buy_score <= sell_score:
        raise ValueError("buy_score must be greater than sell_score.")
    if "Score" not in df.columns:
        raise ValueError("score_strategy requires Score column when score thresholds are set.")

    score = pd.to_numeric(df["Score"], errors="coerce")
    signal = pd.Series("HOLD", index=df.index, dtype=object)
    signal[score >= buy_score] = "BUY"
    signal[score <= sell_score] = "SELL"
    return _with_signal(df, signal)


def ma_cross_strategy(
    df: pd.DataFrame,
    short_window: int = 5,
    long_window: int = 20,
) -> pd.DataFrame:
    if short_window <= 0 or long_window <= 0:
        raise ValueError("MA windows must be greater than 0.")
    if short_window >= long_window:
        raise ValueError("short_window must be less than long_window.")

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
        raise ValueError("RSI parameters must satisfy 0 <= buy_below < sell_above <= 100.")

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

import numpy as np
import pandas as pd

SIGNAL_BUY = "BUY"
SIGNAL_SELL = "SELL"
SIGNAL_HOLD = "HOLD"
SIGNAL_WATCH = "WATCH"

SCORE_WEIGHTS = {
    "bullish_stack": 2.0,
    "golden_cross": 2.0,
    "macd_bull": 1.0,
    "volume_burst": 1.0,
    "breakout_upper": 1.0,
    "rsi_hot": -1.0,
    "bearish_stack": -2.0,
    "death_cross": -2.0,
    "macd_weak": -1.0,
    "break_lower": -1.0,
}

SIGNAL_THRESHOLDS = {
    "buy_min": 4.0,
    "watch_min": 1.0,
    "watch_max": 3.0,
    "hold_min": -1.0,
    "hold_max": 0.0,
    "sell_max": -2.0,
}


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    prev_ma5 = out["MA5"].shift(1)
    prev_ma20 = out["MA20"].shift(1)
    golden_cross = (prev_ma5 <= prev_ma20) & (out["MA5"] > out["MA20"])
    death_cross = (prev_ma5 >= prev_ma20) & (out["MA5"] < out["MA20"])

    bullish_stack = (out["Close"] > out["MA20"]) & (out["MA20"] > out["MA60"])
    bearish_stack = (out["Close"] < out["MA20"]) & (out["MA20"] < out["MA60"])
    macd_bull = out["MACD"] > out["MACD_Signal"]
    macd_weak = out["MACD"] < out["MACD_Signal"]
    rsi_hot = out["RSI"] > 70
    volume_burst = out["Volume"] > (out["Volume_MA20"] * 1.5)
    breakout_upper = out["Close"] > out["BB_Upper"]
    break_lower = out["Close"] < out["BB_Lower"]

    score = np.zeros(len(out), dtype=float)
    score += bullish_stack.astype(int) * SCORE_WEIGHTS["bullish_stack"]
    score += golden_cross.astype(int) * SCORE_WEIGHTS["golden_cross"]
    score += macd_bull.astype(int) * SCORE_WEIGHTS["macd_bull"]
    score += volume_burst.astype(int) * SCORE_WEIGHTS["volume_burst"]
    score += breakout_upper.astype(int) * SCORE_WEIGHTS["breakout_upper"]
    score += rsi_hot.astype(int) * SCORE_WEIGHTS["rsi_hot"]
    score += bearish_stack.astype(int) * SCORE_WEIGHTS["bearish_stack"]
    score += death_cross.astype(int) * SCORE_WEIGHTS["death_cross"]
    score += macd_weak.astype(int) * SCORE_WEIGHTS["macd_weak"]
    score += break_lower.astype(int) * SCORE_WEIGHTS["break_lower"]

    out["Score"] = score
    signal = np.full(len(out), SIGNAL_HOLD, dtype=object)
    signal[out["Score"] >= SIGNAL_THRESHOLDS["buy_min"]] = SIGNAL_BUY
    signal[
        (out["Score"] >= SIGNAL_THRESHOLDS["watch_min"])
        & (out["Score"] <= SIGNAL_THRESHOLDS["watch_max"])
    ] = SIGNAL_WATCH
    signal[
        (out["Score"] >= SIGNAL_THRESHOLDS["hold_min"])
        & (out["Score"] <= SIGNAL_THRESHOLDS["hold_max"])
    ] = SIGNAL_HOLD
    signal[out["Score"] <= SIGNAL_THRESHOLDS["sell_max"]] = SIGNAL_SELL
    out["Signal"] = signal

    out["Golden_Cross"] = golden_cross
    out["Death_Cross"] = death_cross
    out["Bullish_Stack"] = bullish_stack
    out["Bearish_Stack"] = bearish_stack
    out["MACD_Bull"] = macd_bull
    out["MACD_Weak"] = macd_weak
    out["RSI_Hot"] = rsi_hot
    out["RSI_Cold"] = out["RSI"] < 30
    out["Volume_Burst"] = volume_burst
    out["Breakout_Upper"] = breakout_upper
    out["Breakdown_Lower"] = break_lower
    return out


def latest_analysis_text(row: pd.Series) -> str:
    signal = str(row.get("Signal", SIGNAL_HOLD))
    score = row.get("Score", 0)
    lead_text = {
        SIGNAL_BUY: f"目前訊號為 BUY，技術分數 {score}，多方條件較集中",
        SIGNAL_WATCH: f"目前訊號為 WATCH，技術分數 {score}，可列入觀察但仍需等待確認",
        SIGNAL_HOLD: f"目前訊號為 HOLD，技術分數 {score}，整體偏中性",
        SIGNAL_SELL: f"目前訊號為 SELL，技術分數 {score}，空方或風險條件較明顯",
    }.get(signal, f"目前訊號為 {signal}，技術分數 {score}")

    notes = []
    if row.get("Bullish_Stack", False):
        notes.append("目前為多頭排列")
    if row.get("Bearish_Stack", False):
        notes.append("目前為空頭排列")
    if row.get("MACD_Bull", False):
        notes.append("MACD 偏多")
    if row.get("MACD_Weak", False):
        notes.append("MACD 偏弱")
    if row.get("Volume_Burst", False):
        notes.append("成交量放大")
    if row.get("Breakout_Upper", False):
        notes.append("突破布林上軌")
    if row.get("Breakdown_Lower", False):
        notes.append("跌破布林下軌")

    risks = []
    if row.get("RSI_Hot", False):
        risks.append("RSI 已過熱，需注意追高風險")
    if row.get("RSI_Cold", False):
        risks.append("RSI 偏低，留意反彈與續跌風險")

    condition_text = "，".join(notes) if notes else "未出現明顯技術條件"
    text = f"{lead_text}。條件：{condition_text}。"
    if risks:
        text += " 風險：" + "；".join(risks) + "。"
    return text

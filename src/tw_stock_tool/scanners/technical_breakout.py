import pandas as pd
from tw_stock_tool.scanners.candidate import StockCandidate

def detect_technical_breakout(df: pd.DataFrame, stock_id: str = "", stock_name: str | None = None, min_score: float = 3.0) -> StockCandidate | None:
    if df.empty or "Close" not in df.columns:
        return StockCandidate(
            date=None, stock=stock_id, name=stock_name, category="technical_breakout",
            signal="BREAKOUT_WATCH", score=0, close=None, volume_ratio_20d=None, rsi14=None,
            ma20=None, ma60=None, macd=None, status="error", error="Missing Close data"
        )
    
    last_row = df.iloc[-1]
    date = df.index[-1]
    close = float(last_row["Close"])
    
    score = 0.0
    signals = []
    
    # 1. close_above_ma20
    ma20 = float(last_row["MA20"]) if "MA20" in df.columns and not pd.isna(last_row["MA20"]) else None
    if ma20 is not None and close > ma20:
        score += 1.0
        signals.append("close_above_ma20")
        
    # 2. close_above_ma60
    ma60 = float(last_row["MA60"]) if "MA60" in df.columns and not pd.isna(last_row["MA60"]) else None
    if ma60 is not None and close > ma60:
        score += 1.0
        signals.append("close_above_ma60")
        
    # 3. close_break_20d_high
    if len(df) >= 20:
        high_20d = df["Close"].iloc[-20:].max()
        if close >= high_20d:
            score += 1.5
            signals.append("close_break_20d_high")
            
    # 4. volume_ratio_20d >= 1.5
    vol_ratio = None
    if "Volume" in df.columns:
        vol = float(last_row["Volume"])
        if len(df) >= 20:
            avg_vol_20d = df["Volume"].iloc[-20:].mean()
            if avg_vol_20d > 0:
                vol_ratio = vol / avg_vol_20d
                if vol_ratio >= 1.5:
                    score += 1.5
                    signals.append("volume_ratio_20d_spike")
    
    # 5. rsi14 between 50 and 70
    rsi = None
    rsi_col = "RSI14" if "RSI14" in df.columns else ("RSI" if "RSI" in df.columns else None)
    if rsi_col and not pd.isna(last_row[rsi_col]):
        rsi = float(last_row[rsi_col])
        if 50 <= rsi <= 70:
            score += 1.0
            signals.append("rsi_healthy")
            
    # 6. macd_positive_or_turning
    macd = float(last_row["MACD"]) if "MACD" in df.columns and not pd.isna(last_row["MACD"]) else None
    if macd is not None:
        is_turning = False
        if len(df) >= 2:
            prev_macd = float(df["MACD"].iloc[-2]) if not pd.isna(df["MACD"].iloc[-2]) else None
            if prev_macd is not None and macd > prev_macd:
                is_turning = True
        
        if macd > 0 or is_turning:
            score += 1.0
            signals.append("macd_positive_or_turning")
            
    if score < min_score:
        return None
        
    return StockCandidate(
        date=date, stock=stock_id, name=stock_name, category="technical_breakout",
        signal="BREAKOUT_WATCH", score=score, close=close, volume_ratio_20d=vol_ratio,
        rsi14=rsi, ma20=ma20, ma60=ma60, macd=macd, signals=signals, status="ok"
    )

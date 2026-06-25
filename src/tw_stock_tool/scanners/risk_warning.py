import pandas as pd
from tw_stock_tool.scanners.candidate import StockCandidate

def detect_risk_warning(df: pd.DataFrame, stock_id: str = "", stock_name: str | None = None, min_score: float = 2.0) -> StockCandidate | None:
    if df.empty or "Close" not in df.columns:
        return StockCandidate(
            date=None, stock=stock_id, name=stock_name, category="risk_warning",
            signal="RISK_WARNING", score=0, close=None, volume_ratio_20d=None, rsi14=None,
            ma20=None, ma60=None, macd=None, status="error", error="Missing Close data"
        )
    
    last_row = df.iloc[-1]
    date = df.index[-1]
    close = float(last_row["Close"])
    
    score = 0.0
    risks = []
    
    # 1. rsi14_over_80
    rsi = None
    rsi_col = "RSI14" if "RSI14" in df.columns else ("RSI" if "RSI" in df.columns else None)
    if rsi_col and not pd.isna(last_row[rsi_col]):
        rsi = float(last_row[rsi_col])
        if rsi > 80:
            score += 1.0
            risks.append("rsi_over_80")

    # 2. close_below_ma20
    ma20 = float(last_row["MA20"]) if "MA20" in df.columns and not pd.isna(last_row["MA20"]) else None
    if ma20 is not None and close < ma20:
        score += 1.0
        risks.append("close_below_ma20")
        
    # 3. close_below_ma60
    ma60 = float(last_row["MA60"]) if "MA60" in df.columns and not pd.isna(last_row["MA60"]) else None
    if ma60 is not None and close < ma60:
        score += 1.0
        risks.append("close_below_ma60")
        
    vol_ratio = None
    if "Volume" in df.columns and len(df) >= 20:
        vol = float(last_row["Volume"])
        avg_vol_20d = df["Volume"].iloc[-20:].mean()
        if avg_vol_20d > 0:
            vol_ratio = vol / avg_vol_20d
            
    # 4. abnormal_volume_down_day
    if vol_ratio is not None and vol_ratio >= 1.5 and len(df) >= 2:
        prev_close = float(df["Close"].iloc[-2])
        if close < prev_close:
            score += 1.0
            risks.append("abnormal_volume_down_day")
            
    # 5. large_drawdown_recently (10% drop from 20d high)
    if len(df) >= 20:
        high_20d = df["Close"].iloc[-20:].max()
        if high_20d > 0 and (high_20d - close) / high_20d >= 0.10:
            score += 1.5
            risks.append("large_drawdown_10pct")
            
    # 6. volume_spike_but_close_weak
    if vol_ratio is not None and vol_ratio >= 2.0 and len(df) >= 2:
        prev_close = float(df["Close"].iloc[-2])
        if close <= prev_close: # simplified weak condition
            score += 1.5
            risks.append("volume_spike_but_close_weak")
            
    macd = float(last_row["MACD"]) if "MACD" in df.columns and not pd.isna(last_row["MACD"]) else None
            
    if score < min_score:
        return None
        
    return StockCandidate(
        date=date, stock=stock_id, name=stock_name, category="risk_warning",
        signal="RISK_WARNING", score=score, close=close, volume_ratio_20d=vol_ratio,
        rsi14=rsi, ma20=ma20, ma60=ma60, macd=macd, risks=risks, status="ok"
    )

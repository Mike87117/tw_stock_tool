import pandas as pd
from typing import Iterable
from pathlib import Path

from tw_stock_tool.analysis.analysis import analyze_stock
from tw_stock_tool.scanners.technical_breakout import detect_technical_breakout
from tw_stock_tool.scanners.risk_warning import detect_risk_warning
from tw_stock_tool.scanners.candidate import StockCandidate
from tw_stock_tool.utils.config import DEFAULT_PERIOD

def build_daily_watchlist(
    stock_ids: Iterable[str],
    period: str = DEFAULT_PERIOD,
    stock_limit: int | None = None,
    force_refresh: bool = False,
    breakout_min_score: float = 3.0,
    risk_min_score: float = 2.0,
) -> pd.DataFrame:
    stocks = list(stock_ids)
    if stock_limit is not None and stock_limit > 0:
        stocks = stocks[:stock_limit]
        
    candidates = []
    
    for stock_id in stocks:
        try:
            analysis = analyze_stock(
                stock_id=stock_id,
                period=period,
                force_refresh=force_refresh
            )
            df = analysis.signal_df
            name = analysis.symbol
            
            breakout_cand = detect_technical_breakout(df, stock_id=stock_id, stock_name=name, min_score=breakout_min_score)
            if breakout_cand:
                candidates.append(breakout_cand.to_dict())
                
            risk_cand = detect_risk_warning(df, stock_id=stock_id, stock_name=name, min_score=risk_min_score)
            if risk_cand:
                candidates.append(risk_cand.to_dict())
                
        except Exception as e:
            cand = StockCandidate(
                date=None, stock=stock_id, name=None, category="error", signal="ERROR",
                score=0, close=None, volume_ratio_20d=None, rsi14=None, ma20=None,
                ma60=None, macd=None, status="error", error=str(e)
            )
            candidates.append(cand.to_dict())
            
    if not candidates:
        dummy = StockCandidate(date=None, stock="", name=None, category="", signal="", score=0, close=None, volume_ratio_20d=None, rsi14=None, ma20=None, ma60=None, macd=None)
        return pd.DataFrame(columns=list(dummy.to_dict().keys()))
        
    return pd.DataFrame(candidates)

def export_daily_watchlist_excel(df: pd.DataFrame, output: str | None = None) -> Path:
    if output is None:
        out_path = Path("output") / "daily_watchlist.xlsx"
    else:
        out_path = Path(output)
        if out_path.is_dir() or not out_path.suffix:
            out_path = out_path / "daily_watchlist.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="All")
            
            breakout_df = df[df["Category"] == "technical_breakout"]
            if not breakout_df.empty:
                breakout_df.to_excel(writer, index=False, sheet_name="Technical Breakout")
                
            risk_df = df[df["Category"] == "risk_warning"]
            if not risk_df.empty:
                risk_df.to_excel(writer, index=False, sheet_name="Risk Warning")
                
            error_df = df[df["Status"] != "ok"]
            if not error_df.empty:
                error_df.to_excel(writer, index=False, sheet_name="Errors")
                
    except Exception as exc:
        raise ValueError(f"Failed to write Excel: {exc}") from exc
        
    return out_path

def export_daily_watchlist_markdown(df: pd.DataFrame, output: str | None = None) -> Path:
    if output is None:
        out_path = Path("output") / "daily_watchlist.md"
    else:
        out_path = Path(output)
        if out_path.is_dir() or not out_path.suffix:
            out_path = out_path / "daily_watchlist.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    md_lines = [
        "# Daily Watchlist",
        "",
        "> Research candidates only, not investment advice.",
        ""
    ]
    
    def df_to_md_table(sub_df):
        cols = ["Stock", "Name", "Score", "Close", "Signals", "Risks", "Error"]
        disp_cols = [c for c in cols if c in sub_df.columns]
        disp_df = sub_df[disp_cols].copy()
        disp_df = disp_df.fillna("")
        
        if disp_df.empty:
            return ""
            
        lines = []
        header = "| " + " | ".join(disp_cols) + " |"
        separator = "| " + " | ".join(["---"] * len(disp_cols)) + " |"
        lines.append(header)
        lines.append(separator)
        
        for _, row in disp_df.iterrows():
            row_str = "| " + " | ".join(str(row[c]) for c in disp_cols) + " |"
            lines.append(row_str)
            
        return "\n".join(lines)
        
    breakout_df = df[df["Category"] == "technical_breakout"]
    md_lines.append("## Technical Breakout")
    if breakout_df.empty:
        md_lines.append("No technical breakout candidates.")
    else:
        md_lines.append(df_to_md_table(breakout_df))
    md_lines.append("")
    
    risk_df = df[df["Category"] == "risk_warning"]
    md_lines.append("## Risk Warning")
    if risk_df.empty:
        md_lines.append("No risk warning candidates.")
    else:
        md_lines.append(df_to_md_table(risk_df))
    md_lines.append("")
        
    error_df = df[df["Status"] != "ok"]
    md_lines.append("## Errors")
    if error_df.empty:
        md_lines.append("No errors.")
    else:
        md_lines.append(df_to_md_table(error_df))
        
    out_path.write_text("\n".join(md_lines), encoding="utf-8")
    return out_path

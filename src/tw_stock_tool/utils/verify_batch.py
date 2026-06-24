import argparse
from pathlib import Path

import pandas as pd
import requests

from tw_stock_tool.utils.config import DEFAULT_INTERVAL, OUTPUT_DIR
from tw_stock_tool.data.data_loader import download_tw_stock
from tw_stock_tool.analysis.indicators import add_indicators
from tw_stock_tool.analysis.signals import generate_signals


def _get_twse_latest(stock_id: str, date_yyyymm01: str) -> dict:
    url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"
    params = {"response": "json", "date": date_yyyymm01, "stockNo": stock_id}
    obj = requests.get(url, params=params, timeout=20).json()
    if obj.get("stat") != "OK" or not obj.get("data"):
        raise ValueError(f"TWSE 無資料: {stock_id}")

    row = obj["data"][-1]
    return {
        "TWSE Date": row[0],
        "TWSE Open": float(row[3].replace(",", "")),
        "TWSE High": float(row[4].replace(",", "")),
        "TWSE Low": float(row[5].replace(",", "")),
        "TWSE Close": float(row[6].replace(",", "")),
        "TWSE Volume": int(row[1].replace(",", "")),
    }


def _roc_date(ts: pd.Timestamp) -> str:
    return f"{ts.year - 1911}/{ts.month:02d}/{ts.day:02d}"


def verify(stocks: list[str], period: str, twse_month: str) -> pd.DataFrame:
    rows = []
    for stock_id in stocks:
        try:
            raw_df, symbol = download_tw_stock(stock_id, period=period, interval=DEFAULT_INTERVAL)
            sig_df = generate_signals(add_indicators(raw_df)).dropna(
                subset=["MA20", "MA60", "MACD_Signal", "RSI"]
            )
            if sig_df.empty:
                rows.append({"Stock ID": stock_id, "Status": "NO_SIGNAL_DATA"})
                continue

            latest = sig_df.iloc[-1]
            twse = _get_twse_latest(stock_id, twse_month)

            program_date = _roc_date(pd.Timestamp(latest.name))
            program_open = round(float(latest["Open"]), 2)
            program_high = round(float(latest["High"]), 2)
            program_low = round(float(latest["Low"]), 2)
            program_close = round(float(latest["Close"]), 2)
            program_volume = int(latest["Volume"])

            match_date = program_date == twse["TWSE Date"]
            match_open = program_open == round(twse["TWSE Open"], 2)
            match_high = program_high == round(twse["TWSE High"], 2)
            match_low = program_low == round(twse["TWSE Low"], 2)
            match_close = program_close == round(twse["TWSE Close"], 2)
            match_ohlc = match_open and match_high and match_low and match_close
            match_volume = program_volume == twse["TWSE Volume"]

            rows.append(
                {
                    "Stock ID": stock_id,
                    "Symbol": symbol,
                    "Status": "OK",
                    "Program Date": program_date,
                    "TWSE Date": twse["TWSE Date"],
                    "Match Date": match_date,
                    "Program Open": program_open,
                    "TWSE Open": twse["TWSE Open"],
                    "Program High": program_high,
                    "TWSE High": twse["TWSE High"],
                    "Program Low": program_low,
                    "TWSE Low": twse["TWSE Low"],
                    "Program Close": program_close,
                    "TWSE Close": twse["TWSE Close"],
                    "Match OHLC": match_ohlc,
                    "Program Volume": program_volume,
                    "TWSE Volume": twse["TWSE Volume"],
                    "Volume Ratio (Program/TWSE)": round(program_volume / twse["TWSE Volume"], 6)
                    if twse["TWSE Volume"]
                    else None,
                    "Match Volume": match_volume,
                    "All Match": match_date and match_ohlc and match_volume,
                    "Signal": str(latest["Signal"]),
                    "Score": int(latest["Score"]),
                }
            )
        except Exception as exc:
            rows.append({"Stock ID": stock_id, "Status": "ERROR", "Error": str(exc)})

    return pd.DataFrame(rows)


def write_report(
    df: pd.DataFrame,
    stocks: list[str],
    period: str,
    twse_month: str,
    output_path: Path,
) -> None:
    ok = df[df["Status"] == "OK"] if "Status" in df.columns else pd.DataFrame()
    summary = pd.DataFrame(
        [
            {
                "Stocks": ",".join(stocks),
                "Period": period,
                "TWSE Month": twse_month,
                "Total": len(df),
                "OK Count": int((df["Status"] == "OK").sum()) if "Status" in df.columns else 0,
                "All Match Count": int(ok["All Match"].sum()) if not ok.empty else 0,
                "Mismatch Count": int((~ok["All Match"]).sum()) if not ok.empty else 0,
                "Volume Mismatch Count": int((~ok["Match Volume"]).sum()) if not ok.empty else 0,
                "Date Mismatch Count": int((~ok["Match Date"]).sum()) if not ok.empty else 0,
                "OHLC Mismatch Count": int((~ok["Match OHLC"]).sum()) if not ok.empty else 0,
            }
        ]
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary.to_excel(writer, index=False, sheet_name="Summary")
        df.to_excel(writer, index=False, sheet_name="Comparison")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch compare program output vs TWSE official data."
    )
    parser.add_argument(
        "--stocks",
        nargs="+",
        default=["2330", "2317", "2454", "2308", "2882", "6505"],
    )
    parser.add_argument("--period", default="1y")
    parser.add_argument("--twse-month", default="20260501")
    parser.add_argument("--output", default=str(OUTPUT_DIR / "batch_verification.xlsx"))
    args = parser.parse_args()

    df = verify(args.stocks, args.period, args.twse_month)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(df, args.stocks, args.period, args.twse_month, output_path)

    print(f"已輸出驗證報表: {output_path}")
    if "Status" in df.columns:
        ok = df[df["Status"] == "OK"]
        if not ok.empty:
            print(f"OK 檔數: {len(ok)}")
            print(f"完全一致: {int(ok['All Match'].sum())}")
            print(f"不一致: {int((~ok['All Match']).sum())}")


if __name__ == "__main__":
    main()

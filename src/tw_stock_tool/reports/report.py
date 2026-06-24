from pathlib import Path

import pandas as pd


class ReportError(Exception):
    pass


def export_excel_report(
    stock_id: str,
    df: pd.DataFrame,
    backtest_result: dict,
    summary: dict,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{stock_id}_report.xlsx"

    latest_summary = pd.DataFrame([summary])
    backtest_df = pd.DataFrame(
        [{k: v for k, v in backtest_result.items() if k not in {"Trades", "Equity Curve"}}]
    )

    try:
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Price_Indicators")
            df[["Signal", "Score"]].to_excel(writer, sheet_name="Daily_Signals")
            backtest_df.to_excel(writer, index=False, sheet_name="Backtest_Result")
            latest_summary.to_excel(writer, index=False, sheet_name="Latest_Summary")

            trades = backtest_result.get("Trades")
            if isinstance(trades, pd.DataFrame) and not trades.empty:
                trades.to_excel(writer, index=False, sheet_name="Trades")
    except PermissionError as exc:
        raise ReportError("Excel 檔案可能正在使用中，請先關閉後再試。") from exc
    except Exception as exc:
        raise ReportError(f"匯出 Excel 失敗: {exc}") from exc

    return file_path


def export_stock_ranking(
    ranking_df: pd.DataFrame,
    output_dir: Path,
    base_name: str = "stock_ranking",
    sheet_by_signal: bool = False,
) -> dict[str, Path]:
    if len(ranking_df.columns) == 0:
        raise ReportError("排行榜資料不可缺少欄位。")

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "excel": output_dir / f"{base_name}.xlsx",
        "csv": output_dir / f"{base_name}.csv",
        "html": output_dir / f"{base_name}.html",
    }

    try:
        with pd.ExcelWriter(paths["excel"], engine="openpyxl") as writer:
            ranking_df.to_excel(writer, index=False, sheet_name="Ranking")
            if sheet_by_signal:
                for signal in ["BUY", "WATCH", "HOLD", "SELL"]:
                    subset = ranking_df[ranking_df["Signal"] == signal]
                    if not subset.empty:
                        subset.to_excel(writer, index=False, sheet_name=signal)
                errors = ranking_df[ranking_df["Status"] != "OK"]
                if not errors.empty:
                    errors.to_excel(writer, index=False, sheet_name="ERROR")
        ranking_df.to_csv(paths["csv"], index=False, encoding="utf-8-sig")
        ranking_df.to_html(paths["html"], index=False, escape=False)
    except PermissionError as exc:
        raise ReportError("排行榜檔案可能正在使用中，請先關閉後再試。") from exc
    except Exception as exc:
        raise ReportError(f"匯出排行榜失敗: {exc}") from exc

    return paths

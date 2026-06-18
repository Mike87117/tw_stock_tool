import argparse
from pathlib import Path

from config import (
    DEFAULT_AUTO_ADJUST,
    DEFAULT_INTERVAL,
    DEFAULT_PERIOD,
    OUTPUT_DIR,
    VALID_INTERVALS,
    VALID_PERIODS,
)
from report import ReportError, export_stock_ranking
from scanner import (
    SUPPORTED_SORT_COLUMNS,
    ScanConfig,
    load_stock_ids_from_file,
    normalize_stock_ids,
    scan_stocks,
)


def _ask_stock_ids() -> list[str]:
    print("請輸入股票代號，每行一檔，輸入空白行結束：")
    values = []
    while True:
        value = input().strip()
        if not value:
            break
        values.append(value)
    return normalize_stock_ids(values)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="多股票技術分析掃描器")
    parser.add_argument("--stocks", nargs="*", help="股票代號清單，例如: --stocks 2330 2317 2454")
    parser.add_argument("--file", help="從 txt 載入股票代號，每行一檔")
    parser.add_argument("--period", default=DEFAULT_PERIOD, choices=sorted(VALID_PERIODS))
    parser.add_argument("--interval", default=DEFAULT_INTERVAL, choices=sorted(VALID_INTERVALS))
    parser.add_argument("--workers", type=int, default=8, help="多執行緒數量，預設 8")
    parser.add_argument("--min-score", type=float, help="只輸出分數 >= 指定值的股票")
    parser.add_argument("--min-volume-ratio", type=float, help="只輸出 Volume_Ratio >= 指定值的股票")
    parser.add_argument("--min-close", type=float, help="只輸出 Close >= 指定值的股票")
    parser.add_argument("--max-close", type=float, help="只輸出 Close <= 指定值的股票")
    parser.add_argument("--signals", nargs="+", help="只輸出指定訊號，例如: --signals BUY WATCH")
    parser.add_argument("--sort-by", default="Score", choices=sorted(SUPPORTED_SORT_COLUMNS))
    parser.add_argument("--top", type=int, help="只輸出前 N 名 OK 股票")
    parser.add_argument("--errors-only", action="store_true", help="只輸出失敗股票")
    parser.add_argument("--log-errors", action="store_true", help="將錯誤輸出到 output/scan_errors.log")
    parser.add_argument("--sheet-by-signal", action="store_true", help="Excel 依訊號分 sheet")
    parser.add_argument("--force-refresh", action="store_true", help="忽略今日快取並重新下載")
    parser.add_argument(
        "--auto-adjust",
        action="store_true",
        default=DEFAULT_AUTO_ADJUST,
        help="使用除權息調整後價格",
    )
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="輸出資料夾")
    return parser.parse_args()


def _collect_stock_ids(args: argparse.Namespace) -> list[str]:
    stocks = []
    if args.file:
        stocks.extend(load_stock_ids_from_file(args.file))
    if args.stocks:
        stocks.extend(args.stocks)
    if not stocks:
        stocks = _ask_stock_ids()
    return normalize_stock_ids(stocks)


def _print_progress(current: int, total: int, stock_id: str, status: str) -> None:
    print(f"[{current}/{total}] {stock_id} {status}")


def _write_error_log(ranking_df, output_dir: Path) -> Path | None:
    errors = ranking_df[ranking_df["Status"] != "OK"]
    if errors.empty:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "scan_errors.log"
    lines = [
        f"{row['Stock']}: {row['Error']}"
        for _, row in errors.iterrows()
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return log_path


def main() -> None:
    try:
        args = _parse_args()
        stock_ids = _collect_stock_ids(args)
        config = ScanConfig(
            period=args.period,
            interval=args.interval,
            auto_adjust=args.auto_adjust,
            force_refresh=args.force_refresh,
            max_workers=args.workers,
            min_score=args.min_score,
            min_volume_ratio=args.min_volume_ratio,
            min_close=args.min_close,
            max_close=args.max_close,
            signals=tuple(args.signals) if args.signals else None,
            sort_by=args.sort_by,
            top=args.top,
            errors_only=args.errors_only,
        )

        ranking_df = scan_stocks(stock_ids, config=config, progress_callback=_print_progress)
        output_dir = Path(args.output_dir)
        paths = export_stock_ranking(
            ranking_df,
            output_dir=output_dir,
            sheet_by_signal=args.sheet_by_signal,
        )
        error_log = _write_error_log(ranking_df, output_dir) if args.log_errors else None

        ok_count = int((ranking_df["Status"] == "OK").sum())
        error_count = int((ranking_df["Status"] != "OK").sum())
        print("\n掃描完成")
        print(f"成功: {ok_count}，失敗: {error_count}")
        print(f"Excel: {paths['excel']}")
        print(f"CSV: {paths['csv']}")
        print(f"HTML: {paths['html']}")
        if error_log:
            print(f"錯誤紀錄: {error_log}")
    except (ValueError, ReportError) as exc:
        print(f"錯誤：{exc}")
    except KeyboardInterrupt:
        print("\n已取消掃描。")
    except Exception as exc:
        print(f"未預期錯誤：{exc}")


if __name__ == "__main__":
    main()

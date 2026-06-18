import argparse
import time
from pathlib import Path

import pandas as pd

from config import DEFAULT_PERIOD, OUTPUT_DIR
from scanner import ScanConfig, load_stock_ids_from_file, normalize_stock_ids, scan_stocks


def run_benchmark(
    stock_ids: list[str],
    period: str = DEFAULT_PERIOD,
    workers: int = 8,
    force_refresh: bool = False,
) -> pd.DataFrame:
    stocks = normalize_stock_ids(stock_ids)
    if not stocks:
        raise ValueError("benchmark 股票清單不可空白。")

    start = time.perf_counter()
    result = scan_stocks(
        stocks,
        config=ScanConfig(
            period=period,
            max_workers=workers,
            force_refresh=force_refresh,
        ),
    )
    elapsed = time.perf_counter() - start
    ok_count = int((result["Status"] == "OK").sum())
    error_count = int((result["Status"] != "OK").sum())
    return pd.DataFrame(
        [
            {
                "Stocks": len(stocks),
                "OK": ok_count,
                "ERROR": error_count,
                "Workers": workers,
                "Period": period,
                "Force Refresh": force_refresh,
                "Elapsed Seconds": round(elapsed, 3),
                "Seconds Per Stock": round(elapsed / len(stocks), 3),
            }
        ]
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="多股票掃描 benchmark 工具")
    parser.add_argument("--stocks", nargs="*", help="股票代號清單")
    parser.add_argument("--file", help="從 txt 載入股票代號")
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--output", nargs="?", const="", help="輸出 CSV，可省略路徑使用預設位置")
    return parser.parse_args()


def _collect_stock_ids(args: argparse.Namespace) -> list[str]:
    stocks = []
    if args.file:
        stocks.extend(load_stock_ids_from_file(args.file))
    if args.stocks:
        stocks.extend(args.stocks)
    return normalize_stock_ids(stocks)


def main() -> None:
    try:
        args = _parse_args()
        result = run_benchmark(
            stock_ids=_collect_stock_ids(args),
            period=args.period,
            workers=args.workers,
            force_refresh=args.force_refresh,
        )
        print(result.to_string(index=False))
        if args.output is not None:
            output_path = (
                OUTPUT_DIR / "benchmark.csv"
                if args.output == ""
                else Path(args.output)
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result.to_csv(output_path, index=False, encoding="utf-8-sig")
            print(f"\nbenchmark 已輸出：{output_path}")
    except Exception as exc:
        print(f"錯誤：{exc}")


if __name__ == "__main__":
    main()

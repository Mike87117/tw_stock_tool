import argparse
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from tw_stock_tool.utils.config import DEFAULT_AUTO_ADJUST, DEFAULT_INTERVAL, DEFAULT_PERIOD, OUTPUT_DIR
from tw_stock_tool.analysis.scanner import ScanConfig, load_stock_ids_from_file, normalize_stock_ids, scan_stocks


@dataclass(frozen=True)
class BenchmarkResult:
    summary: pd.DataFrame
    detail: pd.DataFrame
    errors: pd.DataFrame


def _validate_benchmark_inputs(stocks: list[str], workers: int, repeat: int, warmup: int) -> None:
    if not stocks:
        raise ValueError("benchmark stock list cannot be empty.")
    if workers <= 0:
        raise ValueError("workers must be greater than 0.")
    if repeat <= 0:
        raise ValueError("repeat must be greater than 0.")
    if warmup < 0:
        raise ValueError("warmup must be greater than or equal to 0.")


def _scan_once(
    stocks: list[str],
    period: str,
    interval: str,
    auto_adjust: bool,
    workers: int,
    force_refresh: bool,
) -> tuple[pd.DataFrame, float]:
    start = time.perf_counter()
    result = scan_stocks(
        stocks,
        config=ScanConfig(
            period=period,
            interval=interval,
            auto_adjust=auto_adjust,
            max_workers=workers,
            force_refresh=force_refresh,
        ),
    )
    elapsed = time.perf_counter() - start
    return result, elapsed


def _output_paths(output_arg: str | None) -> dict[str, Path] | None:
    if output_arg is None:
        return None
    base = OUTPUT_DIR / "benchmark" if output_arg == "" else Path(output_arg)
    if base.suffix:
        output_dir = base.parent
        stem = base.stem
    else:
        output_dir = base
        stem = "benchmark"
    output_dir.mkdir(parents=True, exist_ok=True)
    return {
        "summary": output_dir / f"{stem}_summary.csv",
        "detail": output_dir / f"{stem}_detail.csv",
        "errors": output_dir / f"{stem}_errors.csv",
    }


def run_benchmark(
    stock_ids: list[str],
    period: str = DEFAULT_PERIOD,
    interval: str = DEFAULT_INTERVAL,
    workers: int = 8,
    force_refresh: bool = False,
    auto_adjust: bool = DEFAULT_AUTO_ADJUST,
    repeat: int = 1,
    warmup: int = 0,
) -> BenchmarkResult:
    stocks = normalize_stock_ids(stock_ids)
    _validate_benchmark_inputs(stocks, workers, repeat, warmup)

    for _ in range(warmup):
        _scan_once(stocks, period, interval, auto_adjust, workers, force_refresh)

    detail_rows: list[dict[str, object]] = []
    error_rows: list[dict[str, object]] = []
    for run_number in range(1, repeat + 1):
        result, elapsed = _scan_once(stocks, period, interval, auto_adjust, workers, force_refresh)
        ok_count = int((result["Status"] == "OK").sum())
        error_count = int((result["Status"] != "OK").sum())
        success_rate = ok_count / len(stocks) * 100
        detail_rows.append(
            {
                "Run": run_number,
                "Stocks": len(stocks),
                "OK": ok_count,
                "ERROR": error_count,
                "Workers": workers,
                "Period": period,
                "Interval": interval,
                "Auto Adjust": auto_adjust,
                "Force Refresh": force_refresh,
                "Elapsed Seconds": round(elapsed, 3),
                "Seconds Per Stock": round(elapsed / len(stocks), 3),
                "Stocks Per Second": round(len(stocks) / elapsed, 3) if elapsed > 0 else 0.0,
                "Success Rate %": round(success_rate, 2),
            }
        )
        errors = result[result["Status"] != "OK"]
        for _, row in errors.iterrows():
            error_rows.append(
                {
                    "Run": run_number,
                    "Stock": row.get("Stock", ""),
                    "Symbol": row.get("Symbol", ""),
                    "Error": row.get("Error", ""),
                }
            )

    detail = pd.DataFrame(detail_rows)
    errors = pd.DataFrame(error_rows, columns=["Run", "Stock", "Symbol", "Error"])
    summary = pd.DataFrame(
        [
            {
                "Runs": repeat,
                "Warmup Runs": warmup,
                "Stocks": len(stocks),
                "Workers": workers,
                "Period": period,
                "Interval": interval,
                "Auto Adjust": auto_adjust,
                "Force Refresh": force_refresh,
                "Avg OK": round(float(detail["OK"].mean()), 2),
                "Avg ERROR": round(float(detail["ERROR"].mean()), 2),
                "Avg Success Rate %": round(float(detail["Success Rate %"].mean()), 2),
                "Avg Elapsed Seconds": round(float(detail["Elapsed Seconds"].mean()), 3),
                "Min Elapsed Seconds": round(float(detail["Elapsed Seconds"].min()), 3),
                "Max Elapsed Seconds": round(float(detail["Elapsed Seconds"].max()), 3),
                "Avg Seconds Per Stock": round(float(detail["Seconds Per Stock"].mean()), 3),
                "Avg Stocks Per Second": round(float(detail["Stocks Per Second"].mean()), 3),
            }
        ]
    )
    return BenchmarkResult(summary=summary, detail=detail, errors=errors)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Multi-stock scan benchmark tool")
    parser.add_argument("--stocks", nargs="*", help="Stock id list")
    parser.add_argument("--file", help="Load stock ids from txt file")
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--interval", default=DEFAULT_INTERVAL)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--repeat", type=int, default=1, help="Measured benchmark runs")
    parser.add_argument("--warmup", type=int, default=0, help="Warmup runs not included in output")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument(
        "--auto-adjust",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_AUTO_ADJUST,
    )
    parser.add_argument("--output", nargs="?", const="", help="Export Summary/Detail/Errors CSV files")
    return parser.parse_args()


def _collect_stock_ids(args: argparse.Namespace) -> list[str]:
    stocks = []
    if args.file:
        stocks.extend(load_stock_ids_from_file(args.file))
    if args.stocks:
        stocks.extend(args.stocks)
    return normalize_stock_ids(stocks)


def _print_section(title: str, df: pd.DataFrame) -> None:
    print(f"\n[{title}]")
    if df.empty:
        print("(empty)")
    else:
        print(df.to_string(index=False))


def main() -> int | None:
    try:
        args = _parse_args()
        result = run_benchmark(
            stock_ids=_collect_stock_ids(args),
            period=args.period,
            interval=args.interval,
            workers=args.workers,
            force_refresh=args.force_refresh,
            auto_adjust=args.auto_adjust,
            repeat=args.repeat,
            warmup=args.warmup,
        )
        _print_section("Summary", result.summary)
        _print_section("Detail", result.detail)
        _print_section("Errors", result.errors)

        paths = _output_paths(args.output)
        if paths:
            result.summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
            result.detail.to_csv(paths["detail"], index=False, encoding="utf-8-sig")
            result.errors.to_csv(paths["errors"], index=False, encoding="utf-8-sig")
            print("\nBenchmark exported:")
            for path in paths.values():
                print(path)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

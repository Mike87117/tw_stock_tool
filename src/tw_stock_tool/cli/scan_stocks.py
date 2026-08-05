import argparse

from tw_stock_tool.application.research_run import ScanRunRequest, run_scan
from tw_stock_tool.application.workspace_run import run_scan_workspace
from tw_stock_tool.application.workspace_summary import workspace_run_paths
from tw_stock_tool.cli._research_run_cli import (
    artifact_path,
    collect_symbol_requests,
    find_exception_cause,
)
from tw_stock_tool.utils.config import (
    DEFAULT_AUTO_ADJUST,
    DEFAULT_INTERVAL,
    DEFAULT_PERIOD,
    OUTPUT_DIR,
    VALID_INTERVALS,
    VALID_PERIODS,
)
# export_stock_ranking and scan_stocks are the pre-application-service legacy
# path. They are no longer called here, but the CLI exit-behavior tests patch
# them on this module and assert they stay uncalled, which is what proves the
# CLI delegates to the application service. Removing them removes that proof.
from tw_stock_tool.reports.report import ReportError, export_stock_ranking  # noqa: F401
from tw_stock_tool.analysis.scanner import (
    SUPPORTED_SORT_COLUMNS,
    ScanConfig,
    normalize_stock_ids,
    scan_stocks,  # noqa: F401  legacy-delegation seam, see comment above
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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="多股票技術分析掃描器")
    parser.add_argument("--stocks", nargs="*", help="股票代號清單，例如: --stocks 2330 2317 2454")
    parser.add_argument("--file", help="從 txt 載入股票代號，每行一檔")
    parser.add_argument("--auto-stock-list", action="store_true", help="Update and use an official stock list before scanning")
    parser.add_argument("--stock-market", choices=("all", "twse", "tpex"), default="all")
    parser.add_argument("--stock-list-output", default="stocks.txt")
    parser.add_argument("--allow-partial-stock-list", action="store_true")
    parser.add_argument("--stock-limit", type=int, help="Only scan the first N collected stocks")
    parser.add_argument("--stock-sample", type=int, help="Randomly scan N collected stocks")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed for --stock-sample")
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
    parser.add_argument("--workspace", help="建立 append-only managed Research Run 的 Workspace 路徑")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="輸出資料夾")
    parser.add_argument("--manifest-path", default=None)
    return parser.parse_args(argv)


def _collect_stock_ids(args: argparse.Namespace) -> list[str]:
    requests = collect_symbol_requests(
        stocks=getattr(args, "stocks", None),
        file_path=getattr(args, "file", None),
        auto_stock_list=getattr(args, "auto_stock_list", False),
        stock_market=getattr(args, "stock_market", "all"),
        stock_list_output=getattr(args, "stock_list_output", "stocks.txt"),
        allow_partial_stock_list=getattr(args, "allow_partial_stock_list", False),
        stock_limit=getattr(args, "stock_limit", None),
        stock_sample=getattr(args, "stock_sample", None),
        random_state=getattr(args, "random_state", 42),
        interactive_supplier=_ask_stock_ids,
    )
    return [request.requested_symbol for request in requests]


def _print_progress(current: int, total: int, stock_id: str, status: str) -> None:
    print(f"[{current}/{total}] {stock_id} {status}", flush=True)


def main() -> int | None:
    try:
        args = _parse_args()
        resolved_symbol_requests = collect_symbol_requests(
            stocks=args.stocks,
            file_path=args.file,
            auto_stock_list=args.auto_stock_list,
            stock_market=args.stock_market,
            stock_list_output=args.stock_list_output,
            allow_partial_stock_list=args.allow_partial_stock_list,
            stock_limit=args.stock_limit,
            stock_sample=args.stock_sample,
            random_state=args.random_state,
            interactive_supplier=_ask_stock_ids,
        )
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
        request = ScanRunRequest(
            symbols=resolved_symbol_requests,
            universe=args.stock_market,
            config=config,
            output_dir=args.output_dir,
            manifest_path=getattr(args, "manifest_path", None),
            sheet_by_signal=args.sheet_by_signal,
            log_errors=args.log_errors,
        )
        if getattr(args, "workspace", None):
            result = run_scan_workspace(request, getattr(args, "workspace", None), progress_callback=_print_progress)
        else:
            result = run_scan(request, progress_callback=_print_progress)
        ranking_df = result.domain_result
        ok_count = int((ranking_df["Status"] == "OK").sum())
        error_count = int((ranking_df["Status"] != "OK").sum())
        if getattr(args, "workspace", None):
            run_directory, manifest_path = workspace_run_paths(getattr(args, "workspace", None), result.manifest)
            print(f"Run ID: {result.manifest.run_id}")
            print(f"Run status: {result.manifest.status}")
            print(f"Run directory: {run_directory}")
            print(f"Manifest path: {manifest_path}")
        print("\n掃描完成")
        print(f"成功: {ok_count}，失敗: {error_count}")
        print(f"Excel: {artifact_path(result, 'scan_ranking_excel')}")
        print(f"CSV: {artifact_path(result, 'scan_ranking_csv')}")
        print(f"HTML: {artifact_path(result, 'scan_ranking_html')}")
        error_log = artifact_path(result, "scan_error_log")
        if error_log:
            print(f"錯誤紀錄: {error_log}")
    except KeyboardInterrupt:
        print("\n已取消掃描。")
        return 1
    except Exception as exc:
        if find_exception_cause(exc, (ValueError, ReportError)) is not None:
            print(f"錯誤：{exc}")
        else:
            print(f"未預期錯誤：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

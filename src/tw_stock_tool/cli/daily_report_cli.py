import argparse
import sys
from pathlib import Path

from tw_stock_tool.utils.config import (
    DEFAULT_PERIOD,
    DEFAULT_INTERVAL,
    DEFAULT_AUTO_ADJUST,
)
from tw_stock_tool.reports.daily_report import (
    DEFAULT_SIGNALS,
    DEFAULT_MIN_SCORE,
    DEFAULT_TOP,
    run_daily_report,
    build_daily_report_data,
    render_daily_report_markdown,
    collect_stock_ids,
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily Report CLI")
    # Selection
    parser.add_argument("--stocks", nargs="*", help="Stock id list")
    parser.add_argument("--file", help="Load stock ids from txt file")
    parser.add_argument("--auto-stock-list", action="store_true")
    parser.add_argument("--stock-market", choices=("all", "twse", "tpex"), default="all")
    parser.add_argument("--stock-list-output", default="stocks.txt")
    parser.add_argument("--allow-partial-stock-list", action="store_true")
    parser.add_argument("--stock-limit", type=int)
    parser.add_argument("--stock-sample", type=int)
    parser.add_argument("--random-state", type=int, default=42)
    
    # Scanning
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--interval", default=DEFAULT_INTERVAL)
    parser.add_argument("--signals", nargs="+", default=list(DEFAULT_SIGNALS))
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--auto-adjust", action=argparse.BooleanOptionalAction, default=DEFAULT_AUTO_ADJUST)
    
    # Output
    parser.add_argument("--output-md", nargs="?", const="", default=None)
    parser.add_argument("--output-dir", default="output")
    return parser.parse_args(argv)

def main() -> None:
    try:
        args = _parse_args()
        
        stock_ids = collect_stock_ids(
            args.stocks,
            args.file,
            auto_stock_list=args.auto_stock_list,
            stock_market=args.stock_market,
            stock_list_output=args.stock_list_output,
            allow_partial_stock_list=args.allow_partial_stock_list,
            stock_limit=args.stock_limit,
            stock_sample=args.stock_sample,
            random_state=args.random_state,
        )
        
        if not stock_ids:
            print("Error: No stocks provided.")
            sys.exit(1)
            
        print(f"Scanning {len(stock_ids)} stocks...")
        summary_df, candidates_df, ranking_df, _ = run_daily_report(
            stock_ids=stock_ids,
            period=args.period,
            interval=args.interval,
            signals=args.signals,
            min_score=args.min_score,
            top=args.top,
            force_refresh=args.force_refresh,
            auto_adjust=args.auto_adjust,
            output=None,
            progress=True,
        )
        
        import datetime
        report_data = build_daily_report_data(
            report_date=datetime.datetime.now().strftime("%Y-%m-%d"),
            stock_universe=list(stock_ids),
            screening_results=summary_df,
            watchlist_candidates=candidates_df,
            backtest_highlights=[],
            parameter_sweep_highlights=[],
            walk_forward_highlights=[],
        )
        
        md_text = render_daily_report_markdown(report_data)
        
        default_output = Path(args.output_dir) / "daily_report.md"
        
        if args.output_md in (None, ""):
            output_md = default_output
        else:
            output_md = Path(args.output_md)
            
        output_md.parent.mkdir(parents=True, exist_ok=True)

        with open(output_md, "w", encoding="utf-8") as f:
            f.write(md_text)
        print(f"\nMarkdown report exported to {output_md}")
        print("\nProcess completed successfully.")

    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()

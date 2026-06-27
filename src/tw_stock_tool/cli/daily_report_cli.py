import argparse
import sys
from pathlib import Path
from typing import Any

from tw_stock_tool.cli.parsers import parse_int_tuple
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
from tw_stock_tool.analysis.analysis import analyze_stock
from tw_stock_tool.backtesting.backtest import run_backtest
from tw_stock_tool.backtesting.parameter_sweep import run_parameter_sweep
from tw_stock_tool.backtesting.walk_forward import run_walk_forward
from tw_stock_tool.backtesting.strategies import STRATEGIES

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
    
    # Deep Dive
    parser.add_argument("--run-backtest", action="store_true", help="Run standard backtest on candidates")
    parser.add_argument("--run-sweep", action="store_true", help="Run parameter sweep on candidates")
    parser.add_argument("--run-walk-forward", action="store_true", help="Run walk-forward on candidates")
    parser.add_argument("--deep-dive-strategy", default="ma_cross", help="Strategy to use for deep dives")
    
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
        
        bt_highlights = []
        ps_highlights = []
        wf_highlights = []
        
        strategy_name = args.deep_dive_strategy
        if strategy_name not in STRATEGIES:
            if f"{strategy_name}_strategy" in STRATEGIES:
                strategy_name = f"{strategy_name}_strategy"
        
        if not candidates_df.empty and (args.run_backtest or args.run_sweep or args.run_walk_forward):
            print(f"\nRunning deep dives using strategy: {strategy_name}")
            
            for stock_id in candidates_df["Stock"].tolist():
                # Backtest
                if args.run_backtest:
                    try:
                        analysis = analyze_stock(stock_id, period=args.period, force_refresh=args.force_refresh)
                        strategy_func = STRATEGIES[strategy_name]
                        df_exec = strategy_func(analysis.indicator_df)
                        bt_result = run_backtest(df_exec)
                        summary = bt_result.get("Summary", {})
                        bt_highlights.append({
                            "Stock": stock_id,
                            "Strategy": args.deep_dive_strategy,
                            "Return": summary.get("Total Return", "N/A"),
                            "WinRate": summary.get("Win Rate", "N/A"),
                        })
                    except Exception as e:
                        bt_highlights.append({"Stock": stock_id, "Strategy": args.deep_dive_strategy, "Error": str(e)})
                        
                # Sweep
                if args.run_sweep:
                    try:
                        sweep_df = run_parameter_sweep(stock_id, args.deep_dive_strategy, period=args.period, force_refresh=args.force_refresh)
                        if not sweep_df.empty:
                            best_row = sweep_df.iloc[0]
                            ps_highlights.append({
                                "Stock": stock_id,
                                "Strategy": args.deep_dive_strategy,
                                "Best Return": best_row.get("Total Return", "N/A"),
                                "Best WinRate": best_row.get("Win Rate", "N/A")
                            })
                    except Exception as e:
                        ps_highlights.append({"Stock": stock_id, "Strategy": args.deep_dive_strategy, "Error": str(e)})
                        
                # Walk Forward
                if args.run_walk_forward:
                    try:
                        wf_df = run_walk_forward(stock_id, args.deep_dive_strategy, period=args.period, force_refresh=args.force_refresh)
                        if not wf_df.empty:
                            wf_highlights.append({
                                "Stock": stock_id,
                                "Strategy": args.deep_dive_strategy,
                                "Avg Return": wf_df["Total Return"].mean(),
                            })
                    except Exception as e:
                        wf_highlights.append({"Stock": stock_id, "Strategy": args.deep_dive_strategy, "Error": str(e)})
        
        import datetime
        report_data = build_daily_report_data(
            report_date=datetime.datetime.now().strftime("%Y-%m-%d"),
            stock_universe=list(stock_ids),
            screening_results=summary_df,
            watchlist_candidates=candidates_df,
            backtest_highlights=bt_highlights,
            parameter_sweep_highlights=ps_highlights,
            walk_forward_highlights=wf_highlights,
        )
        
        md_text = render_daily_report_markdown(report_data)
        
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        output_md = args.output_md
        if output_md == "":
            output_md = str(out_dir / "daily_report.md")
            
        if output_md:
            with open(output_md, "w", encoding="utf-8") as f:
                f.write(md_text)
            print(f"\nMarkdown report exported to {output_md}")
            
        print("\nProcess completed successfully.")
        
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()

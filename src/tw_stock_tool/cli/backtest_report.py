import argparse
from pathlib import Path
from typing import Any

from tw_stock_tool.analysis.analysis import analyze_stock
from tw_stock_tool.backtesting.backtest import run_backtest
from tw_stock_tool.backtesting.strategies import STRATEGIES
from tw_stock_tool.reports.backtest_report import (
    export_backtest_report_markdown,
    export_backtest_report_excel,
)
from tw_stock_tool.utils.config import DEFAULT_PERIOD


def _normalize_result(
    raw_result: dict[str, Any],
    stock: str,
    strategy: str,
    start_date: str,
    end_date: str,
    parameters: dict[str, Any]
) -> dict[str, Any]:
    """Ensure result dictionary has metadata for reporting."""
    result = raw_result.copy()
    result["Stock"] = stock
    result["Strategy"] = strategy
    result["Start Date"] = start_date
    result["End Date"] = end_date
    result["Parameters"] = parameters
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest Report Generator")
    parser.add_argument("--stock", required=True, help="Stock ID (e.g., 2330)")
    parser.add_argument("--strategy", required=True, help="Strategy name (e.g., ma_cross)")
    parser.add_argument("--period", default=DEFAULT_PERIOD, help="Data period")
    parser.add_argument("--initial-capital", type=float, default=100000.0, help="Initial capital")
    parser.add_argument("--output-md", nargs="?", const="", default=None, help="Export Markdown report")
    parser.add_argument("--output-excel", nargs="?", const="", default=None, help="Export Excel report")
    parser.add_argument("--output-dir", default="output", help="Default output directory")
    parser.add_argument("--force-refresh", action="store_true", help="Redownload data ignoring cache")
    
    # Strategy specific params (minimal support for Phase 3.1)
    parser.add_argument("--short-window", type=int, default=5, help="Short MA window")
    parser.add_argument("--long-window", type=int, default=20, help="Long MA window")
    
    return parser.parse_args(argv)


def main() -> None:
    try:
        args = _parse_args()
        
        strategy_name = args.strategy
        if strategy_name not in STRATEGIES:
            if f"{strategy_name}_strategy" in STRATEGIES:
                strategy_name = f"{strategy_name}_strategy"
            else:
                raise ValueError(f"Unknown strategy: {args.strategy}")
                
        strategy_func = STRATEGIES[strategy_name]
        
        # Prepare strategy parameters
        params = {}
        if strategy_name == "ma_cross_strategy":
            params = {
                "short_window": args.short_window,
                "long_window": args.long_window,
            }
            
        print(f"Fetching data for {args.stock} (period={args.period})...")
        analysis = analyze_stock(
            stock_id=args.stock,
            period=args.period,
            force_refresh=args.force_refresh,
        )
        
        print(f"Applying strategy {strategy_name}...")
        df_exec = strategy_func(analysis.indicator_df, **params)
        
        print(f"Running backtest with initial capital {args.initial_capital}...")
        raw_result = run_backtest(df_exec, initial_capital=args.initial_capital)
        
        start_date = df_exec.index[0].strftime('%Y-%m-%d') if not df_exec.empty else "N/A"
        end_date = df_exec.index[-1].strftime('%Y-%m-%d') if not df_exec.empty else "N/A"
        
        result = _normalize_result(
            raw_result=raw_result,
            stock=args.stock,
            strategy=args.strategy,
            start_date=start_date,
            end_date=end_date,
            parameters=params,
        )
        
        out_dir = Path(args.output_dir)
        
        if args.output_excel is not None:
            excel_output = args.output_excel or str(out_dir / "backtest_report.xlsx")
            excel_path = export_backtest_report_excel(result, excel_output)
            print(f"Excel report: {excel_path}")
            
        if args.output_md is not None:
            md_output = args.output_md or str(out_dir / "backtest_report.md")
            md_path = export_backtest_report_markdown(result, md_output)
            print(f"Markdown report: {md_path}")
            
        if args.output_excel is None and args.output_md is None:
            print("Backtest finished. Summary:")
            print(f"  Total Return: {result.get('Total Return %', 0)}%")
            print(f"  Win Rate: {result.get('Win Rate %', 0)}%")
            print(f"  Trades: {result.get('Trade Count', 0)}")
            
    except Exception as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

if __name__ == "__main__":
    main()

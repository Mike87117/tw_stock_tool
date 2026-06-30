import argparse
from pathlib import Path
import sys

from tw_stock_tool.backtesting.walk_forward import run_walk_forward
from tw_stock_tool.reports.walk_forward_report import (
    build_walk_forward_report_data,
    export_walk_forward_report_markdown,
    export_walk_forward_report_excel,
)
from tw_stock_tool.utils.config import DEFAULT_PERIOD, FEE_RATE, INITIAL_CAPITAL, TAX_RATE
from tw_stock_tool.cli.parsers import parse_int_tuple

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Walk Forward Report CLI")
    parser.add_argument("--stock", required=True, help="Stock ID (e.g., 2330)")
    parser.add_argument("--strategy", required=True, help="Strategy name (e.g., ma_cross, all)")
    parser.add_argument("--period", default=DEFAULT_PERIOD, help="Data period")
    parser.add_argument("--output-md", nargs="?", const="", default=None, help="Export Markdown report")
    parser.add_argument("--output-excel", nargs="?", const="", default=None, help="Export Excel report")
    parser.add_argument("--output-dir", default="output", help="Default output directory")
    parser.add_argument("--force-refresh", action="store_true", help="Redownload data ignoring cache")

    # Custom Parameter Ranges
    parser.add_argument("--ma-short-windows", type=parse_int_tuple, help="Comma-separated integers, e.g. 5,10")
    parser.add_argument("--ma-long-windows", type=parse_int_tuple, help="Comma-separated integers")
    parser.add_argument("--rsi-buy-below", type=parse_int_tuple, help="Comma-separated integers")
    parser.add_argument("--rsi-sell-above", type=parse_int_tuple, help="Comma-separated integers")
    parser.add_argument("--score-buy", type=parse_int_tuple, help="Comma-separated integers")
    parser.add_argument("--score-sell", type=parse_int_tuple, help="Comma-separated integers, can be negative")

    # Window parameters
    parser.add_argument("--train-days", type=int, default=504, help="Number of training days per window")
    parser.add_argument("--test-days", type=int, default=126, help="Number of test days per window")
    parser.add_argument("--step-days", type=int, default=None, help="Number of days to step forward per window")
    parser.add_argument("--sort-by", default="Train Sharpe Ratio", help="Metric to select best parameters")

    # Backtest engine parameters
    parser.add_argument("--initial-capital", type=float, default=INITIAL_CAPITAL)
    parser.add_argument("--fee-rate", type=float, default=FEE_RATE)
    parser.add_argument("--tax-rate", type=float, default=TAX_RATE)
    parser.add_argument("--position-size", type=float, default=1.0)
    parser.add_argument("--stop-loss-pct", type=float, default=None)
    parser.add_argument("--take-profit-pct", type=float, default=None)
    parser.add_argument("--max-hold-days", type=int, default=None)

    return parser.parse_args(argv)


def main() -> None:
    try:
        args = _parse_args()
        
        print(f"Running walk forward for {args.stock} (strategy={args.strategy}, period={args.period})...")
        wf_df = run_walk_forward(
            stock_id=args.stock,
            strategy=args.strategy,
            period=args.period,
            force_refresh=args.force_refresh,
            train_days=args.train_days,
            test_days=args.test_days,
            step_days=args.step_days,
            sort_by=args.sort_by,
            initial_capital=args.initial_capital,
            fee_rate=args.fee_rate,
            tax_rate=args.tax_rate,
            position_size=args.position_size,
            stop_loss_pct=args.stop_loss_pct,
            take_profit_pct=args.take_profit_pct,
            max_hold_days=args.max_hold_days,
            ma_short_windows=args.ma_short_windows,
            ma_long_windows=args.ma_long_windows,
            rsi_buy_below=args.rsi_buy_below,
            rsi_sell_above=args.rsi_sell_above,
            score_buy=args.score_buy,
            score_sell=args.score_sell,
        )
        
        strategy_params = {
            "ma_short_windows": args.ma_short_windows,
            "ma_long_windows": args.ma_long_windows,
            "rsi_buy_below": args.rsi_buy_below,
            "rsi_sell_above": args.rsi_sell_above,
            "score_buy": args.score_buy,
            "score_sell": args.score_sell,
        }
        
        backtest_params = {
            "initial_capital": args.initial_capital,
            "fee_rate": args.fee_rate,
            "tax_rate": args.tax_rate,
            "position_size": args.position_size,
            "stop_loss_pct": args.stop_loss_pct,
            "take_profit_pct": args.take_profit_pct,
            "max_hold_days": args.max_hold_days,
        }
        
        window_params = {
            "train_days": args.train_days,
            "test_days": args.test_days,
            "step_days": args.step_days,
            "sort_by": args.sort_by,
        }

        result_dict = {
            "Stock": args.stock,
            "Strategy": args.strategy,
            "Parameters": {
                "strategy": strategy_params,
                "backtest": backtest_params,
                "window": window_params,
            },
            "Results": wf_df,
        }
        
        out_dir = Path(args.output_dir)
        
        if args.output_excel is not None:
            excel_output = args.output_excel or str(out_dir / "walk_forward_report.xlsx")
            excel_path = export_walk_forward_report_excel(result_dict, excel_output)
            print(f"Excel report: {excel_path}")
            
        if args.output_md is not None:
            md_output = args.output_md or str(out_dir / "walk_forward_report.md")
            md_path = export_walk_forward_report_markdown(result_dict, md_output)
            print(f"Markdown report: {md_path}")
            
        if args.output_excel is None and args.output_md is None:
            print("Walk forward finished. Summary:")
            print(f"  Total Windows Evaluated: {len(wf_df)}")
            if not wf_df.empty:
                report_data = build_walk_forward_report_data(result_dict)
                best_window = report_data.get("Best Window")
                if best_window:
                    print(f"  Best Strategy: {best_window.get('Strategy', 'N/A')}")
                    print(f"  Best Parameters: {best_window.get('Parameters', 'N/A')}")
                    print(f"  Best Test Total Return: {best_window.get('Test Total Return %', 0)}%")
                    print(f"  Best Test Sharpe Ratio: {best_window.get('Test Sharpe Ratio', 'N/A')}")
            
    except Exception as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

if __name__ == "__main__":
    main()

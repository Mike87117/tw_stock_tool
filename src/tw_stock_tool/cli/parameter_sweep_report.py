import argparse
import tempfile
from pathlib import Path

from tw_stock_tool.backtesting.parameter_sweep import run_parameter_sweep
from tw_stock_tool.reports.parameter_sweep_report import (
    build_parameter_sweep_report_data,
    export_parameter_sweep_report_markdown,
    export_parameter_sweep_report_excel,
)
from tw_stock_tool.utils.config import DEFAULT_PERIOD, INITIAL_CAPITAL, FEE_RATE, TAX_RATE


from tw_stock_tool.cli.parsers import parse_int_tuple


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parameter Sweep Report CLI")
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

    # Engine Parameters
    parser.add_argument("--initial-capital", type=float, default=INITIAL_CAPITAL, help="Initial capital (default from config)")
    parser.add_argument("--fee-rate", type=float, default=FEE_RATE, help="Fee rate (default from config)")
    parser.add_argument("--tax-rate", type=float, default=TAX_RATE, help="Tax rate (default from config)")
    parser.add_argument("--position-size", type=float, default=1.0, help="Position size (0 to 1.0, default 1.0)")
    parser.add_argument("--stop-loss-pct", type=float, default=None, help="Stop loss percentage (e.g., 0.05 for 5%%)")
    parser.add_argument("--take-profit-pct", type=float, default=None, help="Take profit percentage")
    parser.add_argument("--max-hold-days", type=int, default=None, help="Maximum holding days")

    return parser.parse_args(argv)


def _preflight_output_path(path: str | Path) -> None:
    """Validate that the given output path can be written to before starting expensive work."""
    p = Path(path)
    if p.exists():
        if p.is_dir():
            raise ValueError(f"Output path is a directory, not a file: {path}")
        try:
            with open(p, "a", encoding="utf-8") as f:
                pass
        except Exception as exc:
            raise PermissionError(f"Cannot write to output path {path}: {exc}") from exc
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.NamedTemporaryFile(dir=p.parent, delete=True) as f:
                pass
        except Exception as exc:
            raise PermissionError(f"Cannot write to output path {path}: {exc}") from exc


def main() -> None:
    try:
        args = _parse_args()

        out_dir = Path(args.output_dir)
        excel_output = None
        md_output = None

        if args.output_excel is not None:
            excel_output = args.output_excel or str(out_dir / "parameter_sweep_report.xlsx")
            _preflight_output_path(excel_output)
            
        if args.output_md is not None:
            md_output = args.output_md or str(out_dir / "parameter_sweep_report.md")
            _preflight_output_path(md_output)

        print(f"Running parameter sweep for {args.stock} (strategy={args.strategy}, period={args.period})...")
        sweep_df = run_parameter_sweep(
            stock_id=args.stock,
            strategy=args.strategy,
            period=args.period,
            force_refresh=args.force_refresh,
            ma_short_windows=args.ma_short_windows,
            ma_long_windows=args.ma_long_windows,
            rsi_buy_below=args.rsi_buy_below,
            rsi_sell_above=args.rsi_sell_above,
            score_buy=args.score_buy,
            score_sell=args.score_sell,
            initial_capital=args.initial_capital,
            fee_rate=args.fee_rate,
            tax_rate=args.tax_rate,
            stop_loss_pct=args.stop_loss_pct,
            take_profit_pct=args.take_profit_pct,
            max_hold_days=args.max_hold_days,
            position_size=args.position_size,
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

        result_dict = {
            "Stock": args.stock,
            "Strategy": args.strategy,
            "Parameters": {
                "strategy": strategy_params,
                "backtest": backtest_params,
            },
            "Results": sweep_df,
        }
        
        if excel_output is not None:
            excel_path = export_parameter_sweep_report_excel(result_dict, excel_output)
            print(f"Excel report: {excel_path}")
            
        if md_output is not None:
            md_path = export_parameter_sweep_report_markdown(result_dict, md_output)
            print(f"Markdown report: {md_path}")
            
        if args.output_excel is None and args.output_md is None:
            print("Parameter sweep finished. Summary:")
            print(f"  Total Rows: {len(sweep_df)}")
            if not sweep_df.empty:
                report_data = build_parameter_sweep_report_data(result_dict)
                best_row = report_data.get("Best Row")
                if best_row:
                    print(f"  Top In-Sample Strategy: {best_row.get('Strategy', 'N/A')}")
                    print(f"  Top In-Sample Parameters: {best_row.get('Parameters', 'N/A')}")
                    print(f"  Top In-Sample Total Return: {best_row.get('Total Return %', 0)}%")
                    print(f"  Top In-Sample Sharpe Ratio: {best_row.get('Sharpe Ratio', 'N/A')}")
            
    except Exception as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

if __name__ == "__main__":
    main()

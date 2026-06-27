import argparse
from pathlib import Path

from tw_stock_tool.backtesting.parameter_sweep import run_parameter_sweep
from tw_stock_tool.reports.parameter_sweep_report import (
    export_parameter_sweep_report_markdown,
    export_parameter_sweep_report_excel,
)
from tw_stock_tool.utils.config import DEFAULT_PERIOD


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parameter Sweep Report CLI")
    parser.add_argument("--stock", required=True, help="Stock ID (e.g., 2330)")
    parser.add_argument("--strategy", required=True, help="Strategy name (e.g., ma_cross, all)")
    parser.add_argument("--period", default=DEFAULT_PERIOD, help="Data period")
    parser.add_argument("--output-md", nargs="?", const="", default=None, help="Export Markdown report")
    parser.add_argument("--output-excel", nargs="?", const="", default=None, help="Export Excel report")
    parser.add_argument("--output-dir", default="output", help="Default output directory")
    parser.add_argument("--force-refresh", action="store_true", help="Redownload data ignoring cache")
    return parser.parse_args(argv)


def main() -> None:
    try:
        args = _parse_args()
        
        print(f"Running parameter sweep for {args.stock} (strategy={args.strategy}, period={args.period})...")
        sweep_df = run_parameter_sweep(
            stock_id=args.stock,
            strategy=args.strategy,
            period=args.period,
            force_refresh=args.force_refresh,
        )
        
        result_dict = {
            "Stock": args.stock,
            "Strategy": args.strategy,
            "Results": sweep_df,
        }
        
        out_dir = Path(args.output_dir)
        
        if args.output_excel is not None:
            excel_output = args.output_excel or str(out_dir / "parameter_sweep_report.xlsx")
            excel_path = export_parameter_sweep_report_excel(result_dict, excel_output)
            print(f"Excel report: {excel_path}")
            
        if args.output_md is not None:
            md_output = args.output_md or str(out_dir / "parameter_sweep_report.md")
            md_path = export_parameter_sweep_report_markdown(result_dict, md_output)
            print(f"Markdown report: {md_path}")
            
        if args.output_excel is None and args.output_md is None:
            print("Parameter sweep finished. Summary:")
            print(f"  Total Rows: {len(sweep_df)}")
            if not sweep_df.empty:
                # Find the best row simply by taking the first row (the sweep engine already sorts)
                best_row = sweep_df.iloc[0]
                print(f"  Best Strategy: {best_row.get('Strategy', 'N/A')}")
                print(f"  Best Parameters: {best_row.get('Parameters', 'N/A')}")
                print(f"  Best Total Return: {best_row.get('Total Return %', 0)}%")
                print(f"  Best Sharpe Ratio: {best_row.get('Sharpe Ratio', 'N/A')}")
            
    except Exception as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

if __name__ == "__main__":
    main()

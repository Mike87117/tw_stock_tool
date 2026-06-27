import argparse
from pathlib import Path
import sys

from tw_stock_tool.backtesting.walk_forward import run_walk_forward
from tw_stock_tool.reports.walk_forward_report import (
    build_walk_forward_report_data,
    export_walk_forward_report_markdown,
    export_walk_forward_report_excel,
)
from tw_stock_tool.utils.config import DEFAULT_PERIOD


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Walk Forward Report CLI")
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
        
        print(f"Running walk forward for {args.stock} (strategy={args.strategy}, period={args.period})...")
        wf_df = run_walk_forward(
            stock_id=args.stock,
            strategy=args.strategy,
            period=args.period,
            force_refresh=args.force_refresh,
        )
        
        result_dict = {
            "Stock": args.stock,
            "Strategy": args.strategy,
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
        sys.exit(1)

if __name__ == "__main__":
    main()

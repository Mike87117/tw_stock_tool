"""
Offline CLI for multi-symbol simulated portfolio trading JSON artifacts.
"""

import argparse
import sys

from tw_stock_tool.paper_trading.models import PaperTradingModelError
from tw_stock_tool.paper_trading.portfolio_export_files import (
    export_simulated_portfolio_trading_csv_files,
    export_simulated_portfolio_trading_markdown_file,
)
from tw_stock_tool.paper_trading.portfolio_report_data import (
    build_simulated_portfolio_trading_summary,
)
from tw_stock_tool.paper_trading.portfolio_serialization_files import (
    load_simulated_portfolio_trading_result_json_file,
)


def build_parser() -> argparse.ArgumentParser:
    description = (
        "Operate on an existing offline simulated portfolio trading JSON artifact.\n"
        "Does not fetch market data, run analysis, execute strategies or backtests,\n"
        "execute simulated trading, run the portfolio coordinator, connect to brokers,\n"
        "place orders, produce live signals, recommend stocks, or provide investment advice."
    )
    parser = argparse.ArgumentParser(
        prog="twstock simulated-portfolio-artifact",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # validate
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a simulated portfolio trading JSON artifact",
    )
    validate_parser.add_argument("input_json", type=str, help="Path to input JSON artifact")

    # inspect
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect summary metrics of a simulated portfolio trading JSON artifact",
    )
    inspect_parser.add_argument("input_json", type=str, help="Path to input JSON artifact")

    # export-markdown
    markdown_parser = subparsers.add_parser(
        "export-markdown",
        help="Export Markdown report from a simulated portfolio trading JSON artifact",
    )
    markdown_parser.add_argument("input_json", type=str, help="Path to input JSON artifact")
    markdown_parser.add_argument(
        "--output-markdown",
        type=str,
        required=True,
        help="Path to output Markdown file",
    )
    markdown_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output file",
    )

    # export-csv
    csv_parser = subparsers.add_parser(
        "export-csv",
        help="Export 7-file CSV bundle from a simulated portfolio trading JSON artifact",
    )
    csv_parser.add_argument("input_json", type=str, help="Path to input JSON artifact")
    csv_parser.add_argument(
        "--output-csv-dir",
        type=str,
        required=True,
        help="Directory to write CSV bundle files",
    )
    csv_parser.add_argument(
        "--basename",
        type=str,
        default="simulated_portfolio_trading",
        help="Basename for CSV bundle files",
    )
    csv_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files",
    )

    return parser


def main(argv: list[str] | None = None) -> int | None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        result = load_simulated_portfolio_trading_result_json_file(args.input_json)
    except FileExistsError as exc:
        print(f"error: {exc}. Use --overwrite to replace existing files.", file=sys.stderr)
        return 1
    except (FileNotFoundError, IsADirectoryError, PermissionError, UnicodeDecodeError, PaperTradingModelError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    try:
        if args.subcommand == "validate":
            print(f"Simulated Portfolio Trading artifact is valid: {args.input_json}")
            return None

        if args.subcommand == "inspect":
            summary = build_simulated_portfolio_trading_summary(result)
            divider = "-" * 44
            lines = [
                "Simulated Portfolio Trading Artifact Summary",
                divider,
                f"Initial Cash: {summary['initial_cash']}",
                f"Final Cash: {summary['final_cash']}",
                f"Total Market Value: {summary['total_market_value']}",
                f"Total Equity: {summary['total_equity']}",
                f"Realized PnL: {summary['realized_pnl']}",
                f"Unrealized PnL: {summary['unrealized_pnl']}",
                f"Total Return: {summary['total_return']}",
                f"Total Return Pct: {summary['total_return_pct']}",
                f"Open Position Count: {summary['open_position_count']}",
                f"Pending Order Count: {summary['pending_order_count']}",
                f"Order Count: {summary['order_count']}",
                f"Fill Count: {summary['fill_count']}",
                f"Rejection Count: {summary['rejection_count']}",
                f"Audit Record Count: {summary['audit_record_count']}",
            ]
            print("\n".join(lines))
            return None

        if args.subcommand == "export-markdown":
            out_path = export_simulated_portfolio_trading_markdown_file(
                result,
                args.output_markdown,
                overwrite=args.overwrite,
            )
            print(f"Simulated Portfolio Trading Markdown written: {out_path}")
            return None

        if args.subcommand == "export-csv":
            paths_dict = export_simulated_portfolio_trading_csv_files(
                result,
                args.output_csv_dir,
                basename=args.basename,
                overwrite=args.overwrite,
            )
            print("Simulated Portfolio Trading CSV files written:")
            for key, path in paths_dict.items():
                print(f"{key}: {path}")
            return None

    except FileExistsError as exc:
        print(f"error: {exc}. Use --overwrite to replace existing files.", file=sys.stderr)
        return 1
    except (FileNotFoundError, IsADirectoryError, PermissionError, UnicodeDecodeError, PaperTradingModelError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return None


if __name__ == "__main__":
    raise SystemExit(main())

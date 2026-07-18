import argparse
import sys
from pathlib import Path

from tw_stock_tool.paper_trading.models import PaperTradingModelError
from tw_stock_tool.paper_trading.serialization_files import (
    load_simulated_paper_trading_result_json_file,
)
from tw_stock_tool.paper_trading.export_files import (
    export_simulated_paper_trading_markdown_file,
    export_simulated_paper_trading_csv_files,
)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export reports from an existing research-only simulated paper trading JSON artifact.\n"
                    "Does not fetch market data, run strategies, connect to brokers, or place orders."
    )
    parser.add_argument(
        "input_json",
        type=str,
        help="Path to the input JSON artifact file."
    )
    parser.add_argument(
        "--output-markdown",
        type=str,
        help="Path to the output Markdown file."
    )
    parser.add_argument(
        "--output-csv-dir",
        type=str,
        help="Path to the output directory for CSV files."
    )
    parser.add_argument(
        "--basename",
        type=str,
        default="simulated_paper_trading",
        help="Basename for CSV files (default: simulated_paper_trading)."
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files."
    )
    return parser


def main(argv: list[str] | None = None) -> int | None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.output_markdown and not args.output_csv_dir:
        parser.error("at least one of --output-markdown or --output-csv-dir is required")

    try:
        result = load_simulated_paper_trading_result_json_file(args.input_json)
    except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except PaperTradingModelError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    try:
        if args.output_markdown:
            export_simulated_paper_trading_markdown_file(
                result, args.output_markdown, overwrite=args.overwrite
            )
        
        if args.output_csv_dir:
            export_simulated_paper_trading_csv_files(
                result,
                args.output_csv_dir,
                basename=args.basename,
                overwrite=args.overwrite,
            )
    except FileExistsError as e:
        print(
            f"error: {e}. Use --overwrite to replace existing files.",
            file=sys.stderr,
        )
        return 1
    except (FileNotFoundError, IsADirectoryError, PermissionError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

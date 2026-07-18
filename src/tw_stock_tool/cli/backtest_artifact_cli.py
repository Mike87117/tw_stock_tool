import argparse
import sys

from tw_stock_tool.backtesting.serialization import BacktestResultSerializationError
from tw_stock_tool.backtesting.serialization_files import load_backtest_result_json_file
from tw_stock_tool.paper_trading import convert_backtest_result_to_simulated_paper_trading_result
from tw_stock_tool.paper_trading.models import PaperTradingModelError
from tw_stock_tool.paper_trading.serialization_files import (
    export_simulated_paper_trading_result_json_file,
    load_simulated_paper_trading_result_json_file,
)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backtest_artifact_cli.py",
        description=(
            "Validate, inspect, or convert an existing research-only BacktestResult JSON artifact. "
            "Does not fetch market data, run strategies, execute backtests, connect to brokers, "
            "place orders, produce live signals, or provide investment advice. "
            "Conversion is a retrospective offline mapping to a simulated paper trading JSON artifact."
        ),
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate an existing research-only BacktestResult JSON artifact.",
    )
    validate_parser.add_argument(
        "input_json",
        type=str,
        help="Path to the BacktestResult JSON artifact to validate.",
    )
    
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect an existing research-only BacktestResult JSON artifact.",
    )
    inspect_parser.add_argument(
        "input_json",
        type=str,
        help="Path to the BacktestResult JSON artifact to inspect.",
    )
    
    convert_parser = subparsers.add_parser(
        "convert-to-simulated-paper-trading",
        help="Convert an existing research-only BacktestResult JSON artifact to a simulated paper trading JSON artifact.",
        description=(
            "Convert an existing research-only BacktestResult JSON artifact to a simulated paper trading JSON artifact. "
            "Does not fetch market data, run strategies, execute backtests, connect to brokers, "
            "place orders, produce live signals, or provide investment advice."
        ),
    )
    convert_parser.add_argument(
        "input_json",
        type=str,
        help="Path to the existing BacktestResult JSON artifact.",
    )
    convert_parser.add_argument(
        "--output-json",
        type=str,
        required=True,
        help="Path to write the output simulated paper trading JSON artifact.",
    )
    convert_parser.add_argument(
        "--overwrite",
        action="store_true",
        default=False,
        help="Overwrite the output file if it exists.",
    )
    
    return parser


def main(argv: list[str] | None = None) -> int | None:
    parser = build_parser()
    args = parser.parse_args(argv)
    
    try:
        if args.command == "validate":
            result = load_backtest_result_json_file(args.input_json)
            print(f"BacktestResult artifact is valid: {args.input_json}")
            
        elif args.command == "inspect":
            result = load_backtest_result_json_file(args.input_json)
            print("BacktestResult Artifact Summary")
            print("-" * 30)
            print(f"Stock:           {result.stock}")
            print(f"Strategy:        {result.strategy}")
            print(f"Start Date:      {result.start_date}")
            print(f"End Date:        {result.end_date}")
            print(f"Initial Capital: {result.initial_capital:.2f}")
            print(f"Final Capital:   {result.final_capital:.2f}")
            print(f"Total Return:    {result.total_return_pct:.2f}%")
            print(f"Max Drawdown:    {result.max_drawdown_pct:.2f}%")
            print(f"Trade Count:     {result.trade_count}")

        elif args.command == "convert-to-simulated-paper-trading":
            result = load_backtest_result_json_file(args.input_json)
            paper_trading_result = convert_backtest_result_to_simulated_paper_trading_result(result)
            written_path = export_simulated_paper_trading_result_json_file(paper_trading_result, args.output_json, overwrite=args.overwrite)
            load_simulated_paper_trading_result_json_file(written_path)
            print(f"Simulated paper trading artifact written: {written_path}")

            
    except FileExistsError as e:
        print(f"error: {e}. Use --overwrite to replace existing files.", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except IsADirectoryError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except PermissionError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except BacktestResultSerializationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except PaperTradingModelError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import sys
from pathlib import Path

from tw_stock_tool.backtesting.serialization import BacktestResultSerializationError
from tw_stock_tool.backtesting.serialization_files import load_backtest_result_json_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backtest_artifact_cli.py",
        description=(
            "Validate or inspect an existing research-only BacktestResult JSON artifact. "
            "Does not fetch market data, run strategies, execute backtests, connect to brokers, "
            "place orders, produce live signals, or provide investment advice."
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
    
    return parser


def main(argv: list[str] | None = None) -> None:
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
            print(f"Total Return:    {result.total_return_pct * 100:.2f}%")
            print(f"Max Drawdown:    {result.max_drawdown_pct * 100:.2f}%")
            print(f"Trade Count:     {result.trade_count}")
            
    except FileNotFoundError as e:
        parser.exit(1, f"error: {e}\n")
    except IsADirectoryError as e:
        parser.exit(1, f"error: {e}\n")
    except PermissionError as e:
        parser.exit(1, f"error: {e}\n")
    except BacktestResultSerializationError as e:
        parser.exit(1, f"error: {e}\n")


if __name__ == "__main__":
    main()

import argparse
from pathlib import Path
from typing import Any

from tw_stock_tool.application.research_run import BacktestRunRequest, run_backtest
from tw_stock_tool.application.workspace_run import run_backtest_workspace
from tw_stock_tool.application.workspace_summary import workspace_run_paths
from tw_stock_tool.application.symbol_resolution import resolve_symbol_request
from tw_stock_tool.cli._research_run_cli import artifact_path
# analyze_stock, legacy_run_backtest and the two exporters are the
# pre-application-service legacy path. They are no longer called here, but
# test_backtest_report_cli patches them on this module and asserts they stay
# uncalled, which is what proves the CLI delegates to the application service.
from tw_stock_tool.analysis.analysis import analyze_stock  # noqa: F401
from tw_stock_tool.backtesting.backtest import run_backtest as legacy_run_backtest  # noqa: F401
from tw_stock_tool.backtesting.strategies import STRATEGIES
from tw_stock_tool.reports.backtest_report import (  # noqa: F401  legacy-delegation seam, see comment above
    export_backtest_report_markdown,
    export_backtest_report_excel,
)
from tw_stock_tool.cli._report_cli_arguments import (
    add_force_refresh_argument,
    add_report_output_arguments,
    add_stock_strategy_period_arguments,
    build_backtest_parameters,
)


def _normalize_result(
    raw_result: dict[str, Any],
    stock: str,
    strategy: str,
    start_date: str,
    end_date: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Legacy result normalizer retained for compatibility imports."""
    result = raw_result.copy()
    result["Stock"] = stock
    result["Strategy"] = strategy
    result["Start Date"] = start_date
    result["End Date"] = end_date
    result["Parameters"] = parameters
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest Report Generator",
        epilog="Backtest fills use next-bar Open as a research assumption."
    )
    add_stock_strategy_period_arguments(parser, strategy_help="Strategy name (e.g., ma_cross)")
    parser.add_argument("--initial-capital", type=float, default=100000.0, help="Initial capital")
    add_report_output_arguments(parser)
    parser.add_argument("--workspace", help="建立 append-only managed Research Run 的 Workspace 路徑")
    add_force_refresh_argument(parser)
    parser.add_argument("--short-window", type=int, default=5, help="Short MA window")
    parser.add_argument("--long-window", type=int, default=20, help="Long MA window")
    parser.add_argument("--rsi-buy-below", type=float, default=30.0, help="RSI threshold (buy below)")
    parser.add_argument("--rsi-sell-above", type=float, default=70.0, help="RSI threshold (sell above)")
    parser.add_argument("--score-buy", type=float, default=None, help="Score threshold (buy)")
    parser.add_argument("--score-sell", type=float, default=None, help="Score threshold (sell)")
    parser.add_argument("--fee-rate", type=float, default=0.001425, help="Backtest fee rate assumption")
    parser.add_argument("--tax-rate", type=float, default=0.003, help="Backtest tax rate assumption")
    parser.add_argument("--position-size", type=float, default=1.0, help="Backtest position size")
    parser.add_argument("--stop-loss-pct", type=float, default=None, help="Stop-loss threshold percentage")
    parser.add_argument("--take-profit-pct", type=float, default=None, help="Take-profit threshold percentage")
    parser.add_argument("--max-hold-days", type=int, default=None, help="Max holding days")
    parser.add_argument("--manifest-path", default=None)
    return parser.parse_args(argv)


def _build_strategy_params(args: argparse.Namespace, strategy_name: str) -> dict[str, Any]:
    if strategy_name == "ma_cross_strategy":
        return {
            "short_window": args.short_window,
            "long_window": args.long_window,
        }
    elif strategy_name == "rsi_strategy":
        return {
            "buy_below": args.rsi_buy_below,
            "sell_above": args.rsi_sell_above,
        }
    elif strategy_name == "score_strategy":
        params = {}
        if args.score_buy is not None:
            params["buy_score"] = args.score_buy
        if args.score_sell is not None:
            params["sell_score"] = args.score_sell
        return params
    return {}


def _stage_callback(args: argparse.Namespace, strategy_name: str):
    def stage_callback(stage: str) -> None:
        if stage == "market_data":
            print(f"Fetching data for {args.stock} (period={args.period})...")
        elif stage == "strategy":
            print(f"Applying strategy {strategy_name}...")
        elif stage == "backtest":
            print(f"Running backtest with initial capital {args.initial_capital}...")
    return stage_callback


def main() -> int | None:
    try:
        args = _parse_args()

        strategy_name = args.strategy
        if strategy_name not in STRATEGIES:
            if f"{strategy_name}_strategy" in STRATEGIES:
                strategy_name = f"{strategy_name}_strategy"
            else:
                raise ValueError(f"Unknown strategy: {args.strategy}")

        resolved_symbol = resolve_symbol_request(
            args.stock,
            market_hint="all",
        )
        strategy_parameters = _build_strategy_params(args, strategy_name)
        markdown_path = (
            None
            if args.output_md is None
            else args.output_md or ("backtest_report.md" if getattr(args, "workspace", None) else str(Path(args.output_dir) / "backtest_report.md"))
        )
        excel_path = (
            None
            if args.output_excel is None
            else args.output_excel or ("backtest_report.xlsx" if getattr(args, "workspace", None) else str(Path(args.output_dir) / "backtest_report.xlsx"))
        )
        request = BacktestRunRequest(
            symbol=resolved_symbol,
            strategy=args.strategy,
            output_dir=args.output_dir,
            period=args.period,
            force_refresh=args.force_refresh,
            strategy_parameters=strategy_parameters,
            backtest_parameters=build_backtest_parameters(args),
            markdown_path=markdown_path,
            excel_path=excel_path,
            manifest_path=(
                getattr(args, "manifest_path", None)
                if isinstance(getattr(args, "manifest_path", None), (str, Path))
                else None
            ),
        )
        if getattr(args, "workspace", None):
            result = run_backtest_workspace(
                request,
                getattr(args, "workspace", None),
                stage_callback=_stage_callback(args, strategy_name),
            )
        else:
            result = run_backtest(
                request,
                stage_callback=_stage_callback(args, strategy_name),
            )

        if getattr(args, "workspace", None):
            run_directory, manifest_path = workspace_run_paths(getattr(args, "workspace", None), result.manifest)
            print(f"Run ID: {result.manifest.run_id}")
            print(f"Run status: {result.manifest.status}")
            print(f"Run directory: {run_directory}")
            print(f"Manifest path: {manifest_path}")
        if args.output_excel is not None:
            print(f"Excel report: {artifact_path(result, 'backtest_report_excel')}")
        if args.output_md is not None:
            print(f"Markdown report: {artifact_path(result, 'backtest_report_markdown')}")
        if args.output_excel is None and args.output_md is None:
            summary = result.domain_result
            print("Backtest finished. Summary:")
            print(f"  Total Return: {summary.get('Total Return %', 0)}%")
            print(f"  Win Rate: {summary.get('Win Rate %', 0)}%")
            print(f"  Trades: {summary.get('Trade Count', 0)}")
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

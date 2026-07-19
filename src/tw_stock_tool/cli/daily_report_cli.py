import argparse
import math
from pathlib import Path

from tw_stock_tool.utils.config import (
    DEFAULT_PERIOD,
    DEFAULT_INTERVAL,
    DEFAULT_AUTO_ADJUST,
)
from tw_stock_tool.reports.daily_report import (
    DEFAULT_SIGNALS,
    DEFAULT_MIN_SCORE,
    DEFAULT_TOP,
    run_daily_report,
    build_daily_report_data,
    render_daily_report_markdown,
    collect_stock_ids,
    build_data_limitations_from_ranking,
    run_candidate_backtest_validation,
)

def _validated_float(
    value: str,
    *,
    name: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"{name} must be a finite numeric value.") from exc
    if not math.isfinite(number):
        raise argparse.ArgumentTypeError(f"{name} must be a finite numeric value.")
    if minimum is not None and number < minimum:
        raise argparse.ArgumentTypeError(f"{name} must be at least {minimum}.")
    if maximum is not None and number > maximum:
        raise argparse.ArgumentTypeError(f"{name} must be at most {maximum}.")
    return number


def _nonnegative_int(value: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("validate_top must be a non-negative integer.") from exc
    if number < 0:
        raise argparse.ArgumentTypeError("validate_top must be at least 0.")
    return number


def _positive_float(value: str) -> float:
    number = _validated_float(value, name="initial_capital")
    if number <= 0:
        raise argparse.ArgumentTypeError("initial_capital must be greater than 0.")
    return number


def _nonnegative_float(name: str):
    return lambda value: _validated_float(value, name=name, minimum=0.0)


def _position_size(value: str) -> float:
    number = _validated_float(value, name="position_size", minimum=0.0, maximum=1.0)
    if number <= 0:
        raise argparse.ArgumentTypeError("position_size must be greater than 0.")
    return number

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily Report CLI")
    # Selection
    parser.add_argument("--stocks", nargs="*", help="Stock id list")
    parser.add_argument("--file", help="Load stock ids from txt file")
    parser.add_argument("--auto-stock-list", action="store_true")
    parser.add_argument("--stock-market", choices=("all", "twse", "tpex"), default="all")
    parser.add_argument("--stock-list-output", default="stocks.txt")
    parser.add_argument("--allow-partial-stock-list", action="store_true")
    parser.add_argument("--stock-limit", type=int)
    parser.add_argument("--stock-sample", type=int)
    parser.add_argument("--random-state", type=int, default=42)
    
    # Scanning
    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--interval", default=DEFAULT_INTERVAL)
    parser.add_argument("--signals", nargs="+", default=list(DEFAULT_SIGNALS))
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--auto-adjust", action=argparse.BooleanOptionalAction, default=DEFAULT_AUTO_ADJUST)
    parser.add_argument("--validate-top", type=_nonnegative_int, default=0)
    parser.add_argument("--validation-strategy", choices=("ma_cross", "macd", "rsi", "score"), default="ma_cross")
    parser.add_argument("--validation-initial-capital", type=_positive_float, default=100000)
    parser.add_argument("--validation-fee-rate", type=_nonnegative_float("validation_fee_rate"), default=0.001425)
    parser.add_argument("--validation-tax-rate", type=_nonnegative_float("validation_tax_rate"), default=0.003)
    parser.add_argument("--validation-position-size", type=_position_size, default=1.0)
    
    # Output
    parser.add_argument("--output-md", nargs="?", const="", default=None)
    parser.add_argument("--output-excel", nargs="?", const="", default=None)
    parser.add_argument("--output-dir", default="output")
    return parser.parse_args(argv)

def main() -> int | None:
    try:
        args = _parse_args()
        validate_top = getattr(args, "validate_top", 0)
        validation_strategy = getattr(args, "validation_strategy", "ma_cross")
        validation_initial_capital = getattr(args, "validation_initial_capital", 100000)
        validation_fee_rate = getattr(args, "validation_fee_rate", 0.001425)
        validation_tax_rate = getattr(args, "validation_tax_rate", 0.003)
        validation_position_size = getattr(args, "validation_position_size", 1.0)
        
        stock_ids = collect_stock_ids(
            args.stocks,
            args.file,
            auto_stock_list=args.auto_stock_list,
            stock_market=args.stock_market,
            stock_list_output=args.stock_list_output,
            allow_partial_stock_list=args.allow_partial_stock_list,
            stock_limit=args.stock_limit,
            stock_sample=args.stock_sample,
            random_state=args.random_state,
        )
        
        if not stock_ids:
            print("Error: No stocks provided.")
            return 1
            
        print(f"Scanning {len(stock_ids)} stocks...")
        summary_df, candidates_df, ranking_df, _ = run_daily_report(
            stock_ids=stock_ids,
            period=args.period,
            interval=args.interval,
            signals=args.signals,
            min_score=args.min_score,
            top=args.top,
            force_refresh=args.force_refresh,
            auto_adjust=args.auto_adjust,
            output=args.output_excel,
            progress=True,
        )
        
        import datetime
        data_limitations = build_data_limitations_from_ranking(ranking_df)
        backtest_highlights = []
        risk_notes = []
        if validate_top > 0:
            print(
                f"Validating top {validate_top} candidates with {validation_strategy}..."
            )
            backtest_highlights, validation_limitations = run_candidate_backtest_validation(
                candidates_df,
                validate_top=validate_top,
                strategy=validation_strategy,
                period=args.period,
                interval=args.interval,
                auto_adjust=args.auto_adjust,
                force_refresh=args.force_refresh,
                initial_capital=validation_initial_capital,
                fee_rate=validation_fee_rate,
                tax_rate=validation_tax_rate,
                position_size=validation_position_size,
            )
            data_limitations.extend(validation_limitations)
            successes = int((backtest_highlights["Status"] == "OK").sum())
            failures = len(backtest_highlights) - successes
            print(
                f"Validation completed: selected {len(backtest_highlights)}, "
                f"success {successes}, failed {failures}."
            )
            risk_notes.append(
                "Candidate backtests use historical data and next-bar Open execution assumptions; "
                "historical results do not predict future performance."
            )
        report_data = build_daily_report_data(
            report_date=datetime.datetime.now().strftime("%Y-%m-%d"),
            stock_universe=list(stock_ids),
            screening_results=summary_df,
            watchlist_candidates=candidates_df,
            backtest_highlights=backtest_highlights,
            parameter_sweep_highlights=[],
            walk_forward_highlights=[],
            risk_notes=risk_notes,
            data_limitations=data_limitations,
        )
        
        md_text = render_daily_report_markdown(report_data)
        
        default_output = Path(args.output_dir) / "daily_report.md"
        
        if args.output_md in (None, ""):
            output_md = default_output
        else:
            output_md = Path(args.output_md)
            
        output_md.parent.mkdir(parents=True, exist_ok=True)

        with open(output_md, "w", encoding="utf-8") as f:
            f.write(md_text)
        print(f"\nMarkdown report exported to {output_md}")
        print("\nProcess completed successfully.")

    except Exception as exc:
        print(f"Error: {exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())

import argparse
import math
from pathlib import Path

from tw_stock_tool.backtesting.walk_forward import SORTABLE_COLUMNS
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
    run_candidate_walk_forward_validation,
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


def _positive_int(name: str):
    def parse(value: str) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise argparse.ArgumentTypeError(f"{name} must be an integer.") from exc
        if number <= 0:
            raise argparse.ArgumentTypeError(f"{name} must be greater than 0.")
        return number
    return parse


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
    parser.add_argument("--walk-forward-top", type=_nonnegative_int, default=0)
    parser.add_argument("--walk-forward-train-days", type=_positive_int("walk_forward_train_days"), default=126)
    parser.add_argument("--walk-forward-test-days", type=_positive_int("walk_forward_test_days"), default=63)
    parser.add_argument("--walk-forward-step-days", type=_positive_int("walk_forward_step_days"))
    parser.add_argument(
        "--walk-forward-sort-by",
        choices=sorted(SORTABLE_COLUMNS),
        default="Train Sharpe Ratio",
    )

    # Output
    parser.add_argument("--output-md", nargs="?", const="", default=None)
    parser.add_argument("--output-excel", nargs="?", const="", default=None)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args(argv)
    if args.walk_forward_top > 0:
        if args.validate_top <= 0:
            parser.error("--walk-forward-top requires --validate-top greater than 0.")
        if args.walk_forward_top > args.validate_top:
            parser.error("--walk-forward-top cannot exceed --validate-top.")
        if args.validation_strategy == "macd":
            parser.error("MACD is supported for backtest-only validation, not walk-forward validation.")
    return args

def main() -> int | None:
    try:
        args = _parse_args()
        validate_top = getattr(args, "validate_top", 0)
        validation_strategy = getattr(args, "validation_strategy", "ma_cross")
        validation_initial_capital = getattr(args, "validation_initial_capital", 100000)
        validation_fee_rate = getattr(args, "validation_fee_rate", 0.001425)
        validation_tax_rate = getattr(args, "validation_tax_rate", 0.003)
        validation_position_size = getattr(args, "validation_position_size", 1.0)
        walk_forward_top = getattr(args, "walk_forward_top", 0)
        walk_forward_train_days = getattr(args, "walk_forward_train_days", 126)
        walk_forward_test_days = getattr(args, "walk_forward_test_days", 63)
        walk_forward_step_days = getattr(args, "walk_forward_step_days", None)
        walk_forward_sort_by = getattr(args, "walk_forward_sort_by", "Train Sharpe Ratio")

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
        walk_forward_highlights = []
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
        if walk_forward_top > 0:
            print(
                f"Validating walk-forward for up to {walk_forward_top} successful backtest candidate(s)..."
            )
            walk_forward_highlights, walk_forward_limitations = run_candidate_walk_forward_validation(
                backtest_highlights,
                walk_forward_top=walk_forward_top,
                strategy=validation_strategy,
                period=args.period,
                interval=args.interval,
                auto_adjust=args.auto_adjust,
                force_refresh=args.force_refresh,
                train_days=walk_forward_train_days,
                test_days=walk_forward_test_days,
                step_days=walk_forward_step_days,
                sort_by=walk_forward_sort_by,
                initial_capital=validation_initial_capital,
                fee_rate=validation_fee_rate,
                tax_rate=validation_tax_rate,
                position_size=validation_position_size,
            )
            data_limitations.extend(walk_forward_limitations)
            status_counts = walk_forward_highlights["Status"].value_counts() if not walk_forward_highlights.empty else {}
            print(
                "Walk-forward validation completed: "
                f"selected {len(walk_forward_highlights)}, "
                f"OK {status_counts.get('OK', 0)}, "
                f"PARTIAL {status_counts.get('PARTIAL', 0)}, "
                f"ERROR {status_counts.get('ERROR', 0)}."
            )
            risk_notes.append(
                "Walk-forward results are historical out-of-sample research estimates. "
                "Parameters are selected on training windows and evaluated on later test windows; "
                "results do not predict future performance. Window fields represent observations "
                "(rows) in the current engine."
            )
        report_data = build_daily_report_data(
            report_date=datetime.datetime.now().strftime("%Y-%m-%d"),
            stock_universe=list(stock_ids),
            screening_results=summary_df,
            watchlist_candidates=candidates_df,
            backtest_highlights=backtest_highlights,
            parameter_sweep_highlights=[],
            walk_forward_highlights=walk_forward_highlights,
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

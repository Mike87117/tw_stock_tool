import argparse
import math
from pathlib import Path

from tw_stock_tool.backtesting.parameter_sweep import SORTABLE_COLUMNS as PARAMETER_SWEEP_SORTABLE_COLUMNS
from tw_stock_tool.backtesting.walk_forward import SORTABLE_COLUMNS as WALK_FORWARD_SORTABLE_COLUMNS
from tw_stock_tool.reports.daily_pipeline import (
    DailyPipelineConfig,
    run_daily_research_pipeline,
    validate_daily_pipeline_config,
)
from tw_stock_tool.reports.daily_report import DEFAULT_MIN_SCORE, DEFAULT_SIGNALS, DEFAULT_TOP, collect_stock_ids
from tw_stock_tool.utils.config import DEFAULT_AUTO_ADJUST, DEFAULT_INTERVAL, DEFAULT_PERIOD, FEE_RATE, INITIAL_CAPITAL, TAX_RATE


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


def _nonnegative_int(value: str, name: str = "validate_top") -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"{name} must be a non-negative integer.") from exc
    if number < 0:
        raise argparse.ArgumentTypeError(f"{name} must be at least 0.")
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


def _pipeline_config_from_args(args: argparse.Namespace) -> DailyPipelineConfig:
    config = DailyPipelineConfig(
        period=getattr(args, "period", DEFAULT_PERIOD),
        interval=getattr(args, "interval", DEFAULT_INTERVAL),
        signals=tuple(getattr(args, "signals", DEFAULT_SIGNALS)),
        min_score=getattr(args, "min_score", DEFAULT_MIN_SCORE),
        top=getattr(args, "top", DEFAULT_TOP),
        force_refresh=getattr(args, "force_refresh", False),
        auto_adjust=getattr(args, "auto_adjust", DEFAULT_AUTO_ADJUST),
        validate_top=getattr(args, "validate_top", 0),
        validation_strategy=getattr(args, "validation_strategy", "ma_cross"),
        validation_initial_capital=getattr(args, "validation_initial_capital", INITIAL_CAPITAL),
        validation_fee_rate=getattr(args, "validation_fee_rate", FEE_RATE),
        validation_tax_rate=getattr(args, "validation_tax_rate", TAX_RATE),
        validation_position_size=getattr(args, "validation_position_size", 1.0),
        parameter_sweep_top=getattr(args, "parameter_sweep_top", 0),
        parameter_sweep_sort_by=getattr(args, "parameter_sweep_sort_by", "Sharpe Ratio"),
        walk_forward_top=getattr(args, "walk_forward_top", 0),
        walk_forward_train_days=getattr(args, "walk_forward_train_days", 126),
        walk_forward_test_days=getattr(args, "walk_forward_test_days", 63),
        walk_forward_step_days=getattr(args, "walk_forward_step_days", None),
        walk_forward_sort_by=getattr(args, "walk_forward_sort_by", "Train Sharpe Ratio"),
        output_excel=getattr(args, "output_excel", None),
        progress=True,
    )
    validate_daily_pipeline_config(config)
    return config

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily Report CLI")
    parser.add_argument("--stocks", nargs="*", help="Stock id list")
    parser.add_argument("--file", help="Load stock ids from txt file")
    parser.add_argument("--auto-stock-list", action="store_true")
    parser.add_argument("--stock-market", choices=("all", "twse", "tpex"), default="all")
    parser.add_argument("--stock-list-output", default="stocks.txt")
    parser.add_argument("--allow-partial-stock-list", action="store_true")
    parser.add_argument("--stock-limit", type=int)
    parser.add_argument("--stock-sample", type=int)
    parser.add_argument("--random-state", type=int, default=42)

    parser.add_argument("--period", default=DEFAULT_PERIOD)
    parser.add_argument("--interval", default=DEFAULT_INTERVAL)
    parser.add_argument("--signals", nargs="+", default=list(DEFAULT_SIGNALS))
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--auto-adjust", action=argparse.BooleanOptionalAction, default=DEFAULT_AUTO_ADJUST)
    parser.add_argument("--validate-top", type=_nonnegative_int, default=0)
    parser.add_argument("--validation-strategy", choices=("ma_cross", "macd", "rsi", "score"), default="ma_cross")
    parser.add_argument("--validation-initial-capital", type=_positive_float, default=INITIAL_CAPITAL)
    parser.add_argument("--validation-fee-rate", type=_nonnegative_float("validation_fee_rate"), default=FEE_RATE)
    parser.add_argument("--validation-tax-rate", type=_nonnegative_float("validation_tax_rate"), default=TAX_RATE)
    parser.add_argument("--validation-position-size", type=_position_size, default=1.0)
    parser.add_argument("--parameter-sweep-top", type=lambda value: _nonnegative_int(value, "parameter_sweep_top"), default=0)
    parser.add_argument("--parameter-sweep-sort-by", choices=sorted(PARAMETER_SWEEP_SORTABLE_COLUMNS), default="Sharpe Ratio")
    parser.add_argument("--walk-forward-top", type=_nonnegative_int, default=0)
    parser.add_argument("--walk-forward-train-days", type=_positive_int("walk_forward_train_days"), default=126)
    parser.add_argument("--walk-forward-test-days", type=_positive_int("walk_forward_test_days"), default=63)
    parser.add_argument("--walk-forward-step-days", type=_positive_int("walk_forward_step_days"))
    parser.add_argument("--walk-forward-sort-by", choices=sorted(WALK_FORWARD_SORTABLE_COLUMNS), default="Train Sharpe Ratio")

    parser.add_argument("--output-md", nargs="?", const="", default=None)
    parser.add_argument("--output-excel", nargs="?", const="", default=None)
    parser.add_argument("--output-dir", default="output")
    args = parser.parse_args(argv)
    try:
        _pipeline_config_from_args(args)
    except ValueError as exc:
        parser.error(str(exc))
    return args


def main() -> int | None:
    try:
        args = _parse_args()
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
        config = _pipeline_config_from_args(args)
        result = run_daily_research_pipeline(
            stock_ids,
            config,
            status_callback=print,
        )
        output_md = Path(args.output_dir) / "daily_report.md" if args.output_md in (None, "") else Path(args.output_md)
        output_md.parent.mkdir(parents=True, exist_ok=True)
        with open(output_md, "w", encoding="utf-8") as file:
            file.write(result.markdown)
        print(f"\nMarkdown report exported to {output_md}")
        print("\nProcess completed successfully.")
    except Exception as exc:
        print(f"Error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

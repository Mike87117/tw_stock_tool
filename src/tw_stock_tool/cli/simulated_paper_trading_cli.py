import argparse
import math
import pandas as pd

from tw_stock_tool.analysis.analysis import analyze_stock
from tw_stock_tool.backtesting.strategies import STRATEGIES
from tw_stock_tool.paper_trading.engine import run_simulated_paper_trading_result
from tw_stock_tool.paper_trading.results import build_simulated_paper_trading_summary
from tw_stock_tool.utils.config import DEFAULT_PERIOD

from tw_stock_tool.risk.config import SimulatedPaperTradingRiskConfig
from tw_stock_tool.simulated_paper_trading_guard.config import (
    SimulatedPaperTradingGuardConfig,
)
from tw_stock_tool.simulated_paper_trading_guard.builder import (
    build_guard_decision_provider_from_config,
)
from tw_stock_tool.simulated_paper_trading_guard.providers import (
    DataFrameReferencePriceProvider,
)

def _extract_final_close(df: pd.DataFrame) -> float:
    if df.empty:
        raise ValueError("DataFrame is empty.")
    if "Close" not in df.columns:
        raise ValueError("DataFrame missing 'Close' column.")

    val = df["Close"].iloc[-1]

    if type(val) is bool or type(val).__name__ in ("bool", "bool_"):
        raise ValueError("Final Close must not be boolean.")

    try:
        fval = float(val)
    except (ValueError, TypeError):
        raise ValueError("Final Close must be numeric.")

    if math.isnan(fval) or math.isinf(fval):
        raise ValueError("Final Close must be finite.")

    if fval <= 0:
        raise ValueError("Final Close must be positive.")

    return fval

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run research-only simulated paper trading over historical data.\nDoes not connect to brokers, place real orders, or provide investment advice."
    )

    parser.add_argument("--stock", required=True, help="Stock symbol")
    parser.add_argument("--strategy", required=True, choices=["ma_cross", "macd", "rsi"], help="Strategy name")

    def check_initial_cash(val: str) -> float:
        if val.lower() in ("true", "false"):
            raise argparse.ArgumentTypeError("initial_cash must be numeric.")
        fval = float(val)
        if math.isnan(fval) or math.isinf(fval) or fval < 0:
            raise argparse.ArgumentTypeError("initial_cash must be a finite non-negative number.")
        return fval

    parser.add_argument("--initial-cash", required=True, type=check_initial_cash, help="Initial cash for simulation")

    def check_quantity(val: str) -> int:
        if "." in val:
            raise argparse.ArgumentTypeError("quantity_per_trade must be an integer.")
        ival = int(val)
        if ival <= 0:
            raise argparse.ArgumentTypeError("quantity_per_trade must be a positive integer.")
        return ival

    parser.add_argument("--quantity-per-trade", required=True, type=check_quantity, help="Quantity per trade")

    parser.add_argument("--period", default=DEFAULT_PERIOD, help="Data period")

    def check_rate(val: str) -> float:
        fval = float(val)
        if math.isnan(fval) or math.isinf(fval) or fval < 0:
            raise argparse.ArgumentTypeError("Rate must be a finite non-negative number.")
        return fval

    parser.add_argument("--fee-rate", type=check_rate, default=0.0, help="Fee rate")
    parser.add_argument("--tax-rate", type=check_rate, default=0.0, help="Tax rate")
    parser.add_argument("--slippage-per-share", type=check_rate, default=0.0, help="Slippage per share")
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh data")

    def check_notional(val: str) -> float:
        if val.lower() in ("true", "false"):
            raise argparse.ArgumentTypeError("Notional must be numeric.")
        try:
            fval = float(val)
        except ValueError:
            raise argparse.ArgumentTypeError("Notional must be numeric.")
        if math.isnan(fval) or math.isinf(fval) or fval <= 0:
            raise argparse.ArgumentTypeError("Notional must be a finite strictly positive number.")
        return fval

    parser.add_argument("--max-order-notional", type=check_notional, default=None, help="Maximum notional value per order")
    parser.add_argument("--max-position-notional", type=check_notional, default=None, help="Maximum total position notional value")

    def check_max_quantity(val: str) -> int:
        if val.lower() in ("true", "false"):
            raise argparse.ArgumentTypeError("Quantity must be a positive integer.")
        if "." in val:
            raise argparse.ArgumentTypeError("Quantity must be a strict integer.")
        try:
            ival = int(val)
        except ValueError:
            raise argparse.ArgumentTypeError("Quantity must be a positive integer.")
        if ival <= 0:
            raise argparse.ArgumentTypeError("Quantity must be a strictly positive integer.")
        return ival

    parser.add_argument("--max-position-quantity", type=check_max_quantity, default=None, help="Maximum total position quantity")

    return parser.parse_args(argv)

def _build_guard_decision_provider(
    args: argparse.Namespace,
    df_exec: pd.DataFrame,
):
    if (
        args.max_order_notional is None
        and args.max_position_quantity is None
        and args.max_position_notional is None
    ):
        return None

    risk_config = SimulatedPaperTradingRiskConfig(
        max_order_notional=args.max_order_notional,
        max_position_quantity=args.max_position_quantity,
        max_position_notional=args.max_position_notional,
    )

    guard_config = SimulatedPaperTradingGuardConfig(
        risk=risk_config,
    )

    reference_price_provider = DataFrameReferencePriceProvider(
        df_exec,
    )

    return build_guard_decision_provider_from_config(
        guard_config,
        reference_price_provider=reference_price_provider,
    )

def main(argv: list[str] | None = None) -> None:
    try:
        args = _parse_args(argv)

        if not args.stock.strip():
            raise ValueError("Stock symbol cannot be blank.")

        strategy_key = f"{args.strategy}_strategy"
        strategy_func = STRATEGIES[strategy_key]

        analysis = analyze_stock(
            stock_id=args.stock,
            period=args.period,
            force_refresh=args.force_refresh,
        )

        df_exec = strategy_func(analysis.indicator_df)

        if df_exec.empty:
            raise ValueError("Strategy returned empty dataframe.")
        if "Open" not in df_exec.columns or "Close" not in df_exec.columns:
            raise ValueError("Strategy output missing Open or Close.")
        if "entry_signal" not in df_exec.columns or "exit_signal" not in df_exec.columns:
            raise ValueError("Strategy output missing standard signals.")

        last_price = _extract_final_close(df_exec)

        guard_decision_provider = _build_guard_decision_provider(args, df_exec)

        result = run_simulated_paper_trading_result(
            df=df_exec,
            symbol=analysis.symbol,
            initial_cash=args.initial_cash,
            quantity_per_trade=args.quantity_per_trade,
            fee_rate=args.fee_rate,
            tax_rate=args.tax_rate,
            slippage_per_share=args.slippage_per_share,
            last_price=last_price,
            guard_decision_provider=guard_decision_provider,
        )

        summary = build_simulated_paper_trading_summary(result)

        print("Simulated paper trading finished. Summary:")
        print(f"  Symbol: {summary['symbol']}")
        print(f"  Initial Cash: {summary['initial_cash']}")
        print(f"  Final Cash: {summary['final_cash']}")
        print(f"  Final Position Quantity: {summary['final_position_quantity']}")
        print(f"  Realized PnL: {summary['realized_pnl']}")
        print(f"  Unrealized PnL: {summary['unrealized_pnl']}")
        print(f"  Total Equity: {summary['total_equity']}")
        print(f"  Total Return: {summary['total_return']}")

        pct = summary['total_return_pct']
        if pct is None:
            pct_str = "N/A"
        else:
            pct_str = f"{pct * 100:.2f}%"

        print(f"  Total Return %: {pct_str}")
        print(f"  Orders: {summary['order_count']}")
        print(f"  Fills: {summary['fill_count']}")

    except SystemExit:
        raise
    except Exception as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

if __name__ == "__main__":
    main()

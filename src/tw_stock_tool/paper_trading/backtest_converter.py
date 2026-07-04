import json
import math
import pandas as pd
from typing import Any

from tw_stock_tool.backtesting.results import BacktestResult
from tw_stock_tool.paper_trading.models import (
    SimulatedOrder,
    SimulatedFill,
    PaperTradingModelError,
)
from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult


import numbers

def _is_strictly_positive_int(val: Any) -> bool:
    if isinstance(val, bool):
        return False
    if not isinstance(val, numbers.Integral):
        return False
    return int(val) > 0


def _is_finite_number(val: Any) -> bool:
    if isinstance(val, bool):
        return False
    if not isinstance(val, (int, float)):
        return False
    return math.isfinite(val)


def _is_json_serializable(data: dict) -> bool:
    try:
        json.dumps(data)
        return True
    except (TypeError, ValueError):
        return False


def convert_backtest_result_to_simulated_paper_trading_result(
    backtest_result: BacktestResult,
    *,
    metadata: dict | None = None,
) -> SimulatedPaperTradingResult:
    """
    Offline data transformer that maps an already-computed historical BacktestResult
    into a SimulatedPaperTradingResult artifact.
    It does not run a strategy, fetch live or historical market data, generate new trading signals,
    connect to a broker, place orders, or provide investment advice.
    """
    if not isinstance(backtest_result, BacktestResult):
        raise PaperTradingModelError("Input must be a BacktestResult object.")

    if not backtest_result.stock or not backtest_result.stock.strip():
        raise PaperTradingModelError("stock must be present and non-blank.")

    if not _is_finite_number(backtest_result.initial_capital) or backtest_result.initial_capital < 0:
        raise PaperTradingModelError("initial_capital must be finite and non-negative.")

    if not _is_finite_number(backtest_result.final_capital) or backtest_result.final_capital < 0:
        raise PaperTradingModelError("final_capital must be finite and non-negative.")

    if not isinstance(backtest_result.trades, pd.DataFrame):
        raise PaperTradingModelError("trades must be a pandas DataFrame.")

    SYSTEM_METADATA = {
        "source": "backtest_result",
        "conversion": "backtest_to_simulated_paper_trading_result",
        "semantics": "retrospective_offline_mapping",
    }
    
    metadata_payload = dict(SYSTEM_METADATA)
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise PaperTradingModelError("metadata must be a dict.")
        metadata_payload["user_metadata"] = metadata

    if not _is_json_serializable(metadata_payload):
        raise PaperTradingModelError("metadata must be JSON serializable.")

    orders = []
    fills = []
    realized_pnl = 0.0

    df = backtest_result.trades
    if not df.empty:
        required_cols = [
            "Entry Date", "Exit Date", "Entry Price", "Exit Price",
            "Shares", "PnL"
        ]
        for col in required_cols:
            if col not in df.columns:
                raise PaperTradingModelError(f"Missing required trade column: {col}")

        for trade_number, (_, row) in enumerate(df.iterrows()):
            shares = row["Shares"]
            if not _is_strictly_positive_int(shares):
                raise PaperTradingModelError(f"Shares must be a strict positive integer, got: {shares}")
            qty = int(shares)

            entry_price = row["Entry Price"]
            exit_price = row["Exit Price"]
            if not _is_finite_number(entry_price) or entry_price <= 0:
                raise PaperTradingModelError(f"Entry Price must be finite and positive, got: {entry_price}")
            if not _is_finite_number(exit_price) or exit_price <= 0:
                raise PaperTradingModelError(f"Exit Price must be finite and positive, got: {exit_price}")

            pnl = row["PnL"]
            if not _is_finite_number(pnl):
                raise PaperTradingModelError(f"PnL must be finite, got: {pnl}")

            entry_date = str(row["Entry Date"])
            exit_date = str(row["Exit Date"])

            sell_metadata = dict(metadata_payload)
            if "Exit Reason" in df.columns:
                sell_metadata["Exit Reason"] = str(row["Exit Reason"])
            if "Type" in df.columns:
                sell_metadata["Type"] = str(row["Type"])

            # Generate stable deterministic order IDs based on trade index
            buy_order_id = f"backtest-{trade_number:06d}-buy"
            sell_order_id = f"backtest-{trade_number:06d}-sell"

            # BUY Order and Fill
            orders.append(
                SimulatedOrder(
                    order_id=buy_order_id,
                    symbol=backtest_result.stock,
                    side="BUY",
                    quantity=qty,
                    signal_time=entry_date,
                    created_at=entry_date,
                    strategy=backtest_result.strategy,
                    metadata=dict(metadata_payload),
                )
            )
            fills.append(
                SimulatedFill(
                    order_id=buy_order_id,
                    symbol=backtest_result.stock,
                    side="BUY",
                    quantity=qty,
                    price=float(entry_price),
                    filled_at=entry_date,
                    fee=0.0,
                    tax=0.0,
                    slippage=0.0,
                )
            )

            # SELL Order and Fill
            orders.append(
                SimulatedOrder(
                    order_id=sell_order_id,
                    symbol=backtest_result.stock,
                    side="SELL",
                    quantity=qty,
                    signal_time=exit_date,
                    created_at=exit_date,
                    strategy=backtest_result.strategy,
                    metadata=sell_metadata,
                )
            )
            fills.append(
                SimulatedFill(
                    order_id=sell_order_id,
                    symbol=backtest_result.stock,
                    side="SELL",
                    quantity=qty,
                    price=float(exit_price),
                    filled_at=exit_date,
                    fee=0.0,
                    tax=0.0,
                    slippage=0.0,
                )
            )

            realized_pnl += float(pnl)

    return SimulatedPaperTradingResult(
        symbol=backtest_result.stock,
        initial_cash=float(backtest_result.initial_capital),
        final_cash=float(backtest_result.final_capital),
        final_position_quantity=0,
        average_cost=0.0,
        realized_pnl=realized_pnl,
        unrealized_pnl=0.0,
        total_equity=float(backtest_result.final_capital),
        order_count=len(orders),
        fill_count=len(fills),
        open_position_count=0,
        orders=tuple(orders),
        fills=tuple(fills),
    )

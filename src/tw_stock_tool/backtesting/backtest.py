from typing import Any

import pandas as pd

from tw_stock_tool.backtesting.metrics import (
    calculate_avg_hold_days,
    calculate_buy_hold_return,
    calculate_cagr,
    calculate_exposure,
    calculate_max_drawdown,
    calculate_profit_factor,
    calculate_sharpe,
    calculate_sortino,
    calculate_total_return,
    calculate_win_rate,
)
from tw_stock_tool.backtesting.results import BacktestResult


class BacktestError(Exception):
    pass


def _validate_inputs(df: pd.DataFrame, position_size: float) -> None:
    if df.empty:
        raise BacktestError("無資料可回測。")
    if not 0 < position_size <= 1:
        raise BacktestError("position_size 必須大於 0 且小於等於 1。")
    if "Close" not in df.columns or "Open" not in df.columns:
        raise BacktestError("回測資料缺少欄位: ['Open', 'Close']")
    
    from tw_stock_tool.backtesting.signals import has_legacy_signal, has_standard_signals
    if not has_legacy_signal(df) and not has_standard_signals(df):
        raise BacktestError("回測資料缺少訊號欄位，必須提供 'Signal' 或 'entry_signal'/'exit_signal'")


def _hold_days(index: pd.Index, entry_pos: int, exit_pos: int) -> int:
    entry_date = index[entry_pos]
    exit_date = index[exit_pos]
    if isinstance(entry_date, pd.Timestamp) and isinstance(exit_date, pd.Timestamp):
        return max((exit_date - entry_date).days, 0)
    return max(exit_pos - entry_pos, 0)


def _ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def run_backtest(
    df: pd.DataFrame,
    initial_capital: float = 100000,
    fee_rate: float = 0.001425,
    tax_rate: float = 0.003,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    max_hold_days: int | None = None,
    position_size: float = 1.0,
) -> dict[str, Any]:
    _validate_inputs(df, position_size)
    from tw_stock_tool.backtesting.signals import ensure_standard_signals
    df_exec = ensure_standard_signals(df)

    cash = float(initial_capital)
    shares = 0
    entry_price = 0.0
    entry_cost = 0.0
    entry_date = None
    entry_pos: int | None = None
    trades: list[dict[str, Any]] = []
    equity_curve = []
    invested_days = 0
    pending_order: str | None = None

    def close_position(exit_pos: int, exit_reason: str, exit_price: float) -> None:
        nonlocal cash, shares, entry_cost, entry_date, entry_price, entry_pos

        if shares <= 0 or entry_pos is None:
            return

        gross = shares * exit_price
        fee = gross * fee_rate
        tax = gross * tax_rate
        net = gross - fee - tax
        pnl = net - entry_cost
        pnl_pct = _ratio(pnl, entry_cost) * 100
        hold_days = _hold_days(df.index, entry_pos, exit_pos)

        cash += net
        trades.append(
            {
                "Entry Date": entry_date,
                "Exit Date": df.index[exit_pos],
                "Entry Price": entry_price,
                "Exit Price": exit_price,
                "Shares": shares,
                "PnL": pnl,
                "PnL_pct": pnl_pct,
                "Hold Days": hold_days,
                "Exit Reason": exit_reason,
                "Type": exit_reason,
            }
        )
        shares = 0
        entry_cost = 0.0
        entry_price = 0.0
        entry_date = None
        entry_pos = None

    def open_position(entry_execution_pos: int, entry_execution_price: float) -> None:
        nonlocal cash, shares, entry_cost, entry_date, entry_price, entry_pos

        if shares > 0:
            return

        invest_cash = cash * position_size
        affordable = int(invest_cash // (entry_execution_price * (1 + fee_rate)))
        if affordable <= 0:
            return

        gross = affordable * entry_execution_price
        fee = gross * fee_rate
        total_cost = gross + fee
        cash -= total_cost
        shares = affordable
        entry_cost = total_cost
        entry_price = entry_execution_price
        entry_date = df.index[entry_execution_pos]
        entry_pos = entry_execution_pos

    for pos, (_, row) in enumerate(df_exec.iterrows()):
        close_price = float(row["Close"])
        open_price = float(row["Open"]) if "Open" in row else float('nan')
        entry_sig = row.get("entry_signal", False)
        exit_sig = row.get("exit_signal", False)

        # Execute yesterday's signal at today's open to avoid look-ahead bias.
        if pending_order:
            if pd.isna(open_price) or open_price <= 0:
                pass  # Skip execution safely if missing or invalid open price
            else:
                if pending_order == "BUY" and shares == 0:
                    open_position(pos, open_price)
                elif pending_order.startswith("SELL") and shares > 0:
                    close_position(pos, pending_order, open_price)
            pending_order = None

        if shares > 0 and entry_pos is not None:
            invested_days += 1
            change_pct = _ratio(close_price - entry_price, entry_price) * 100
            current_hold_days = _hold_days(df.index, entry_pos, pos)
            if stop_loss_pct is not None and change_pct <= -abs(stop_loss_pct):
                pending_order = "SELL_STOP_LOSS"
            elif take_profit_pct is not None and change_pct >= abs(take_profit_pct):
                pending_order = "SELL_TAKE_PROFIT"
            elif max_hold_days is not None and current_hold_days >= max_hold_days:
                pending_order = "SELL_MAX_HOLD"
            elif exit_sig:
                pending_order = "SELL"
        elif entry_sig:
            pending_order = "BUY"

        equity_curve.append(cash + shares * close_price)

    if shares > 0:
        last_price = float(df.iloc[-1]["Close"])
        if not (pd.isna(last_price) or last_price <= 0):
            close_position(len(df) - 1, "SELL_EOD", last_price)
        equity_curve[-1] = cash

    equity = pd.Series(equity_curve, index=df.index, name="Equity")
    final_capital = cash
    closed_trades = trades
    wins = [t for t in closed_trades if t["PnL"] > 0]
    losses = [t for t in closed_trades if t["PnL"] <= 0]
    trade_pcts = [t["PnL_pct"] for t in closed_trades]

    result = BacktestResult(
        initial_capital=initial_capital,
        final_capital=final_capital,
        total_return_pct=calculate_total_return(initial_capital, final_capital),
        buy_hold_return_pct=calculate_buy_hold_return(df),
        cagr_pct=calculate_cagr(initial_capital, final_capital, df.index),
        exposure_pct=calculate_exposure(invested_days, len(df)),
        trade_count=len(closed_trades),
        win_rate_pct=calculate_win_rate(closed_trades),
        max_drawdown_pct=calculate_max_drawdown(equity),
        profit_factor=calculate_profit_factor(closed_trades),
        best_trade_pct=max(trade_pcts) if trade_pcts else 0.0,
        worst_trade_pct=min(trade_pcts) if trade_pcts else 0.0,
        avg_hold_days=calculate_avg_hold_days(closed_trades),
        sharpe_ratio=calculate_sharpe(equity),
        sortino_ratio=calculate_sortino(equity),
        avg_profit=sum(t["PnL"] for t in wins) / len(wins) if wins else 0.0,
        avg_loss=sum(t["PnL"] for t in losses) / len(losses) if losses else 0.0,
        trades=pd.DataFrame(trades),
        equity_curve=equity,
        start_date=df.index[0],
        end_date=df.index[-1],
    )
    return result.to_legacy_dict()

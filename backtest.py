import math
from typing import Any

import numpy as np
import pandas as pd


class BacktestError(Exception):
    pass


def _validate_inputs(df: pd.DataFrame, position_size: float) -> None:
    if df.empty:
        raise BacktestError("無資料可回測。")
    if not 0 < position_size <= 1:
        raise BacktestError("position_size 必須大於 0 且小於等於 1。")
    required = {"Close", "Signal"}
    missing = required - set(df.columns)
    if missing:
        raise BacktestError(f"回測資料缺少欄位: {sorted(missing)}")


def _hold_days(index: pd.Index, entry_pos: int, exit_pos: int) -> int:
    entry_date = index[entry_pos]
    exit_date = index[exit_pos]
    if isinstance(entry_date, pd.Timestamp) and isinstance(exit_date, pd.Timestamp):
        return max((exit_date - entry_date).days, 0)
    return max(exit_pos - entry_pos, 0)


def _safe_round(value: float, digits: int = 2) -> float:
    if value is None or not np.isfinite(value):
        return 0.0
    return round(float(value), digits)


def _annualized_years(index: pd.Index) -> float:
    if len(index) < 2:
        return 0.0
    start = index[0]
    end = index[-1]
    if isinstance(start, pd.Timestamp) and isinstance(end, pd.Timestamp):
        days = max((end - start).days, 1)
        return days / 365.0
    return len(index) / 252.0


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

    cash = float(initial_capital)
    shares = 0
    entry_price = 0.0
    entry_cost = 0.0
    entry_date = None
    entry_pos: int | None = None
    trades: list[dict[str, Any]] = []
    equity_curve = []
    invested_days = 0

    def close_position(exit_pos: int, exit_reason: str) -> None:
        nonlocal cash, shares, entry_cost, entry_date, entry_price, entry_pos

        if shares <= 0 or entry_pos is None:
            return

        row = df.iloc[exit_pos]
        exit_price = float(row["Close"])
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

    for pos, (_, row) in enumerate(df.iterrows()):
        price = float(row["Close"])
        signal = row["Signal"]

        if shares > 0 and entry_pos is not None:
            invested_days += 1
            change_pct = _ratio(price - entry_price, entry_price) * 100
            current_hold_days = _hold_days(df.index, entry_pos, pos)
            exit_reason = None
            if stop_loss_pct is not None and change_pct <= -abs(stop_loss_pct):
                exit_reason = "SELL_STOP_LOSS"
            elif take_profit_pct is not None and change_pct >= abs(take_profit_pct):
                exit_reason = "SELL_TAKE_PROFIT"
            elif max_hold_days is not None and current_hold_days >= max_hold_days:
                exit_reason = "SELL_MAX_HOLD"
            elif signal == "SELL":
                exit_reason = "SELL"

            if exit_reason:
                close_position(pos, exit_reason)

        if signal == "BUY" and shares == 0:
            invest_cash = cash * position_size
            affordable = int(invest_cash // (price * (1 + fee_rate)))
            if affordable > 0:
                gross = affordable * price
                fee = gross * fee_rate
                total_cost = gross + fee
                cash -= total_cost
                shares = affordable
                entry_cost = total_cost
                entry_price = price
                entry_date = df.index[pos]
                entry_pos = pos

        equity_curve.append(cash + shares * price)

    if shares > 0:
        close_position(len(df) - 1, "SELL_EOD")
        equity_curve[-1] = cash

    equity = pd.Series(equity_curve, index=df.index, name="Equity")
    final_capital = cash
    total_return = (final_capital / initial_capital - 1) * 100
    closed_trades = trades
    wins = [t for t in closed_trades if t["PnL"] > 0]
    losses = [t for t in closed_trades if t["PnL"] <= 0]

    peak = equity.cummax()
    drawdown = (equity / peak - 1) * 100
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    downside = returns[returns < 0]
    years = _annualized_years(df.index)
    buy_hold_return = (float(df.iloc[-1]["Close"]) / float(df.iloc[0]["Close"]) - 1) * 100
    cagr = ((final_capital / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0.0
    gross_profit = sum(t["PnL"] for t in wins)
    gross_loss = abs(sum(t["PnL"] for t in losses))
    profit_factor = (
        math.inf if gross_profit > 0 and gross_loss == 0 else _ratio(gross_profit, gross_loss)
    )
    sharpe = (
        _ratio(returns.mean(), returns.std(ddof=0)) * math.sqrt(252)
        if not returns.empty
        else 0.0
    )
    sortino = (
        _ratio(returns.mean(), downside.std(ddof=0)) * math.sqrt(252)
        if not downside.empty
        else 0.0
    )

    trade_pcts = [t["PnL_pct"] for t in closed_trades]
    hold_days = [t["Hold Days"] for t in closed_trades]

    return {
        "Initial Capital": round(initial_capital, 2),
        "Final Capital": round(final_capital, 2),
        "Total Return %": round(total_return, 2),
        "Buy and Hold Return %": round(buy_hold_return, 2),
        "CAGR %": _safe_round(cagr),
        "Exposure %": round(invested_days / len(df) * 100, 2),
        "Trade Count": len(closed_trades),
        "Win Rate %": round((len(wins) / len(closed_trades) * 100), 2) if closed_trades else 0.0,
        "Max Drawdown %": _safe_round(drawdown.min()),
        "Profit Factor": round(profit_factor, 2) if np.isfinite(profit_factor) else float("inf"),
        "Best Trade %": _safe_round(max(trade_pcts) if trade_pcts else 0.0),
        "Worst Trade %": _safe_round(min(trade_pcts) if trade_pcts else 0.0),
        "Avg Hold Days": _safe_round(sum(hold_days) / len(hold_days) if hold_days else 0.0),
        "Sharpe Ratio": _safe_round(sharpe),
        "Sortino Ratio": _safe_round(sortino),
        "Avg Profit": round(sum(t["PnL"] for t in wins) / len(wins), 2) if wins else 0.0,
        "Avg Loss": round(sum(t["PnL"] for t in losses) / len(losses), 2) if losses else 0.0,
        "Trades": pd.DataFrame(trades),
        "Equity Curve": equity,
    }

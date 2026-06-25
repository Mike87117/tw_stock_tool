"""Reusable backtest performance metrics."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _annualized_years(index: pd.Index) -> float:
    if len(index) < 2:
        return 0.0
    start = index[0]
    end = index[-1]
    if isinstance(start, pd.Timestamp) and isinstance(end, pd.Timestamp):
        days = max((end - start).days, 1)
        return days / 365.0
    return len(index) / 252.0


def _trade_records(trades: Sequence[dict[str, Any]] | pd.DataFrame) -> list[dict[str, Any]]:
    if isinstance(trades, pd.DataFrame):
        return trades.to_dict("records")
    return list(trades)


def _equity_returns(equity_curve: pd.Series | Sequence[float]) -> pd.Series:
    equity = pd.Series(equity_curve, dtype="float64")
    return equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()


def calculate_total_return(initial_capital: float, final_capital: float) -> float:
    """Return total strategy return in percent."""
    return _safe_ratio(final_capital, initial_capital) * 100 - 100


def calculate_buy_hold_return(df: pd.DataFrame | pd.Series | Sequence[float]) -> float:
    """Return buy-and-hold return in percent from the first to last close."""
    if isinstance(df, pd.DataFrame):
        closes = df["Close"]
    else:
        closes = pd.Series(df)
    closes = closes.dropna()
    if closes.empty:
        return 0.0
    first = float(closes.iloc[0])
    last = float(closes.iloc[-1])
    return (_safe_ratio(last, first) - 1) * 100


def calculate_cagr(initial_capital: float, final_capital: float, index: pd.Index) -> float:
    """Return compound annual growth rate in percent."""
    years = _annualized_years(index)
    if years <= 0 or initial_capital <= 0 or final_capital <= 0:
        return 0.0
    return ((final_capital / initial_capital) ** (1 / years) - 1) * 100


def calculate_exposure(invested_days: int, total_days: int) -> float:
    """Return percentage of bars spent in a position."""
    return _safe_ratio(invested_days, total_days) * 100


def calculate_win_rate(trades: Sequence[dict[str, Any]] | pd.DataFrame) -> float:
    """Return percentage of closed trades with positive PnL."""
    records = _trade_records(trades)
    if not records:
        return 0.0
    wins = [trade for trade in records if float(trade.get("PnL", 0.0)) > 0]
    return len(wins) / len(records) * 100


def calculate_max_drawdown(equity_curve: pd.Series | Sequence[float]) -> float:
    """Return maximum drawdown in percent."""
    equity = pd.Series(equity_curve, dtype="float64")
    if equity.empty:
        return 0.0
    peak = equity.cummax().replace(0, np.nan)
    drawdown = (equity / peak - 1) * 100
    if drawdown.dropna().empty:
        return 0.0
    return float(drawdown.min())


def calculate_profit_factor(trades: Sequence[dict[str, Any]] | pd.DataFrame) -> float:
    """Return gross profit divided by gross loss."""
    records = _trade_records(trades)
    wins = [trade for trade in records if float(trade.get("PnL", 0.0)) > 0]
    losses = [trade for trade in records if float(trade.get("PnL", 0.0)) <= 0]
    gross_profit = sum(float(trade.get("PnL", 0.0)) for trade in wins)
    gross_loss = abs(sum(float(trade.get("PnL", 0.0)) for trade in losses))
    if gross_profit > 0 and gross_loss == 0:
        return math.inf
    return _safe_ratio(gross_profit, gross_loss)


def calculate_sharpe(equity_curve: pd.Series | Sequence[float]) -> float:
    """Return annualized Sharpe ratio from equity-curve daily returns."""
    returns = _equity_returns(equity_curve)
    if returns.empty:
        return 0.0
    return _safe_ratio(float(returns.mean()), float(returns.std(ddof=0))) * math.sqrt(252)


def calculate_sortino(equity_curve: pd.Series | Sequence[float]) -> float:
    """Return annualized Sortino ratio from equity-curve downside returns."""
    returns = _equity_returns(equity_curve)
    downside = returns[returns < 0]
    if downside.empty:
        return 0.0
    return _safe_ratio(float(returns.mean()), float(downside.std(ddof=0))) * math.sqrt(252)


def calculate_avg_hold_days(trades: Sequence[dict[str, Any]] | pd.DataFrame) -> float:
    """Return average closed-trade holding period in days."""
    records = _trade_records(trades)
    hold_days = [float(trade.get("Hold Days", 0.0)) for trade in records]
    if not hold_days:
        return 0.0
    return sum(hold_days) / len(hold_days)

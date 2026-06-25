"""Backtest result schema and legacy-output adapter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


def _safe_round(value: float, digits: int = 2) -> float:
    if value is None or not np.isfinite(value):
        return 0.0
    return round(float(value), digits)


@dataclass(slots=True)
class BacktestResult:
    """Structured backtest result used internally before legacy dict export."""

    initial_capital: float
    final_capital: float
    total_return_pct: float
    buy_hold_return_pct: float
    cagr_pct: float
    exposure_pct: float
    trade_count: int
    win_rate_pct: float
    max_drawdown_pct: float
    profit_factor: float
    best_trade_pct: float
    worst_trade_pct: float
    avg_hold_days: float
    sharpe_ratio: float
    sortino_ratio: float
    avg_profit: float
    avg_loss: float
    trades: pd.DataFrame
    equity_curve: pd.Series
    stock: str | None = None
    strategy: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    start_date: Any | None = None
    end_date: Any | None = None

    def to_legacy_dict(self) -> dict[str, Any]:
        """Return the historical run_backtest() dict format."""
        return {
            "Initial Capital": round(self.initial_capital, 2),
            "Final Capital": round(self.final_capital, 2),
            "Total Return %": round(self.total_return_pct, 2),
            "Buy and Hold Return %": round(self.buy_hold_return_pct, 2),
            "CAGR %": _safe_round(self.cagr_pct),
            "Exposure %": round(self.exposure_pct, 2),
            "Trade Count": self.trade_count,
            "Win Rate %": round(self.win_rate_pct, 2),
            "Max Drawdown %": _safe_round(self.max_drawdown_pct),
            "Profit Factor": (
                round(self.profit_factor, 2)
                if np.isfinite(self.profit_factor)
                else float("inf")
            ),
            "Best Trade %": _safe_round(self.best_trade_pct),
            "Worst Trade %": _safe_round(self.worst_trade_pct),
            "Avg Hold Days": _safe_round(self.avg_hold_days),
            "Sharpe Ratio": _safe_round(self.sharpe_ratio),
            "Sortino Ratio": _safe_round(self.sortino_ratio),
            "Avg Profit": round(self.avg_profit, 2),
            "Avg Loss": round(self.avg_loss, 2),
            "Trades": self.trades,
            "Equity Curve": self.equity_curve,
        }

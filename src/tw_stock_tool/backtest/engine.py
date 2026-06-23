"""Long-only backtest engine using standardized strategy signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd


class SignalStrategy(Protocol):
    """Protocol for strategies consumed by BacktestEngine."""

    name: str

    def generate_signals(
        self,
        df: pd.DataFrame,
        params: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """Generate entry_signal and exit_signal columns."""

    def validate_signals(self, result_df: pd.DataFrame) -> None:
        """Validate generated signal columns."""


@dataclass(frozen=True)
class BacktestResult:
    """Summary output from BacktestEngine."""

    total_return: float
    max_drawdown: float
    win_rate: float
    trade_count: int
    final_equity: float
    trade_log: pd.DataFrame

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation for callers that prefer mappings."""
        return {
            "total_return": self.total_return,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "trade_count": self.trade_count,
            "final_equity": self.final_equity,
            "trade_log": self.trade_log,
        }


class BacktestEngine:
    """Simple long-only backtest engine with next-bar-open execution."""

    required_price_columns = ("Open", "Close")

    def __init__(
        self,
        price_df: pd.DataFrame,
        strategy: SignalStrategy,
        params: dict[str, Any] | None = None,
        initial_cash: float = 100_000.0,
        commission: float = 0.0,
        tax: float = 0.0,
        slippage: float = 0.0,
    ) -> None:
        self.price_df = price_df.copy()
        self.strategy = strategy
        self.params = params
        self.initial_cash = float(initial_cash)
        self.commission = float(commission)
        self.tax = float(tax)
        self.slippage = float(slippage)
        self._validate_inputs()

    def run(self) -> BacktestResult:
        """Run a long-only backtest and return performance metrics."""
        signals = self.strategy.generate_signals(self.price_df.copy(), self.params)
        self.strategy.validate_signals(signals)
        self._validate_signal_frame(signals)

        cash = self.initial_cash
        shares = 0.0
        entry_date: Any | None = None
        entry_price = 0.0
        entry_cost = 0.0
        equity_curve: list[float] = []
        trades: list[dict[str, Any]] = []

        for index in range(len(self.price_df)):
            row = self.price_df.iloc[index]

            if index > 0:
                previous_signal = signals.iloc[index - 1]
                open_price = float(row["Open"])
                current_date = self.price_df.index[index]

                if shares <= 0 and bool(previous_signal["entry_signal"]):
                    fill_price = self._entry_fill_price(open_price)
                    shares = cash / (fill_price * (1 + self.commission))
                    entry_cost = shares * fill_price * (1 + self.commission)
                    cash -= entry_cost
                    entry_date = current_date
                    entry_price = fill_price
                elif shares > 0 and bool(previous_signal["exit_signal"]):
                    fill_price = self._exit_fill_price(open_price)
                    proceeds = shares * fill_price * (1 - self.commission - self.tax)
                    cash += proceeds
                    pnl = proceeds - entry_cost
                    trades.append(
                        {
                            "Entry Date": entry_date,
                            "Exit Date": current_date,
                            "Entry Price": entry_price,
                            "Exit Price": fill_price,
                            "Shares": shares,
                            "PnL": pnl,
                            "PnL %": pnl / entry_cost if entry_cost else 0.0,
                        }
                    )
                    shares = 0.0
                    entry_date = None
                    entry_price = 0.0
                    entry_cost = 0.0

            close_price = float(row["Close"])
            equity_curve.append(cash + shares * close_price)

        trade_log = pd.DataFrame(
            trades,
            columns=["Entry Date", "Exit Date", "Entry Price", "Exit Price", "Shares", "PnL", "PnL %"],
        )
        final_equity = float(equity_curve[-1]) if equity_curve else self.initial_cash
        total_return = final_equity / self.initial_cash - 1 if self.initial_cash else 0.0
        max_drawdown = self._max_drawdown(pd.Series(equity_curve, index=self.price_df.index))
        win_rate = self._win_rate(trade_log)

        return BacktestResult(
            total_return=total_return,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            trade_count=len(trade_log),
            final_equity=final_equity,
            trade_log=trade_log,
        )

    def _validate_inputs(self) -> None:
        if self.price_df.empty:
            raise ValueError("price_df cannot be empty")
        missing = [column for column in self.required_price_columns if column not in self.price_df.columns]
        if missing:
            raise ValueError(f"price_df missing required columns: {', '.join(missing)}")
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        for name, value in (
            ("commission", self.commission),
            ("tax", self.tax),
            ("slippage", self.slippage),
        ):
            if value < 0:
                raise ValueError(f"{name} cannot be negative")

    def _validate_signal_frame(self, signals: pd.DataFrame) -> None:
        if len(signals) != len(self.price_df):
            raise ValueError("signal length must match price dataframe length")
        if not signals.index.equals(self.price_df.index):
            raise ValueError("signal index must match price dataframe index")

    def _entry_fill_price(self, open_price: float) -> float:
        return open_price * (1 + self.slippage)

    def _exit_fill_price(self, open_price: float) -> float:
        return open_price * (1 - self.slippage)

    @staticmethod
    def _max_drawdown(equity_curve: pd.Series) -> float:
        if equity_curve.empty:
            return 0.0
        running_max = equity_curve.cummax()
        drawdown = equity_curve / running_max - 1
        return float(drawdown.min())

    @staticmethod
    def _win_rate(trade_log: pd.DataFrame) -> float:
        if trade_log.empty:
            return 0.0
        return float((trade_log["PnL"] > 0).mean())

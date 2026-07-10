import pandas as pd
import math
from typing import Mapping
from tw_stock_tool.paper_trading.models import SimulatedOrder, SimulatedPortfolio
from tw_stock_tool.simulated_paper_trading_guard.models import SimulatedPaperTradingGuardError

class DataFrameReferencePriceProvider:
    def __init__(self, df: pd.DataFrame, *, price_column: str = "Open") -> None:
        if not isinstance(df, pd.DataFrame):
            raise SimulatedPaperTradingGuardError("df must be a pandas DataFrame.")
        if df.empty:
            raise SimulatedPaperTradingGuardError("DataFrame must not be empty.")
        if not price_column or not isinstance(price_column, str) or not price_column.strip():
            raise SimulatedPaperTradingGuardError("price_column must be a non-blank string.")
        if price_column not in df.columns:
            raise SimulatedPaperTradingGuardError(f"DataFrame must contain '{price_column}' column.")
        if not df.index.is_unique:
            raise SimulatedPaperTradingGuardError("DataFrame index must be unique.")

        self._df = df
        self._price_column = price_column

    def __call__(self, order: SimulatedOrder, portfolio: SimulatedPortfolio) -> float:
        if not isinstance(order, SimulatedOrder):
            raise SimulatedPaperTradingGuardError("order must be a SimulatedOrder.")
        if not isinstance(portfolio, SimulatedPortfolio):
            raise SimulatedPaperTradingGuardError("portfolio must be a SimulatedPortfolio.")

        signal_time = order.signal_time
        if signal_time not in self._df.index:
            raise SimulatedPaperTradingGuardError(f"order.signal_time {signal_time} not found in DataFrame index.")

        price = self._df.loc[signal_time, self._price_column]

        if isinstance(price, pd.Series):
            price = price.iloc[0]

        if pd.isna(price):
            raise SimulatedPaperTradingGuardError("Price must not be NaN.")

        if type(price) is bool or type(price).__name__ in ("bool", "bool_"):
            raise SimulatedPaperTradingGuardError("Price must be numeric, not boolean.")

        try:
            price_float = float(price)
        except (ValueError, TypeError):
            raise SimulatedPaperTradingGuardError("Price must be numeric.")

        if price_float <= 0.0:
            raise SimulatedPaperTradingGuardError("Price must be strictly positive.")

        return price_float

class DataFramePortfolioExposureProvider:
    def __init__(
        self,
        dataframes: Mapping[str, pd.DataFrame],
        *,
        price_column: str = "Open",
    ) -> None:
        if not isinstance(dataframes, Mapping):
            raise SimulatedPaperTradingGuardError("dataframes must be a Mapping.")

        for k, v in dataframes.items():
            if not isinstance(k, str) or not k.strip():
                raise SimulatedPaperTradingGuardError("symbol keys must be non-blank strings.")
            if not isinstance(v, pd.DataFrame):
                raise SimulatedPaperTradingGuardError("values must be pandas DataFrames.")
            if v.empty:
                raise SimulatedPaperTradingGuardError("DataFrame must not be empty.")
            if not price_column or not isinstance(price_column, str) or not price_column.strip():
                raise SimulatedPaperTradingGuardError("price_column must be a non-blank string.")
            if price_column not in v.columns:
                raise SimulatedPaperTradingGuardError(f"DataFrame must contain '{price_column}' column.")
            if not v.index.is_unique:
                raise SimulatedPaperTradingGuardError("DataFrame index must be unique.")

        if not price_column or not isinstance(price_column, str) or not price_column.strip():
            raise SimulatedPaperTradingGuardError("price_column must be a non-blank string.")

        self._dataframes = dataframes
        self._price_column = price_column

    def __call__(
        self,
        order: SimulatedOrder,
        portfolio: SimulatedPortfolio,
    ) -> float:
        if not isinstance(order, SimulatedOrder):
            raise SimulatedPaperTradingGuardError("order must be a SimulatedOrder.")
        if not isinstance(portfolio, SimulatedPortfolio):
            raise SimulatedPaperTradingGuardError("portfolio must be a SimulatedPortfolio.")

        total_exposure = 0.0
        signal_time = order.signal_time

        for pos in portfolio.positions.values():
            if pos.quantity > 0:
                symbol = pos.symbol
                if symbol not in self._dataframes:
                    raise SimulatedPaperTradingGuardError(f"No DataFrame found for open position symbol: {symbol}")

                df = self._dataframes[symbol]

                if signal_time not in df.index:
                    raise SimulatedPaperTradingGuardError(f"order.signal_time {signal_time} not found in DataFrame index for {symbol}.")

                price = df.loc[signal_time, self._price_column]

                if isinstance(price, pd.Series):
                    price = price.iloc[0]

                if pd.isna(price):
                    raise SimulatedPaperTradingGuardError(f"Price must not be NaN for {symbol}.")

                if type(price) is bool or type(price).__name__ in ("bool", "bool_"):
                    raise SimulatedPaperTradingGuardError(f"Price must be numeric, not boolean for {symbol}.")

                try:
                    price_float = float(price)
                except (ValueError, TypeError):
                    raise SimulatedPaperTradingGuardError(f"Price must be numeric for {symbol}.")

                if not math.isfinite(price_float):
                    raise SimulatedPaperTradingGuardError(f"Price must be finite for {symbol}.")

                if price_float <= 0.0:
                    raise SimulatedPaperTradingGuardError(f"Price must be strictly positive for {symbol}.")

                total_exposure += float(pos.quantity) * price_float

        return total_exposure

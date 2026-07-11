import unittest
import math
import pandas as pd
from tw_stock_tool.paper_trading.models import SimulatedOrder, SimulatedPortfolio, SimulatedPosition
from tw_stock_tool.simulated_paper_trading_guard.providers import DataFrameReferencePriceProvider, DataFramePortfolioExposureProvider
from tw_stock_tool.simulated_paper_trading_guard.models import SimulatedPaperTradingGuardError

class TestDataFrameReferencePriceProvider(unittest.TestCase):
    def test_provider_returns_signal_row_open_by_default(self):
        df = pd.DataFrame({"Open": [100.0, 105.0]}, index=pd.to_datetime(["2023-01-01", "2023-01-02"]))
        provider = DataFrameReferencePriceProvider(df)
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01"))
        portfolio = SimulatedPortfolio(cash=1000.0)
        self.assertEqual(provider(order, portfolio), 100.0)

    def test_provider_supports_custom_price_column(self):
        df = pd.DataFrame({"Close": [100.0, 105.0]}, index=pd.to_datetime(["2023-01-01", "2023-01-02"]))
        provider = DataFrameReferencePriceProvider(df, price_column="Close")
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-02"))
        portfolio = SimulatedPortfolio(cash=1000.0)
        self.assertEqual(provider(order, portfolio), 105.0)

    def test_provider_rejects_non_dataframe_input(self):
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFrameReferencePriceProvider([1, 2, 3]) # type: ignore

    def test_provider_rejects_empty_dataframe(self):
        df = pd.DataFrame()
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFrameReferencePriceProvider(df)

    def test_provider_rejects_blank_price_column(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFrameReferencePriceProvider(df, price_column="   ")
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFrameReferencePriceProvider(df, price_column="")

    def test_provider_rejects_missing_price_column(self):
        df = pd.DataFrame({"Close": [100.0]}, index=[1])
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFrameReferencePriceProvider(df)

    def test_provider_rejects_duplicate_dataframe_index(self):
        df = pd.DataFrame({"Open": [100.0, 105.0]}, index=[1, 1])
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFrameReferencePriceProvider(df)

    def test_provider_rejects_missing_order_signal_time(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFrameReferencePriceProvider(df)
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=2)
        portfolio = SimulatedPortfolio(cash=1000.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_rejects_nan_price(self):
        df = pd.DataFrame({"Open": [float('nan')]}, index=[1])
        provider = DataFrameReferencePriceProvider(df)
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_rejects_non_numeric_price(self):
        df = pd.DataFrame({"Open": ["abc"]}, index=[1])
        provider = DataFrameReferencePriceProvider(df)
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_rejects_boolean_price(self):
        df = pd.DataFrame({"Open": [True]}, index=[1])
        provider = DataFrameReferencePriceProvider(df)
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_rejects_zero_price(self):
        df = pd.DataFrame({"Open": [0.0]}, index=[1])
        provider = DataFrameReferencePriceProvider(df)
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_rejects_negative_price(self):
        df = pd.DataFrame({"Open": [-10.0]}, index=[1])
        provider = DataFrameReferencePriceProvider(df)
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_rejects_non_simulated_order_order(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFrameReferencePriceProvider(df)
        portfolio = SimulatedPortfolio(cash=1000.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider("not an order", portfolio) # type: ignore

    def test_provider_rejects_non_simulated_portfolio_portfolio(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFrameReferencePriceProvider(df)
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, "not a portfolio") # type: ignore

    def test_provider_does_not_read_or_depend_on_order_metadata_price(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFrameReferencePriceProvider(df)
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1, metadata={"price": 999.0})
        portfolio = SimulatedPortfolio(cash=1000.0)
        price = provider(order, portfolio)
        self.assertEqual(price, 100.0)

    def test_provider_does_not_mutate_dataframe(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFrameReferencePriceProvider(df)
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        provider(order, portfolio)
        self.assertIn("Open", df.columns)
        self.assertEqual(df.loc[1, "Open"], 100.0)

    def test_provider_returns_plain_float(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFrameReferencePriceProvider(df)
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        price = provider(order, portfolio)
        self.assertEqual(type(price), float)

class TestDataFramePortfolioExposureProvider(unittest.TestCase):
    def test_provider_exposures_two_symbols(self):
        df1 = pd.DataFrame({"Open": [100.0, 105.0]}, index=pd.to_datetime(["2023-01-01", "2023-01-02"]))
        df2 = pd.DataFrame({"Open": [50.0, 55.0]}, index=pd.to_datetime(["2023-01-01", "2023-01-02"]))
        provider = DataFramePortfolioExposureProvider({"2330": df1, "2317": df2})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01"))
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        portfolio.positions["2317"] = SimulatedPosition(symbol="2317", quantity=3, average_cost=40.0)

        exposure = provider(order, portfolio)
        self.assertEqual(exposure, 350.0)
        self.assertEqual(type(exposure), float)

    def test_provider_default_column_uses_signal_row_open(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        self.assertEqual(provider(order, portfolio), 200.0)

    def test_provider_custom_price_column(self):
        df = pd.DataFrame({"Close": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df}, price_column="Close")
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        self.assertEqual(provider(order, portfolio), 200.0)

    def test_provider_empty_portfolio(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        self.assertEqual(provider(order, portfolio), 0.0)

    def test_provider_zero_quantity_positions(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=0, average_cost=90.0)
        self.assertEqual(provider(order, portfolio), 0.0)

    def test_provider_ignores_closed_positions_missing_df(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2317"] = SimulatedPosition(symbol="2317", quantity=0, average_cost=90.0)
        self.assertEqual(provider(order, portfolio), 0.0)

    def test_provider_uses_signal_time_exact(self):
        df = pd.DataFrame({"Open": [90.0, 100.0, 110.0]}, index=[0, 1, 2])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        self.assertEqual(provider(order, portfolio), 200.0)

    def test_provider_ignores_avg_cost_cash_metadata(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1, metadata={"price": 999.0})
        portfolio = SimulatedPortfolio(cash=5000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        self.assertEqual(provider(order, portfolio), 200.0)

    def test_provider_does_not_mutate(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)

        provider(order, portfolio)

        self.assertIn("Open", df.columns)
        self.assertEqual(df.loc[1, "Open"], 100.0)
        self.assertEqual(portfolio.cash, 1000.0)
        self.assertEqual(portfolio.positions["2330"].quantity, 2)
        self.assertNotIn("price", order.metadata)

    def test_provider_constructor_rejects_non_mapping(self):
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFramePortfolioExposureProvider([1, 2, 3]) # type: ignore

    def test_provider_constructor_rejects_blank_symbol(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFramePortfolioExposureProvider({"   ": df})
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFramePortfolioExposureProvider({"": df})

    def test_provider_constructor_rejects_non_string_symbol(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFramePortfolioExposureProvider({1: df}) # type: ignore

    def test_provider_constructor_rejects_non_dataframe(self):
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFramePortfolioExposureProvider({"2330": "df"}) # type: ignore

    def test_provider_constructor_rejects_empty_dataframe(self):
        df = pd.DataFrame()
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFramePortfolioExposureProvider({"2330": df})

    def test_provider_constructor_rejects_blank_price_column(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFramePortfolioExposureProvider({"2330": df}, price_column="   ")
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFramePortfolioExposureProvider({"2330": df}, price_column="")

    def test_provider_constructor_rejects_missing_price_column(self):
        df = pd.DataFrame({"Close": [100.0]}, index=[1])
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFramePortfolioExposureProvider({"2330": df})

    def test_provider_constructor_rejects_duplicate_index(self):
        df = pd.DataFrame({"Open": [100.0, 105.0]}, index=[1, 1])
        with self.assertRaises(SimulatedPaperTradingGuardError):
            DataFramePortfolioExposureProvider({"2330": df})

    def test_provider_call_rejects_non_simulated_order(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        portfolio = SimulatedPortfolio(cash=1000.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider("not an order", portfolio) # type: ignore

    def test_provider_call_rejects_non_simulated_portfolio(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=1, signal_time=1)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, "not a portfolio") # type: ignore

    def test_provider_call_rejects_missing_df(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2317"] = SimulatedPosition(symbol="2317", quantity=2, average_cost=90.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_call_rejects_missing_signal_time(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=2)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_call_rejects_nan_price(self):
        df = pd.DataFrame({"Open": [float("nan")]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_call_rejects_positive_infinity(self):
        df = pd.DataFrame({"Open": [float("inf")]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_call_rejects_negative_infinity(self):
        df = pd.DataFrame({"Open": [float("-inf")]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_call_rejects_boolean_price(self):
        df = pd.DataFrame({"Open": [True]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_call_rejects_nonnumeric_price(self):
        df = pd.DataFrame({"Open": ["abc"]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_call_rejects_zero_price(self):
        df = pd.DataFrame({"Open": [0.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_call_rejects_negative_price(self):
        df = pd.DataFrame({"Open": [-1.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_call_rejects_entire_calculation(self):
        df1 = pd.DataFrame({"Open": [100.0]}, index=[1])
        df2 = pd.DataFrame({"Open": ["abc"]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df1, "2317": df2})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        portfolio.positions["2317"] = SimulatedPosition(symbol="2317", quantity=2, average_cost=90.0)
        with self.assertRaises(SimulatedPaperTradingGuardError):
            provider(order, portfolio)

    def test_provider_boundary_unused_symbols(self):
        df1 = pd.DataFrame({"Open": [100.0]}, index=[1])
        df2 = pd.DataFrame({"Open": [200.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df1, "unused": df2})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        self.assertEqual(provider(order, portfolio), 200.0)

    def test_provider_candidate_order_not_in_portfolio(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        self.assertEqual(provider(order, portfolio), 200.0)

    def test_provider_sell_candidate_does_not_reduce_exposure(self):
        df = pd.DataFrame({"Open": [100.0]}, index=[1])
        provider = DataFramePortfolioExposureProvider({"2330": df})
        order = SimulatedOrder(order_id="1", symbol="2330", side="SELL", quantity=1, signal_time=1)
        portfolio = SimulatedPortfolio(cash=1000.0)
        portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0)
        self.assertEqual(provider(order, portfolio), 200.0)




from tw_stock_tool.paper_trading.runtime import SimulatedPaperTradingRuntimeState, SimulatedPendingOrderState
from tw_stock_tool.simulated_paper_trading_guard.providers import ChronologicalRuntimePortfolioExposureProvider

class TestChronologicalRuntimePortfolioExposureProvider(unittest.TestCase):

    def setUp(self):
        self.df = pd.DataFrame({"Open": [100.0, 105.0]}, index=pd.to_datetime(["2023-01-01", "2023-01-02"]))
        self.runtime_state = SimulatedPaperTradingRuntimeState(
            portfolio=SimulatedPortfolio(cash=1000.0)
        )
        self.runtime_state.portfolio.positions["2330"] = SimulatedPosition(symbol="2330", quantity=2, average_cost=90.0, realized_pnl=0.0)
        self.provider = ChronologicalRuntimePortfolioExposureProvider(
            {"2330": self.df}, self.runtime_state
        )

    def test_provider_constructor_rejects_non_mapping(self):
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "dataframes must be a Mapping"):
            ChronologicalRuntimePortfolioExposureProvider([], self.runtime_state) # type: ignore

    def test_provider_constructor_rejects_empty_mapping(self):
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "dataframes must not be empty"):
            ChronologicalRuntimePortfolioExposureProvider({}, self.runtime_state)

    def test_provider_constructor_rejects_blank_symbol(self):
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "symbol keys must be non-blank strings"):
            ChronologicalRuntimePortfolioExposureProvider({"": self.df}, self.runtime_state)

    def test_provider_constructor_rejects_non_string_symbol(self):
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "symbol keys must be non-blank strings"):
            ChronologicalRuntimePortfolioExposureProvider({1: self.df}, self.runtime_state) # type: ignore

    def test_provider_constructor_rejects_non_dataframe(self):
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "values must be pandas DataFrames"):
            ChronologicalRuntimePortfolioExposureProvider({"2330": "not df"}, self.runtime_state) # type: ignore

    def test_provider_constructor_rejects_empty_dataframe(self):
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "DataFrame must not be empty"):
            ChronologicalRuntimePortfolioExposureProvider({"2330": pd.DataFrame()}, self.runtime_state)

    def test_provider_constructor_rejects_blank_price_column(self):
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "price_column must be a non-blank string"):
            ChronologicalRuntimePortfolioExposureProvider({"2330": self.df}, self.runtime_state, price_column="")

    def test_provider_constructor_rejects_missing_price_column(self):
        df_no_col = pd.DataFrame({"Close": [100.0]}, index=[1])
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "DataFrame must contain 'Open' column"):
            ChronologicalRuntimePortfolioExposureProvider({"2330": df_no_col}, self.runtime_state)

    def test_provider_constructor_rejects_duplicate_index(self):
        df_dup = pd.DataFrame({"Open": [100.0, 105.0]}, index=[1, 1])
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "DataFrame index must be unique"):
            ChronologicalRuntimePortfolioExposureProvider({"2330": df_dup}, self.runtime_state)

    def test_provider_constructor_rejects_non_monotonic_index(self):
        df_nonmono = pd.DataFrame({"Open": [100.0, 105.0]}, index=[2, 1])
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "DataFrame index must be monotonic increasing"):
            ChronologicalRuntimePortfolioExposureProvider({"2330": df_nonmono}, self.runtime_state)

    def test_provider_constructor_rejects_invalid_runtime_state(self):
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "runtime_state must be a SimulatedPaperTradingRuntimeState"):
            ChronologicalRuntimePortfolioExposureProvider({"2330": self.df}, "not_state") # type: ignore

    def test_provider_exact_timestamp_valuation(self):
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01"))
        # 2 shares * 100.0 = 200.0
        self.assertEqual(self.provider(order, self.runtime_state.portfolio), 200.0)

    def test_provider_missing_timestamp_uses_nearest_earlier_row(self):
        # Time is 2023-01-01 12:00:00, nearest earlier is 2023-01-01 00:00:00 (100.0)
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01 12:00:00"))
        self.assertEqual(self.provider(order, self.runtime_state.portfolio), 200.0)

    def test_provider_later_row_never_used(self):
        # Time is 2022-12-31, earlier than all rows.
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=pd.to_datetime("2022-12-31"))
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "No row exists at or before signal time"):
            self.provider(order, self.runtime_state.portfolio)

    def test_provider_non_comparable_signal_time_raises(self):
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time="not_a_time") # type: ignore
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "Index cannot be compared with signal_time"):
            self.provider(order, self.runtime_state.portfolio)

    def test_provider_invalid_price_raises_does_not_fallback(self):
        df_bad = pd.DataFrame({"Open": [100.0, float('nan')]}, index=pd.to_datetime(["2023-01-01", "2023-01-02"]))
        provider = ChronologicalRuntimePortfolioExposureProvider({"2330": df_bad}, self.runtime_state)
        # Signal time is Jan 3. Nearest earlier is Jan 2, which has NaN. Should raise instead of falling back to Jan 1.
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-03"))
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "Price must not be NaN"):
            provider(order, self.runtime_state.portfolio)

    def test_provider_invalid_prices_fail_closed(self):
        invalid_prices = [False, True, "invalid", float('nan'), float('inf'), float('-inf'), 0.0, -10.0]
        for ip in invalid_prices:
            df_bad = pd.DataFrame({"Open": [ip]}, index=pd.to_datetime(["2023-01-01"]))
            provider = ChronologicalRuntimePortfolioExposureProvider({"2330": df_bad}, self.runtime_state)
            order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01"))
            with self.assertRaises(SimulatedPaperTradingGuardError):
                provider(order, self.runtime_state.portfolio)

    def test_provider_multiple_positions_summed(self):
        self.runtime_state.portfolio.positions["2317"] = SimulatedPosition(symbol="2317", quantity=5, average_cost=90.0, realized_pnl=0.0)
        df_2317 = pd.DataFrame({"Open": [10.0]}, index=pd.to_datetime(["2023-01-01"]))
        provider = ChronologicalRuntimePortfolioExposureProvider(
            {"2330": self.df, "2317": df_2317}, self.runtime_state
        )
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01"))
        # 2330: 2 * 100 = 200
        # 2317: 5 * 10 = 50
        # Total: 250
        self.assertEqual(provider(order, self.runtime_state.portfolio), 250.0)

    def test_provider_ignores_zero_quantity_positions(self):
        self.runtime_state.portfolio.positions["2317"] = SimulatedPosition(symbol="2317", quantity=0, average_cost=90.0, realized_pnl=0.0)
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01"))
        # Only 2330 is counted, 2317 has qty=0 so it's skipped, avoiding missing df error.
        self.assertEqual(self.provider(order, self.runtime_state.portfolio), 200.0)

    def test_provider_missing_df_for_positive_position_raises(self):
        self.runtime_state.portfolio.positions["2317"] = SimulatedPosition(symbol="2317", quantity=1, average_cost=90.0, realized_pnl=0.0)
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01"))
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "No DataFrame found for open position symbol: 2317"):
            self.provider(order, self.runtime_state.portfolio)

    def test_provider_wrong_portfolio_identity_raises(self):
        other_portfolio = SimulatedPortfolio(cash=1000.0)
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01"))
        with self.assertRaisesRegex(SimulatedPaperTradingGuardError, "Portfolio identity does not match runtime_state.portfolio."):
            self.provider(order, other_portfolio)

    def test_provider_includes_pending_buy_reservation(self):
        order_pending = SimulatedOrder(order_id="2", symbol="9999", side="BUY", quantity=10, signal_time=pd.to_datetime("2023-01-01"))
        self.runtime_state.pending_orders["9999"] = SimulatedPendingOrderState(order=order_pending, reference_price=50.0)
        # Pending BUY notional = 10 * 50 = 500
        order = SimulatedOrder(order_id="1", symbol="8888", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01"))
        # 2 shares * 100.0 + 500.0 = 700.0
        self.assertEqual(self.provider(order, self.runtime_state.portfolio), 700.0)

    def test_provider_pending_sell_contributes_zero_reservation(self):
        order_pending = SimulatedOrder(order_id="2", symbol="9999", side="SELL", quantity=10, signal_time=pd.to_datetime("2023-01-01"))
        self.runtime_state.pending_orders["9999"] = SimulatedPendingOrderState(order=order_pending, reference_price=50.0)
        order = SimulatedOrder(order_id="1", symbol="8888", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01"))
        # 2 shares * 100.0 + 0.0 = 200.0
        self.assertEqual(self.provider(order, self.runtime_state.portfolio), 200.0)

    def test_provider_current_candidate_notional_not_included(self):
        order = SimulatedOrder(order_id="1", symbol="2330", side="BUY", quantity=10, signal_time=pd.to_datetime("2023-01-01"))
        # The candidate is NOT in pending orders yet, so its exposure shouldn't be added by the provider
        # Only existing positions (2330: 2 shares * 100 = 200) are evaluated.
        self.assertEqual(self.provider(order, self.runtime_state.portfolio), 200.0)

    def test_provider_return_type_exactly_float(self):
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01"))
        ret = self.provider(order, self.runtime_state.portfolio)
        self.assertEqual(type(ret), float)

    def test_provider_does_not_mutate_inputs(self):
        df_copy = self.df.copy()
        order = SimulatedOrder(order_id="1", symbol="9999", side="BUY", quantity=1, signal_time=pd.to_datetime("2023-01-01"))
        order_dict = repr(order)

        self.provider(order, self.runtime_state.portfolio)

        pd.testing.assert_frame_equal(self.df, df_copy)
        self.assertEqual(repr(order), order_dict)

if __name__ == "__main__":
    unittest.main()

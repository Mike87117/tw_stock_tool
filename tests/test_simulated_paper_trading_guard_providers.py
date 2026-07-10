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

if __name__ == "__main__":
    unittest.main()

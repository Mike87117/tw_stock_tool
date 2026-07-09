import unittest
import pandas as pd
from tw_stock_tool.paper_trading.models import SimulatedOrder, SimulatedPortfolio
from tw_stock_tool.simulated_paper_trading_guard.providers import DataFrameReferencePriceProvider
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

if __name__ == "__main__":
    unittest.main()

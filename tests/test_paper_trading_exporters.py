import unittest

from tw_stock_tool.paper_trading.models import SimulatedOrder, SimulatedFill
from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult
from tw_stock_tool.paper_trading.exporters import export_simulated_paper_trading_markdown

class TestPaperTradingMarkdownExporter(unittest.TestCase):

    def setUp(self):
        self.order = SimulatedOrder(
            order_id="order-1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            signal_time="2023-01-01 10:00:00",
            created_at="2023-01-01 10:05:00",
            strategy="mean|reversion"
        )
        self.fill = SimulatedFill(
            order_id="order-1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            price=100.5,
            filled_at="2023-01-01 10:10:00",
            fee=143.0,
            tax=0.0,
            slippage=50.0
        )
        self.result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=1000000.0,
            final_cash=899307.0,
            final_position_quantity=1000,
            average_cost=100.5,
            realized_pnl=0.0,
            unrealized_pnl=5000.0,
            total_equity=1004307.0,
            order_count=1,
            fill_count=1,
            open_position_count=1,
            orders=(self.order,),
            fills=(self.fill,),
        )

    def test_export_simulated_paper_trading_markdown(self):
        output = export_simulated_paper_trading_markdown(self.result)

        # 1. Verify returns string
        self.assertIsInstance(output, str)

        # 2. Output contains the three expected sections
        self.assertIn("# Simulated Paper Trading Report", output)
        self.assertIn("## Summary", output)
        self.assertIn("## Orders", output)
        self.assertIn("## Fills", output)

        # 3. Summary table contains expected metrics
        self.assertIn("| Symbol | 2330 |", output)
        self.assertIn("| Initial Cash | 1,000,000.00 |", output)
        self.assertIn("| Final Cash | 899,307.00 |", output)
        self.assertIn("| Total Equity | 1,004,307.00 |", output)
        self.assertIn("| Total Return | 4,307.00 |", output)
        self.assertIn("| Total Return % | 0.43% |", output)
        self.assertIn("| Final Position Quantity | 1000 |", output)

        # 4. Order rows are represented
        self.assertIn("| order-1 | 2330 | BUY | 1000 | 2023-01-01 10:00:00 | 2023-01-01 10:05:00 | mean\\|reversion |", output)
        self.assertNotIn("mean|reversion", output)

        # 5. Fill rows are represented
        self.assertIn("| order-1 | 2330 | BUY | 1000 | 100.50 | 2023-01-01 10:10:00 | 143.00 | 0.00 | 50.00 | 100,500.00 | -100,693.00 |", output)

        # 7. No forbidden words
        forbidden_words = [
            "recommended", "recommendation", "buy recommendation", "sell recommendation",
            "hold recommendation", "profitable", "bad trade", "safe", "guaranteed"
        ]
        lower_output = output.lower()
        for word in forbidden_words:
            self.assertNotIn(word, lower_output)

    def test_empty_orders_and_fills(self):
        empty_result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=1000000.0,
            final_cash=1000000.0,
            final_position_quantity=0,
            average_cost=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_equity=1000000.0,
            order_count=0,
            fill_count=0,
            open_position_count=0,
            orders=(),
            fills=(),
        )
        output = export_simulated_paper_trading_markdown(empty_result)

        self.assertIn("## Orders", output)
        self.assertIn("## Fills", output)

        self.assertIn("*No orders to display.*", output)
        self.assertIn("*No fills to display.*", output)

        # Should only contain the summary items, the empty orders/fills headers, but no extra data lines.
        lines = output.strip().split("\n")
        self.assertGreater(len(lines), 15)
        # Check there is no "order-1"
        self.assertNotIn("order-1", output)

class TestPaperTradingCSVExporter(unittest.TestCase):

    def setUp(self):
        self.order = SimulatedOrder(
            order_id="order-1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            signal_time="2023-01-01 10:00:00",
            created_at="2023-01-01 10:05:00",
            strategy="mean|reversion,with,commas"
        )
        self.fill = SimulatedFill(
            order_id="order-1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            price=100.5,
            filled_at="2023-01-01 10:10:00",
            fee=143.0,
            tax=0.0,
            slippage=50.0
        )
        self.result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=1000000.0,
            final_cash=899307.0,
            final_position_quantity=1000,
            average_cost=100.5,
            realized_pnl=0.0,
            unrealized_pnl=5000.0,
            total_equity=1004307.0,
            order_count=1,
            fill_count=1,
            open_position_count=1,
            orders=(self.order,),
            fills=(self.fill,),
        )

    def test_export_simulated_paper_trading_csv_bundle(self):
        from tw_stock_tool.paper_trading.exporters import export_simulated_paper_trading_csv_bundle
        import csv
        import io

        output = export_simulated_paper_trading_csv_bundle(self.result)

        self.assertIsInstance(output, dict)
        self.assertEqual(set(output.keys()), {"summary", "orders", "fills", "rejections"})

        for v in output.values():
            self.assertIsInstance(v, str)

        summary_csv = output["summary"]
        orders_csv = output["orders"]
        fills_csv = output["fills"]

        # Parse summary
        summary_reader = list(csv.reader(io.StringIO(summary_csv)))
        self.assertEqual(summary_reader[0], ["metric", "value"])
        # Check specific rows
        summary_dict = {row[0]: row[1] for row in summary_reader[1:]}
        self.assertEqual(summary_dict["symbol"], "2330")
        self.assertEqual(summary_dict["initial_cash"], "1000000.0")
        self.assertEqual(summary_dict["total_return"], "4307.0")
        self.assertEqual(summary_dict["total_return_pct"], "0.004307") # no % sign

        # Parse orders
        orders_reader = list(csv.reader(io.StringIO(orders_csv)))
        self.assertEqual(orders_reader[0], ["order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy"])
        self.assertEqual(len(orders_reader), 2)
        self.assertEqual(orders_reader[1], ["order-1", "2330", "BUY", "1000", "2023-01-01 10:00:00", "2023-01-01 10:05:00", "mean|reversion,with,commas"])

        # Parse fills
        fills_reader = list(csv.reader(io.StringIO(fills_csv)))
        self.assertEqual(fills_reader[0], ["order_id", "symbol", "side", "quantity", "price", "filled_at", "fee", "tax", "slippage", "gross_amount", "net_cash_effect"])
        self.assertEqual(len(fills_reader), 2)
        self.assertEqual(fills_reader[1], ["order-1", "2330", "BUY", "1000", "100.5", "2023-01-01 10:10:00", "143.0", "0.0", "50.0", "100500.0", "-100693.0"])

        forbidden_words = [
            "recommended", "recommendation", "buy recommendation", "sell recommendation",
            "hold recommendation", "profitable", "bad trade", "safe", "guaranteed"
        ]
        for v in output.values():
            lower_val = v.lower()
            for word in forbidden_words:
                self.assertNotIn(word, lower_val)

    def test_empty_orders_and_fills_csv(self):
        from tw_stock_tool.paper_trading.exporters import export_simulated_paper_trading_csv_bundle
        import csv
        import io

        empty_result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=1000000.0,
            final_cash=1000000.0,
            final_position_quantity=0,
            average_cost=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            total_equity=1000000.0,
            order_count=0,
            fill_count=0,
            open_position_count=0,
            orders=(),
            fills=(),
        )

        output = export_simulated_paper_trading_csv_bundle(empty_result)

        orders_reader = list(csv.reader(io.StringIO(output["orders"])))
        self.assertEqual(len(orders_reader), 1)
        self.assertEqual(orders_reader[0], ["order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy"])

        fills_reader = list(csv.reader(io.StringIO(output["fills"])))
        self.assertEqual(len(fills_reader), 1)
        self.assertEqual(fills_reader[0], ["order_id", "symbol", "side", "quantity", "price", "filled_at", "fee", "tax", "slippage", "gross_amount", "net_cash_effect"])

        summary_reader = list(csv.reader(io.StringIO(output["summary"])))
        summary_dict = {row[0]: row[1] for row in summary_reader[1:]}
        self.assertEqual(summary_dict["symbol"], "2330")
        self.assertEqual(summary_dict["total_return"], "0.0")
        self.assertEqual(summary_dict["total_return_pct"], "0.0")

if __name__ == "__main__":
    unittest.main()

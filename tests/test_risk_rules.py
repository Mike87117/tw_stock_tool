import unittest
from tw_stock_tool.risk import RiskDecision, RiskModelError, RiskInputSnapshot, check_max_order_notional

class TestRiskRules(unittest.TestCase):
    def setUp(self):
        self.snapshot = RiskInputSnapshot(
            symbol="2330",
            side="BUY",
            quantity=1000,
            price=100.0,
            cash=1000000.0
        )
        # order_notional = 100000.0

    def test_max_order_notional_allowed_below(self):
        decision = check_max_order_notional(self.snapshot, 200000.0)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.metadata["symbol"], "2330")
        self.assertEqual(decision.metadata["side"], "BUY")
        self.assertEqual(decision.metadata["order_notional"], 100000.0)
        self.assertEqual(decision.metadata["max_order_notional"], 200000.0)

    def test_max_order_notional_allowed_equal(self):
        decision = check_max_order_notional(self.snapshot, 100000.0)
        self.assertTrue(decision.allowed)

    def test_max_order_notional_rejected_exceeds(self):
        decision = check_max_order_notional(self.snapshot, 50000.0)
        self.assertTrue(decision.is_rejected)
        self.assertIn("order_notional exceeds max_order_notional", decision.reasons)
        self.assertEqual(decision.metadata["order_notional"], 100000.0)
        self.assertEqual(decision.metadata["max_order_notional"], 50000.0)

    def test_invalid_snapshot_raises(self):
        with self.assertRaises(RiskModelError):
            check_max_order_notional("not a snapshot", 100000.0) # type: ignore

    def test_zero_limit_raises(self):
        with self.assertRaises(RiskModelError):
            check_max_order_notional(self.snapshot, 0.0)

    def test_negative_limit_raises(self):
        with self.assertRaises(RiskModelError):
            check_max_order_notional(self.snapshot, -100.0)

    def test_bool_limit_raises(self):
        with self.assertRaises(RiskModelError):
            check_max_order_notional(self.snapshot, True) # type: ignore

    def test_non_number_limit_raises(self):
        with self.assertRaises(RiskModelError):
            check_max_order_notional(self.snapshot, "1000") # type: ignore

    def test_public_import(self):
        from tw_stock_tool.risk import check_max_order_notional as cmon
        self.assertEqual(cmon, check_max_order_notional)

    def test_max_position_quantity_allowed_below(self):
        snapshot = RiskInputSnapshot("2330", "BUY", 1000, 100.0, 100000.0, 1000) # projected = 2000
        from tw_stock_tool.risk.rules import check_max_position_quantity
        decision = check_max_position_quantity(snapshot, 3000)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.metadata["symbol"], "2330")
        self.assertEqual(decision.metadata["side"], "BUY")
        self.assertEqual(decision.metadata["quantity"], 1000)
        self.assertEqual(decision.metadata["current_position_quantity"], 1000)
        self.assertEqual(decision.metadata["projected_position_quantity"], 2000)
        self.assertEqual(decision.metadata["max_position_quantity"], 3000)

    def test_max_position_quantity_allowed_equal(self):
        snapshot = RiskInputSnapshot("2330", "BUY", 1000, 100.0, 100000.0, 1000) # projected = 2000
        from tw_stock_tool.risk.rules import check_max_position_quantity
        decision = check_max_position_quantity(snapshot, 2000)
        self.assertTrue(decision.allowed)

    def test_max_position_quantity_rejected_exceeds(self):
        snapshot = RiskInputSnapshot("2330", "BUY", 1000, 100.0, 100000.0, 1000) # projected = 2000
        from tw_stock_tool.risk.rules import check_max_position_quantity
        decision = check_max_position_quantity(snapshot, 1500)
        self.assertTrue(decision.is_rejected)
        self.assertIn("projected_position_quantity exceeds max_position_quantity", decision.reasons)
        self.assertEqual(decision.metadata["projected_position_quantity"], 2000)
        self.assertEqual(decision.metadata["max_position_quantity"], 1500)

    def test_max_position_quantity_sell_allowed(self):
        snapshot = RiskInputSnapshot("2330", "SELL", 1000, 100.0, 100000.0, 1000) # projected = 0
        from tw_stock_tool.risk.rules import check_max_position_quantity
        decision = check_max_position_quantity(snapshot, 2000)
        self.assertTrue(decision.allowed)

    def test_max_position_quantity_invalid_snapshot(self):
        from tw_stock_tool.risk.rules import check_max_position_quantity
        with self.assertRaises(RiskModelError):
            check_max_position_quantity("not a snapshot", 1000) # type: ignore

    def test_max_position_quantity_zero_limit(self):
        from tw_stock_tool.risk.rules import check_max_position_quantity
        with self.assertRaises(RiskModelError):
            check_max_position_quantity(self.snapshot, 0)

    def test_max_position_quantity_negative_limit(self):
        from tw_stock_tool.risk.rules import check_max_position_quantity
        with self.assertRaises(RiskModelError):
            check_max_position_quantity(self.snapshot, -100)

    def test_max_position_quantity_bool_limit(self):
        from tw_stock_tool.risk.rules import check_max_position_quantity
        with self.assertRaises(RiskModelError):
            check_max_position_quantity(self.snapshot, True) # type: ignore

    def test_max_position_quantity_non_int_limit(self):
        from tw_stock_tool.risk.rules import check_max_position_quantity
        with self.assertRaises(RiskModelError):
            check_max_position_quantity(self.snapshot, 1000.0) # type: ignore

    def test_max_position_quantity_public_import(self):
        from tw_stock_tool.risk import check_max_position_quantity as cmpq
        from tw_stock_tool.risk.rules import check_max_position_quantity
        self.assertEqual(cmpq, check_max_position_quantity)

if __name__ == "__main__":
    unittest.main()

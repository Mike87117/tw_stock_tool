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

if __name__ == "__main__":
    unittest.main()

import unittest
from tw_stock_tool.risk import RiskDecision, RiskModelError

class TestRiskModels(unittest.TestCase):
    def test_allow_default(self):
        decision = RiskDecision.allow()
        self.assertTrue(decision.allowed)
        self.assertFalse(decision.is_rejected)
        self.assertEqual(decision.reasons, ())
        self.assertEqual(decision.metadata, {})

    def test_reject_with_reasons(self):
        decision = RiskDecision.reject(reasons=["Too risky", "Exceeds max exposure"])
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.is_rejected)
        self.assertEqual(decision.reasons, ("Too risky", "Exceeds max exposure"))

    def test_reject_empty_reasons_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision.reject(reasons=[])

    def test_non_bool_allowed_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision(allowed="True") # type: ignore

    def test_non_string_reason_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision.reject(reasons=[123]) # type: ignore

    def test_blank_reason_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision.reject(reasons=["   "])
            
    def test_empty_string_reason_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision.reject(reasons=[""])

    def test_non_dict_metadata_raises(self):
        with self.assertRaises(RiskModelError):
            RiskDecision.allow(metadata=["not a dict"]) # type: ignore

    def test_public_import_works(self):
        from tw_stock_tool.risk import RiskDecision as RD, RiskModelError as RME
        self.assertEqual(RD, RiskDecision)
        self.assertEqual(RME, RiskModelError)

    def test_normalize_list_reasons(self):
        decision = RiskDecision.allow(reasons=["ok reason"])
        self.assertIsInstance(decision.reasons, tuple)
        self.assertEqual(decision.reasons, ("ok reason",))

if __name__ == "__main__":
    unittest.main()

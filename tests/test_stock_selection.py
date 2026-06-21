import unittest

from stock_selection import apply_stock_selection


class StockSelectionTest(unittest.TestCase):
    def test_stock_limit_takes_first_n(self) -> None:
        result = apply_stock_selection(["2330", "2317", "2454"], stock_limit=2)

        self.assertEqual(result, ["2330", "2317"])

    def test_stock_sample_takes_n(self) -> None:
        result = apply_stock_selection(["2330", "2317", "2454", "2308"], stock_sample=2)

        self.assertEqual(len(result), 2)
        self.assertTrue(set(result).issubset({"2330", "2317", "2454", "2308"}))

    def test_random_state_makes_sample_reproducible(self) -> None:
        stocks = ["2330", "2317", "2454", "2308", "2882"]

        first = apply_stock_selection(stocks, stock_sample=3, random_state=7)
        second = apply_stock_selection(stocks, stock_sample=3, random_state=7)

        self.assertEqual(first, second)

    def test_limit_and_sample_together_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "either --stock-limit or --stock-sample"):
            apply_stock_selection(["2330"], stock_limit=1, stock_sample=1)

    def test_limit_less_than_or_equal_zero_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "--stock-limit"):
            apply_stock_selection(["2330"], stock_limit=0)

    def test_sample_less_than_or_equal_zero_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "--stock-sample"):
            apply_stock_selection(["2330"], stock_sample=0)


if __name__ == "__main__":
    unittest.main()

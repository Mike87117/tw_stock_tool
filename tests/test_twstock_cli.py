from contextlib import redirect_stderr
from io import StringIO
import sys
import unittest
from unittest.mock import patch

import twstock_cli


class TwStockCliTest(unittest.TestCase):
    def test_doctor_subcommand_dispatches_to_doctor_main(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.doctor, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["doctor", "--live"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["doctor.py", "--live"])

    def test_stock_list_update_dispatches_to_updater_main(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.stock_list_updater, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["stock-list", "update", "--market", "all", "--output", "stocks.txt"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["stock_list_updater.py", "--market", "all", "--output", "stocks.txt"])

    def test_stock_list_smoke_check_dispatches_to_smoke_main(self) -> None:
        with patch.object(twstock_cli.stock_list_smoke_check, "main") as mocked:
            twstock_cli.main(["stock-list", "smoke-check"])

        mocked.assert_called_once_with()

    def test_price_smoke_check_dispatches_to_price_main(self) -> None:
        with patch.object(twstock_cli.price_data_smoke_check, "main") as mocked:
            twstock_cli.main(["price-smoke-check"])

        mocked.assert_called_once_with()

    def test_scan_subcommand_dispatches_to_scan_stocks(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.scan_stocks, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["scan", "--auto-stock-list", "--stock-limit", "50"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["scan_stocks.py", "--auto-stock-list", "--stock-limit", "50"])

    def test_daily_subcommand_dispatches_to_daily_report(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.daily_report_cli, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["daily", "--auto-stock-list", "--stock-limit", "50", "--output-md"])

        mocked.assert_called_once_with()
        self.assertEqual(
            captured[0],
            ["daily_report_cli.py", "--auto-stock-list", "--stock-limit", "50", "--output-md"],
        )

    def test_ai_scan_subcommand_dispatches_to_ai_stock_scanner(self) -> None:
        captured: list[list[str]] = []

        def fake_main() -> None:
            captured.append(sys.argv[:])

        with patch.object(twstock_cli.ai_stock_scanner, "main", side_effect=fake_main) as mocked:
            twstock_cli.main(["ai-scan", "--auto-stock-list", "--stock-limit", "20"])

        mocked.assert_called_once_with()
        self.assertEqual(captured[0], ["ai_stock_scanner.py", "--auto-stock-list", "--stock-limit", "20"])

    def test_unknown_subcommand_shows_error(self) -> None:
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["unknown"])

        self.assertNotEqual(ctx.exception.code, 0)

    def test_top_level_help_exits_successfully(self) -> None:
        from contextlib import redirect_stdout

        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["--help"])

        self.assertEqual(ctx.exception.code, 0)
        output = out.getvalue()
        self.assertIn("usage:", output)
        self.assertIn("doctor", output)
        self.assertIn("scan", output)
        self.assertIn("daily", output)
        self.assertIn("stock-list", output)
        self.assertIn("price-smoke-check", output)
        self.assertIn("ai-scan", output)

    def test_stock_list_help_exits_successfully(self) -> None:
        from contextlib import redirect_stdout

        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["stock-list", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        output = out.getvalue()
        self.assertIn("usage:", output)
        self.assertIn("update", output)
        self.assertIn("smoke-check", output)

    def test_stock_list_update_help_exits_successfully(self) -> None:
        from contextlib import redirect_stdout

        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["stock-list", "update", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())

    def test_stock_list_smoke_check_help_exits_successfully(self) -> None:
        from contextlib import redirect_stdout

        out = StringIO()
        with redirect_stdout(out):
            with self.assertRaises(SystemExit) as ctx:
                twstock_cli.main(["stock-list", "smoke-check", "--help"])

        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("usage:", out.getvalue())


if __name__ == "__main__":
    unittest.main()

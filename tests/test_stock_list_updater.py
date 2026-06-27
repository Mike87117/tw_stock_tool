import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

import stock_list_updater


class StockListUpdaterTest(unittest.TestCase):
    def _mock_response(self, payload: list[dict[str, object]]) -> Mock:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = payload
        return response

    def test_twse_official_chinese_field_parsing(self) -> None:
        payload = [
            {"公司代號": "2330", "公司名稱": "TSMC", "產業別": "24"},
            {"公司代號": "1101", "公司名稱": "TCC", "產業別": "01"},
        ]
        with patch.object(stock_list_updater.requests, "get", return_value=self._mock_response(payload)):
            result = stock_list_updater.fetch_twse_stock_list()

        self.assertEqual(result["Stock"].tolist(), ["2330", "1101"])
        self.assertEqual(result["Name"].tolist(), ["TSMC", "TCC"])
        self.assertEqual(result["Market"].tolist(), ["TWSE", "TWSE"])

    def test_tpex_official_field_parsing(self) -> None:
        payload = [
            {"SecuritiesCompanyCode": "8069", "CompanyName": "E Ink", "SecuritiesIndustryCode": "26"},
            {"SecuritiesCompanyCode": "8299", "CompanyName": "Phison", "SecuritiesIndustryCode": "24"},
        ]
        with patch.object(stock_list_updater.requests, "get", return_value=self._mock_response(payload)):
            result = stock_list_updater.fetch_tpex_stock_list()

        self.assertEqual(result["Stock"].tolist(), ["8069", "8299"])
        self.assertEqual(result["Name"].tolist(), ["E Ink", "Phison"])
        self.assertEqual(result["Market"].tolist(), ["TPEX", "TPEX"])

    def test_english_fallback_parsing(self) -> None:
        payload = [
            {"Code": "2330", "Name": "TSMC", "Type": "semiconductor"},
            {"stock_id": "1101", "name": "TCC", "security_type": "cement"},
        ]
        frame = stock_list_updater._records_to_frame(payload, market="twse")

        self.assertEqual(frame["Stock"].tolist(), ["2330", "1101"])
        self.assertEqual(frame["Name"].tolist(), ["TSMC", "TCC"])

    def test_missing_stock_code_field_raises(self) -> None:
        payload = [{"Unknown": "2330", "CompanyName": "TSMC"}]

        with self.assertRaisesRegex(stock_list_updater.StockListUpdaterError, "Cannot find stock code field"):
            stock_list_updater._records_to_frame(payload, market="twse")

    def test_all_merges_and_deduplicates(self) -> None:
        twse = pd.DataFrame(
            [
                {"Stock": "2330", "Name": "TSMC", "Market": "TWSE", "Type": "stock"},
                {"Stock": "1101", "Name": "TCC", "Market": "TWSE", "Type": "stock"},
            ]
        )
        tpex = pd.DataFrame(
            [
                {"Stock": "2330", "Name": "duplicate", "Market": "TPEX", "Type": "stock"},
                {"Stock": "8069", "Name": "E Ink", "Market": "TPEX", "Type": "stock"},
            ]
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "stocks.txt"
            with patch.object(stock_list_updater, "fetch_twse_stock_list", return_value=twse):
                with patch.object(stock_list_updater, "fetch_tpex_stock_list", return_value=tpex):
                    result, path = stock_list_updater.update_stock_list(
                        "all",
                        output,
                        min_common_stocks=1,
                    )

        self.assertEqual(result["Stock"].tolist(), ["1101", "2330", "8069"])
        self.assertEqual(path, output)

    def test_filter_excludes_etf_warrants_and_non_stock_codes(self) -> None:
        data = pd.DataFrame(
            [
                {"Stock": "2330", "Name": "TSMC", "Market": "TWSE", "Type": "stock"},
                {"Stock": "0050", "Name": "ETF product", "Market": "TWSE", "Type": "ETF"},
                {"Stock": "12345", "Name": "bad", "Market": "TWSE", "Type": "stock"},
                {"Stock": "0301", "Name": "call warrant", "Market": "TWSE", "Type": "WARRANT"},
                {"Stock": "ABCD", "Name": "bad", "Market": "TWSE", "Type": "stock"},
            ]
        )

        result = stock_list_updater.normalize_stock_list(data)

        self.assertEqual(result["Stock"].tolist(), ["2330"])

    def test_abnormally_few_common_stocks_raises(self) -> None:
        twse = pd.DataFrame([{"Stock": "2330", "Name": "TSMC", "Market": "TWSE", "Type": "stock"}])
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "stocks.txt"
            with patch.object(stock_list_updater, "fetch_twse_stock_list", return_value=twse):
                with self.assertRaisesRegex(stock_list_updater.StockListUpdaterError, "Abnormally few"):
                    stock_list_updater.update_stock_list("twse", output, min_common_stocks=100)
            self.assertFalse(output.exists())

    def test_write_stock_list_outputs_txt(self) -> None:
        data = pd.DataFrame([{"Stock": "1101"}, {"Stock": "2330"}])
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "stocks.txt"
            path = stock_list_updater.write_stock_list(data, output)
            content = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(content, ["1101", "2330"])

    def test_write_stock_list_outputs_txt_with_suffix(self) -> None:
        data = pd.DataFrame([
            {"Stock": "1101", "Market": "TWSE"},
            {"Stock": "2330", "Market": "TPEX"}
        ])
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "stocks.txt"
            path = stock_list_updater.write_stock_list(data, output, add_suffix=True)
            content = path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(content, ["1101.TW", "2330.TWO"])

    def test_update_stock_list_writes_normal_mock_output(self) -> None:
        twse = pd.DataFrame([{"Stock": "2330", "Name": "TSMC", "Market": "TWSE", "Type": "stock"}])
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "stocks.txt"
            with patch.object(stock_list_updater, "fetch_twse_stock_list", return_value=twse):
                result, path = stock_list_updater.update_stock_list(
                    "twse",
                    output,
                    min_common_stocks=1,
                )

            self.assertEqual(result["Stock"].tolist(), ["2330"])
            self.assertEqual(path.read_text(encoding="utf-8").splitlines(), ["2330"])

    def test_invalid_market_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            stock_list_updater.update_stock_list("bad", "stocks.txt")

    def test_all_failure_does_not_write_partial_without_allow_partial(self) -> None:
        twse = pd.DataFrame([{"Stock": "2330", "Name": "TSMC", "Market": "TWSE", "Type": "stock"}])
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "stocks.txt"
            with patch.object(stock_list_updater, "fetch_twse_stock_list", return_value=twse):
                with patch.object(stock_list_updater, "fetch_tpex_stock_list", side_effect=RuntimeError("down")):
                    with self.assertRaises(stock_list_updater.StockListUpdaterError):
                        stock_list_updater.update_stock_list(
                            "all",
                            output,
                            min_common_stocks=1,
                        )
            self.assertFalse(output.exists())

    def test_partial_failure_logs_warning_with_allow_partial(self) -> None:
        twse = pd.DataFrame([{"Stock": "2330", "Name": "TSMC", "Market": "TWSE", "Type": "stock"}])
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "stocks.txt"
            with patch.object(stock_list_updater, "fetch_twse_stock_list", return_value=twse):
                with patch.object(stock_list_updater, "fetch_tpex_stock_list", side_effect=RuntimeError("down")):
                    with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                        result, path = stock_list_updater.update_stock_list(
                            "all",
                            output,
                            allow_partial=True,
                            min_common_stocks=1,
                        )

            self.assertEqual(result["Stock"].tolist(), ["2330"])
            self.assertIn("Warning: Partial stock list update. Errors: TPEX: down", mock_stderr.getvalue())
            self.assertTrue(output.exists())

    def test_parse_args(self) -> None:
        args = stock_list_updater._parse_args(
            ["--market", "all", "--output", "stocks.txt", "--allow-partial"]
        )

        self.assertEqual(args.market, "all")
        self.assertEqual(args.output, "stocks.txt")
        self.assertTrue(args.allow_partial)
        self.assertFalse(args.add_suffix)

    def test_parse_args_with_add_suffix(self) -> None:
        args = stock_list_updater._parse_args(["--add-suffix"])
        self.assertTrue(args.add_suffix)


if __name__ == "__main__":
    unittest.main()

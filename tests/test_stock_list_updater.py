import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from tw_stock_tool.data import stock_list_updater


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

    def test_main_success_output_has_no_banned_data_freshness_wording(self) -> None:
        import sys
        df = pd.DataFrame({"Stock": ["2330"], "Name": ["台積電"], "Market": ["TWSE"], "Type": ["股票"]})
        path = Path("stocks.txt")

        with patch.object(sys, "argv", ["stock_list_updater.py", "--market", "twse", "--output", "stocks.txt"]):
            with patch.object(stock_list_updater, "update_stock_list", return_value=(df, path)):
                with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
                    stock_list_updater.main()

        output = mock_stdout.getvalue().lower()
        self.assertIn("stock list updated:", output)
        self.assertIn("stocks: 1", output)
        banned_phrases = (
            "guaranteed latest data",
            "guaranteed complete",
            "guaranteed accurate",
            "always latest",
            "real-time guaranteed",
            "refresh always succeeds",
            "fallback data is current",
            "official stock list is complete",
            "investment-grade data",
            "safe to invest",
            "best stocks to buy",
            "investment recommendation",
            "recommended stocks",
            "guaranteed profit",
            "guaranteed return",
        )
        for phrase in banned_phrases:
            self.assertNotIn(phrase, output)

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

            banned_phrases = (
                "guaranteed latest data",
                "guaranteed complete",
                "guaranteed accurate",
                "always latest",
                "real-time guaranteed",
                "refresh always succeeds",
                "fallback data is current",
                "official stock list is complete",
                "investment-grade data",
                "safe to invest",
                "best stocks to buy",
                "investment recommendation",
                "recommended stocks",
                "guaranteed profit",
                "guaranteed return",
            )
            err_str = mock_stderr.getvalue().lower()
            for phrase in banned_phrases:
                self.assertNotIn(phrase, err_str)

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

    @staticmethod
    def _catalog(*rows: tuple[str, str, str, str]) -> pd.DataFrame:
        return pd.DataFrame(rows, columns=["Stock", "Name", "Market", "Type"])

    def test_read_only_catalog_does_not_write_or_create_directories(self) -> None:
        twse = self._catalog(("2330", "TSMC", "TWSE", "stock"))
        with patch.object(stock_list_updater, "fetch_twse_stock_list", return_value=twse):
            with patch.object(stock_list_updater, "write_stock_list") as write:
                with patch.object(Path, "mkdir") as mkdir, patch.object(Path, "write_text") as write_text:
                    result = stock_list_updater.load_stock_market_catalog("twse", min_common_stocks=1)
        self.assertEqual(result["Stock"].tolist(), ["2330"])
        write.assert_not_called()
        mkdir.assert_not_called()
        write_text.assert_not_called()

    def test_catalog_market_selection_and_cross_market_duplicates(self) -> None:
        twse = self._catalog(("2330", "TSMC", "TWSE", "stock"), ("1101", "TCC", "TWSE", "stock"))
        tpex = self._catalog(("2330", "duplicate", "TPEX", "stock"), ("8069", "E Ink", "TPEX", "stock"))
        with patch.object(stock_list_updater, "fetch_twse_stock_list", return_value=twse) as twse_fetch:
            with patch.object(stock_list_updater, "fetch_tpex_stock_list", return_value=tpex) as tpex_fetch:
                all_catalog = stock_list_updater.load_stock_market_catalog("all", min_common_stocks=1)
                twse_catalog = stock_list_updater.load_stock_market_catalog("twse", min_common_stocks=1)
                tpex_catalog = stock_list_updater.load_stock_market_catalog("tpex", min_common_stocks=1)
        self.assertEqual(all_catalog.columns.tolist(), ["Stock", "Name", "Market", "Type"])
        self.assertEqual(all_catalog["Stock"].tolist(), ["1101", "2330", "2330", "8069"])
        self.assertEqual(all_catalog["Market"].tolist(), ["TWSE", "TWSE", "TPEX", "TPEX"])
        self.assertEqual(twse_catalog["Market"].unique().tolist(), ["TWSE"])
        self.assertEqual(tpex_catalog["Market"].unique().tolist(), ["TPEX"])
        self.assertGreaterEqual(twse_fetch.call_count, 2)
        self.assertGreaterEqual(tpex_fetch.call_count, 2)

    def test_catalog_order_is_deterministic_and_input_is_not_mutated(self) -> None:
        source = self._catalog(
            ("2330", "tpex", "tpex", "stock"),
            ("1101", "tcc", "TWSE", "stock"),
            ("2330", "twse-first", "TWSE", "stock"),
            ("2330", "twse-second", "TWSE", "stock"),
        )
        original = source.copy(deep=True)
        result = stock_list_updater.normalize_stock_catalog(source)
        self.assertEqual(result["Stock"].tolist(), ["1101", "2330", "2330", "2330"])
        self.assertEqual(result["Market"].tolist(), ["TWSE", "TWSE", "TWSE", "TPEX"])
        self.assertEqual(result["Name"].tolist(), ["tcc", "twse-first", "twse-second", "tpex"])
        pd.testing.assert_frame_equal(source, original)

    def test_catalog_partial_and_all_source_failures(self) -> None:
        twse = self._catalog(("2330", "TSMC", "TWSE", "stock"))
        with patch.object(stock_list_updater, "fetch_twse_stock_list", return_value=twse):
            with patch.object(stock_list_updater, "fetch_tpex_stock_list", side_effect=RuntimeError("down")):
                with patch("sys.stderr", new_callable=io.StringIO) as stderr:
                    result = stock_list_updater.load_stock_market_catalog("all", allow_partial=True, min_common_stocks=1)
                self.assertIn("Warning: Partial stock list update. Errors: TPEX: down", stderr.getvalue())
        self.assertEqual(result["Market"].tolist(), ["TWSE"])

        with patch.object(stock_list_updater, "fetch_twse_stock_list", side_effect=RuntimeError("twse down")):
            with patch.object(stock_list_updater, "fetch_tpex_stock_list", side_effect=RuntimeError("tpex down")):
                with self.assertRaisesRegex(stock_list_updater.StockListUpdaterError, "Failed to update stock list"):
                    stock_list_updater.load_stock_market_catalog("all", allow_partial=True, min_common_stocks=1)

    def test_catalog_minimum_validation_counts_market_rows(self) -> None:
        twse = self._catalog(("2330", "TSMC", "TWSE", "stock"))
        tpex = self._catalog(("2330", "duplicate", "TPEX", "stock"))
        with patch.object(stock_list_updater, "fetch_twse_stock_list", return_value=twse):
            with patch.object(stock_list_updater, "fetch_tpex_stock_list", return_value=tpex):
                result = stock_list_updater.load_stock_market_catalog("all", min_common_stocks=2)
                self.assertEqual(len(result), 2)
                with self.assertRaisesRegex(stock_list_updater.StockListUpdaterError, "Abnormally few"):
                    stock_list_updater.load_stock_market_catalog("all", min_common_stocks=3)

    def test_normalize_stock_catalog_rejects_malformed_structures(self) -> None:
        with self.assertRaisesRegex(stock_list_updater.StockListUpdaterError, "pandas DataFrame"):
            stock_list_updater.normalize_stock_catalog([])  # type: ignore[arg-type]
        with self.assertRaisesRegex(stock_list_updater.StockListUpdaterError, "missing required"):
            stock_list_updater.normalize_stock_catalog(pd.DataFrame({"Stock": ["2330"]}))

    def test_preloaded_catalog_reuses_zero_sources_and_filters_markets(self) -> None:
        catalog = self._catalog(
            ("2330", "TSMC", "TWSE", "stock"),
            ("2330", "duplicate", "TPEX", "stock"),
            ("8069", "E Ink", "TPEX", "stock"),
        )
        original = catalog.copy(deep=True)
        for market, expected, suffix, expected_lines in (
            ("twse", ["2330"], False, ["2330"]),
            ("tpex", ["2330", "8069"], True, ["2330.TWO", "8069.TWO"]),
            ("all", ["2330", "8069"], True, ["2330.TW", "8069.TWO"]),
        ):
            with self.subTest(market=market):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    output = Path(tmp_dir) / "stocks.txt"
                    with patch.object(stock_list_updater, "fetch_twse_stock_list") as twse_fetch:
                        with patch.object(stock_list_updater, "fetch_tpex_stock_list") as tpex_fetch:
                            result, path = stock_list_updater.update_stock_list(
                                market,
                                output,
                                min_common_stocks=1,
                                add_suffix=suffix,
                                _preloaded_catalog=catalog,
                            )
                    twse_fetch.assert_not_called()
                    tpex_fetch.assert_not_called()
                    output_lines = path.read_text(encoding="utf-8").splitlines()
                self.assertEqual(result["Stock"].tolist(), expected)
                self.assertEqual(output_lines, expected_lines)
        pd.testing.assert_frame_equal(catalog, original)

    def test_preloaded_catalog_validates_final_output_and_writes_once(self) -> None:
        catalog = self._catalog(("2330", "TSMC", "TWSE", "stock"))
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "stocks.txt"
            with patch.object(stock_list_updater, "write_stock_list", wraps=stock_list_updater.write_stock_list) as write:
                stock_list_updater.update_stock_list(
                    "twse",
                    output,
                    min_common_stocks=1,
                    _preloaded_catalog=catalog,
                )
            write.assert_called_once()
            with self.assertRaisesRegex(stock_list_updater.StockListUpdaterError, "Abnormally few"):
                stock_list_updater.update_stock_list(
                    "twse",
                    Path(tmp_dir) / "too-small.txt",
                    min_common_stocks=2,
                    _preloaded_catalog=catalog,
                )


if __name__ == "__main__":
    unittest.main()

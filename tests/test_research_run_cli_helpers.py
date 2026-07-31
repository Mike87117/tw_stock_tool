from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from tw_stock_tool.application.research_run import SymbolRequest
from tw_stock_tool.application.symbol_resolution import SymbolResolutionError
from tw_stock_tool.cli import _research_run_cli as helper
from tw_stock_tool.research_run.models import ArtifactReference


def _catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Stock": "2330", "Name": "TSMC", "Market": "TWSE", "Type": "普通股"},
            {"Stock": "6488", "Name": "TPEX", "Market": "TPEX", "Type": "普通股"},
            {"Stock": "9999", "Name": "Dual", "Market": "TWSE", "Type": "普通股"},
            {"Stock": "9999", "Name": "Dual", "Market": "TPEX", "Type": "普通股"},
        ]
    )


class ResearchRunCliHelperTests(unittest.TestCase):
    def test_manual_file_values_precede_stocks_and_normalize(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "stocks.txt"
            file_path.write_text("2317\n2330\n2317\n", encoding="utf-8")
            with patch.object(helper, "resolve_symbol_requests", wraps=helper.resolve_symbol_requests) as resolve:
                resolve.return_value = tuple(
                    SymbolRequest(value, f"{value}.TW")
                    for value in ("2317", "2330", "2454")
                )
                result = helper.collect_symbol_requests(
                    stocks=["2454", "2317"],
                    file_path=str(file_path),
                    auto_stock_list=False,
                    stock_market="twse",
                    stock_list_output="stocks.txt",
                    allow_partial_stock_list=False,
                    stock_limit=None,
                    stock_sample=None,
                    random_state=42,
                )
        self.assertEqual([item.requested_symbol for item in result], ["2317", "2330", "2454"])
        self.assertEqual(resolve.call_args.args[0], ("2317", "2330", "2454"))
        resolve.assert_called_once_with(
            ("2317", "2330", "2454"),
            market_hint="twse",
            catalog=None,
            allow_partial_catalog=False,
        )

    def test_scan_interactive_fallback_and_daily_no_input_error(self) -> None:
        with patch.object(helper, "resolve_symbol_requests", wraps=helper.resolve_symbol_requests) as resolve:
            resolve.return_value = (SymbolRequest("2330", "2330.TW"),)
            result = helper.collect_symbol_requests(
                stocks=None,
                file_path=None,
                auto_stock_list=False,
                stock_market="twse",
                stock_list_output="stocks.txt",
                allow_partial_stock_list=False,
                stock_limit=None,
                stock_sample=None,
                random_state=42,
                interactive_supplier=lambda: ["2330"],
            )
        self.assertEqual(result[0].requested_symbol, "2330")
        with self.assertRaisesRegex(ValueError, "No stock ids provided"):
            helper.collect_symbol_requests(
                stocks=None,
                file_path=None,
                auto_stock_list=False,
                stock_market="all",
                stock_list_output="stocks.txt",
                allow_partial_stock_list=False,
                stock_limit=None,
                stock_sample=None,
                random_state=42,
            )

    def test_selection_happens_before_resolution_with_deterministic_sample(self) -> None:
        with patch.object(helper, "resolve_symbol_requests", wraps=helper.resolve_symbol_requests) as resolve:
            resolve.return_value = ()
            kwargs = dict(
                stocks=["2330", "2317", "2454", "2308"],
                file_path=None,
                auto_stock_list=False,
                stock_market="twse",
                stock_list_output="stocks.txt",
                allow_partial_stock_list=False,
                stock_limit=None,
                stock_sample=2,
                random_state=7,
            )
            helper.collect_symbol_requests(**kwargs)
            first = resolve.call_args.args[0]
            resolve.reset_mock()
            helper.collect_symbol_requests(**kwargs)
            second = resolve.call_args.args[0]
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)

    def test_manual_all_market_bare_batch_loads_one_catalog(self) -> None:
        with patch("tw_stock_tool.application.symbol_resolution.load_stock_market_catalog", return_value=_catalog()) as load:
            with patch.object(helper, "resolve_symbol_requests", wraps=helper.resolve_symbol_requests) as resolve:
                helper.collect_symbol_requests(
                    stocks=["2330"],
                    file_path=None,
                    auto_stock_list=False,
                    stock_market="all",
                    stock_list_output="stocks.txt",
                    allow_partial_stock_list=True,
                    stock_limit=None,
                    stock_sample=None,
                    random_state=42,
                )
        load.assert_called_once_with(market="all", allow_partial=True)
        resolve.assert_called_once()
        self.assertIsNone(resolve.call_args.kwargs["catalog"])
        self.assertTrue(resolve.call_args.kwargs["allow_partial_catalog"])

    def test_auto_list_fetches_once_writes_once_and_reuses_raw_catalog(self) -> None:
        catalog = _catalog()
        output = catalog.drop_duplicates("Stock", keep="first").loc[:, ["Stock", "Name", "Market", "Type"]]
        with patch.object(helper, "load_stock_market_catalog", return_value=catalog) as load:
            with patch.object(helper, "update_stock_list", return_value=(output, Path("stocks.txt"))) as update:
                with patch.object(helper, "resolve_symbol_requests", wraps=helper.resolve_symbol_requests) as resolve:
                    helper.collect_symbol_requests(
                        stocks=["ignored"],
                        file_path="ignored.txt",
                        auto_stock_list=True,
                        stock_market="all",
                        stock_list_output="stocks.txt",
                        allow_partial_stock_list=True,
                        stock_limit=1,
                        stock_sample=None,
                        random_state=42,
                    )
        load.assert_called_once_with(market="all", allow_partial=True)
        update.assert_called_once()
        self.assertIs(update.call_args.kwargs["_preloaded_catalog"], catalog)
        resolve.assert_called_once()
        self.assertIs(resolve.call_args.kwargs["catalog"], catalog)
        self.assertEqual(resolve.call_args.args[0], ("2330",))
        self.assertEqual(update.call_args.kwargs["output"], "stocks.txt")

    def test_explicit_suffix_and_market_hints_do_not_load_catalog(self) -> None:
        with patch.object(helper, "load_stock_market_catalog") as load:
            with patch.object(helper, "resolve_symbol_requests", wraps=helper.resolve_symbol_requests) as resolve:
                resolve.return_value = (
                    SymbolRequest("2330.TW", "2330.TW"),
                    SymbolRequest("6488", "6488.TWO"),
                )
                helper.collect_symbol_requests(
                    stocks=["2330.TW", "6488"],
                    file_path=None,
                    auto_stock_list=False,
                    stock_market="tpex",
                    stock_list_output="stocks.txt",
                    allow_partial_stock_list=False,
                    stock_limit=None,
                    stock_sample=None,
                    random_state=42,
                )
        load.assert_not_called()
        self.assertEqual(resolve.call_args.kwargs["catalog"], None)

    def test_exception_cause_lookup_is_nested_and_cycle_safe(self) -> None:
        root = RuntimeError("root")
        middle = RuntimeError("middle")
        target = ValueError("target")
        root.__cause__ = middle
        middle.__cause__ = target
        self.assertIs(helper.find_exception_cause(root, ValueError), target)
        cycle_a = RuntimeError("a")
        cycle_b = RuntimeError("b")
        cycle_a.__cause__ = cycle_b
        cycle_b.__cause__ = cycle_a
        self.assertIsNone(helper.find_exception_cause(cycle_a, ValueError))

    def test_artifact_lookup_is_exact_and_rejects_duplicates(self) -> None:
        artifacts = (
            ArtifactReference("daily_report_markdown", "reports/daily.md", "text/markdown", None),
            ArtifactReference("daily_report_json", "reports/daily.json", "application/json", 1),
        )
        result = SimpleNamespace(generated_artifacts=artifacts)
        self.assertEqual(helper.artifact_path(result, "daily_report_json"), "reports/daily.json")
        self.assertIsNone(helper.artifact_path(result, "missing"))
        duplicate = SimpleNamespace(generated_artifacts=artifacts + (artifacts[0],))
        with self.assertRaisesRegex(ValueError, "Duplicate generated artifact"):
            helper.artifact_path(duplicate, "daily_report_markdown")



    def test_mixed_all_market_batch_loads_once_and_preserves_order(self) -> None:
        with patch("tw_stock_tool.application.symbol_resolution.load_stock_market_catalog", return_value=_catalog()) as load:
            result = helper.collect_symbol_requests(
                stocks=["2330.TW", "6488"],
                file_path=None,
                auto_stock_list=False,
                stock_market="all",
                stock_list_output="stocks.txt",
                allow_partial_stock_list=False,
                stock_limit=None,
                stock_sample=None,
                random_state=42,
            )
        load.assert_called_once_with(market="all", allow_partial=False)
        self.assertEqual(
            [(item.requested_symbol, item.canonical_symbol) for item in result],
            [("2330.TW", "2330.TW"), ("6488", "6488.TWO")],
        )

    def test_manual_limit_is_applied_before_resolution(self) -> None:
        with patch.object(helper, "resolve_symbol_requests", return_value=()) as resolve:
            helper.collect_symbol_requests(
                stocks=["2330", "2317", "2454"],
                file_path=None,
                auto_stock_list=False,
                stock_market="twse",
                stock_list_output="stocks.txt",
                allow_partial_stock_list=False,
                stock_limit=2,
                stock_sample=None,
                random_state=42,
            )
        self.assertEqual(resolve.call_args.args[0], ("2330", "2317"))

    def test_twse_and_tpex_hints_skip_catalog_fetch(self) -> None:
        with patch("tw_stock_tool.application.symbol_resolution.load_stock_market_catalog") as load:
            for market, code, suffix in (("twse", "2330", ".TW"), ("tpex", "6488", ".TWO")):
                with self.subTest(market=market):
                    result = helper.collect_symbol_requests(
                        stocks=[code],
                        file_path=None,
                        auto_stock_list=False,
                        stock_market=market,
                        stock_list_output="stocks.txt",
                        allow_partial_stock_list=False,
                        stock_limit=None,
                        stock_sample=None,
                        random_state=42,
                    )
                    self.assertEqual(result[0].canonical_symbol, code + suffix)
        load.assert_not_called()

    def test_auto_list_selected_ambiguity_fails_and_unselected_does_not(self) -> None:
        catalog = _catalog()
        selected_duplicate = catalog[catalog["Stock"] == "9999"].drop_duplicates(
            "Stock", keep="first"
        )
        with patch.object(helper, "load_stock_market_catalog", return_value=catalog):
            with patch.object(
                helper,
                "update_stock_list",
                return_value=(selected_duplicate, Path("stocks.txt")),
            ):
                with self.assertRaises(SymbolResolutionError):
                    helper.collect_symbol_requests(
                        stocks=None,
                        file_path=None,
                        auto_stock_list=True,
                        stock_market="all",
                        stock_list_output="stocks.txt",
                        allow_partial_stock_list=False,
                        stock_limit=None,
                        stock_sample=None,
                        random_state=42,
                    )

        normalized = pd.DataFrame([{"Stock": "2330"}, {"Stock": "9999"}])
        with patch.object(helper, "load_stock_market_catalog", return_value=catalog):
            with patch.object(
                helper,
                "update_stock_list",
                return_value=(normalized, Path("stocks.txt")),
            ):
                result = helper.collect_symbol_requests(
                    stocks=None,
                    file_path=None,
                    auto_stock_list=True,
                    stock_market="all",
                    stock_list_output="stocks.txt",
                    allow_partial_stock_list=False,
                    stock_limit=1,
                    stock_sample=None,
                    random_state=42,
                )
        self.assertEqual(result[0].canonical_symbol, "2330.TW")

    def test_auto_list_does_not_mutate_raw_catalog(self) -> None:
        catalog = _catalog().loc[lambda frame: frame["Stock"] != "9999"].reset_index(drop=True)
        snapshot = catalog.copy(deep=True)
        normalized = catalog.drop_duplicates("Stock", keep="first").loc[:, ["Stock"]]
        with patch.object(helper, "load_stock_market_catalog", return_value=catalog):
            with patch.object(
                helper,
                "update_stock_list",
                return_value=(normalized, Path("stocks.txt")),
            ):
                helper.collect_symbol_requests(
                    stocks=None,
                    file_path=None,
                    auto_stock_list=True,
                    stock_market="all",
                    stock_list_output="stocks.txt",
                    allow_partial_stock_list=False,
                    stock_limit=None,
                    stock_sample=None,
                    random_state=42,
                )
        pd.testing.assert_frame_equal(catalog, snapshot)
if __name__ == "__main__":
    unittest.main()

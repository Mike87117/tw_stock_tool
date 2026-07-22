import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tw_stock_tool.cli import daily_report_artifact_cli
from tw_stock_tool.reports.daily_report import build_daily_report_data
from tw_stock_tool.reports.daily_report_serialization import (
    DailyReportSerializationError,
    export_daily_report_json,
)
from tw_stock_tool.reports.daily_report_serialization_files import export_daily_report_json_file


def _report():
    return build_daily_report_data(
        report_date="2026-07-22",
        stock_universe=["2330", "2317"],
        screening_results=[{"Stock": "2330", "Signal": "BUY"}],
        watchlist_candidates=[{"Stock": "2317", "Signal": "SELL"}],
        risk_notes=["\u96e2\u7dda\u98a8\u96aa\u6ce8\u610f"],
    )


def _run(argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = daily_report_artifact_cli.main(argv)
    return status, stdout.getvalue(), stderr.getvalue()


class DailyReportArtifactCliTests(unittest.TestCase):
    def test_root_and_subcommand_help_and_safety_wording(self):
        for argv in (
            ["--help"], ["validate", "--help"], ["inspect", "--help"],
            ["export-markdown", "--help"],
        ):
            with self.subTest(argv=argv):
                stdout = io.StringIO()
                with redirect_stdout(stdout), self.assertRaises(SystemExit) as raised:
                    daily_report_artifact_cli.main(argv)
                self.assertEqual(raised.exception.code, 0)
                self.assertIn("usage:", stdout.getvalue())

        root = io.StringIO()
        with redirect_stdout(root), self.assertRaises(SystemExit):
            daily_report_artifact_cli.main(["--help"])
        help_text = root.getvalue()
        for wording in (
            "existing offline Daily Research Report JSON artifact",
            "Does not fetch market data", "run analysis",
            "execute strategies or backtests", "connect to brokers",
            "place orders", "produce live signals", "investment advice",
        ):
            self.assertIn(wording, help_text)
        for forbidden in (
            "recommended stocks", "best stocks to buy", "buy/sell advice",
            "guaranteed return", "auto trading",
        ):
            self.assertNotIn(forbidden, help_text.lower())

    def test_parser_errors_return_two(self):
        for argv in (
            [], ["validate"], ["inspect"], ["export-markdown", "report.json"],
        ):
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    daily_report_artifact_cli.main(argv)
                self.assertEqual(raised.exception.code, 2)

    def test_validate_valid_artifact(self):
        with tempfile.TemporaryDirectory() as tempdir:
            path = export_daily_report_json_file(_report(), Path(tempdir) / "report.json")
            status, stdout, stderr = _run(["validate", str(path)])
        self.assertIsNone(status)
        self.assertEqual(stdout, f"Daily Research Report artifact is valid: {path}\n")
        self.assertEqual(stderr, "")

    def test_validate_schema_and_file_failures_return_one_without_traceback(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            artifact = json.loads(export_daily_report_json(_report()))
            version = copy.deepcopy(artifact)
            version["schema_version"] = 2
            missing = copy.deepcopy(artifact)
            missing.pop("report")
            unknown = copy.deepcopy(artifact)
            unknown["unknown"] = None
            contents = {
                "syntax.json": "{",
                "version.json": json.dumps(version),
                "missing.json": json.dumps(missing),
                "unknown.json": json.dumps(unknown),
            }
            paths = []
            for name, content in contents.items():
                path = root / name
                path.write_text(content, encoding="utf-8")
                paths.append(path)
            utf8 = root / "utf8.json"
            utf8.write_bytes(b"\xff")
            paths.extend([utf8, root / "absent.json", root])
            for path in paths:
                with self.subTest(path=path):
                    status, stdout, stderr = _run(["validate", str(path)])
                    self.assertEqual(status, 1)
                    self.assertEqual(stdout, "")
                    self.assertTrue(stderr.startswith("error: "))
                    self.assertNotIn("Traceback", stderr)

    def test_validate_permission_error(self):
        with patch(
            "tw_stock_tool.cli.daily_report_artifact_cli.load_daily_report_json_file",
            side_effect=PermissionError("locked"),
        ):
            status, stdout, stderr = _run(["validate", "report.json"])
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "error: locked\n")

    def test_inspect_exact_output_and_loader_once(self):
        report = _report()
        expected = (
            "Daily Research Report Artifact Summary\n"
            "--------------------------------------\n"
            "Report Date: 2026-07-22\n"
            "Report Type: Daily Research Report\n"
            "Total Stocks: 2\n"
            "Screening Summary Rows: 1\n"
            "Watchlist Candidate Rows: 1\n"
            "Backtest Highlight Rows: 0\n"
            "Parameter Sweep Highlight Rows: 0\n"
            "Walk Forward Highlight Rows: 0\n"
            "Risk Note Count: 2\n"
            "Data Limitation Count: 0\n"
            "Next Research Action Count: 0\n"
        )
        with patch(
            "tw_stock_tool.cli.daily_report_artifact_cli.load_daily_report_json_file",
            return_value=report,
        ) as loader:
            status, stdout, stderr = _run(["inspect", "report.json"])
        self.assertIsNone(status)
        loader.assert_called_once_with("report.json")
        self.assertEqual(stdout, expected)
        self.assertEqual(stderr, "")
        for excluded in ("2330", "2317", "BUY", "SELL", '"schema_version"'):
            self.assertNotIn(excluded, stdout)

    def test_inspect_empty_and_unicode_metadata(self):
        report = build_daily_report_data()
        report["Report Metadata"] = {
            "Date": "\u6c11\u570b115\u5e74",
            "Type": "\u6bcf\u65e5\u7814\u7a76\u5831\u544a",
        }
        with patch(
            "tw_stock_tool.cli.daily_report_artifact_cli.load_daily_report_json_file",
            return_value=report,
        ):
            status, stdout, stderr = _run(["inspect", "report.json"])
        self.assertIsNone(status)
        self.assertIn("Report Date: \u6c11\u570b115\u5e74", stdout)
        self.assertIn("Report Type: \u6bcf\u65e5\u7814\u7a76\u5831\u544a", stdout)
        self.assertIn("Total Stocks: 0", stdout)
        self.assertEqual(stderr, "")

    def test_export_uses_loaded_identity_order_returned_path_and_overwrite(self):
        report = _report()
        returned = Path("absolute-returned.md").resolve()
        events = []

        def load(path):
            events.append(("load", path))
            return report

        def export(value, path, *, overwrite):
            events.append(("export", value, path, overwrite))
            return returned

        with patch(
            "tw_stock_tool.cli.daily_report_artifact_cli.load_daily_report_json_file",
            side_effect=load,
        ) as loader, patch(
            "tw_stock_tool.cli.daily_report_artifact_cli.export_daily_report_markdown_file",
            side_effect=export,
        ) as exporter:
            status, stdout, stderr = _run([
                "export-markdown", "report.json",
                "--output-markdown", "custom/report.md", "--overwrite",
            ])
        self.assertIsNone(status)
        loader.assert_called_once_with("report.json")
        args, kwargs = exporter.call_args
        self.assertIs(args[0], report)
        self.assertEqual(args[1], "custom/report.md")
        self.assertEqual(kwargs, {"overwrite": True})
        self.assertEqual(events[0], ("load", "report.json"))
        self.assertEqual(events[1][0], "export")
        self.assertEqual(stdout, f"Daily Research Report Markdown written: {returned}\n")
        self.assertEqual(stderr, "")

    def test_export_default_overwrite_false(self):
        with patch(
            "tw_stock_tool.cli.daily_report_artifact_cli.load_daily_report_json_file",
            return_value=_report(),
        ), patch(
            "tw_stock_tool.cli.daily_report_artifact_cli.export_daily_report_markdown_file",
            return_value=Path("out.md").resolve(),
        ) as exporter:
            status, _, _ = _run([
                "export-markdown", "report.json", "--output-markdown", "out.md",
            ])
        self.assertIsNone(status)
        self.assertFalse(exporter.call_args.kwargs["overwrite"])

    def test_export_runtime_errors_have_no_success_output(self):
        errors = (
            FileExistsError("exists"), PermissionError("locked"),
            DailyReportSerializationError("bad artifact"),
        )
        for error in errors:
            with self.subTest(error=error), patch(
                "tw_stock_tool.cli.daily_report_artifact_cli.load_daily_report_json_file",
                return_value=_report(),
            ), patch(
                "tw_stock_tool.cli.daily_report_artifact_cli.export_daily_report_markdown_file",
                side_effect=error,
            ):
                status, stdout, stderr = _run([
                    "export-markdown", "report.json", "--output-markdown", "out.md",
                ])
            self.assertEqual(status, 1)
            self.assertEqual(stdout, "")
            self.assertTrue(stderr.startswith("error: "))
            self.assertNotIn("Traceback", stderr)
            self.assertNotIn("Markdown written", stdout)
            if isinstance(error, FileExistsError):
                self.assertIn("--overwrite", stderr)

    def test_real_export_preserves_input_json(self):
        with tempfile.TemporaryDirectory() as tempdir:
            source = export_daily_report_json_file(
                _report(), Path(tempdir) / "report.json"
            )
            before = source.read_bytes()
            target = Path(tempdir) / "restored.md"
            status, stdout, stderr = _run([
                "export-markdown", str(source), "--output-markdown", str(target),
            ])
            self.assertIsNone(status)
            self.assertTrue(target.exists())
            self.assertEqual(source.read_bytes(), before)
            self.assertIn(str(target.resolve()), stdout)
            self.assertEqual(stderr, "")

    def test_clean_subprocess_dependency_boundary(self):
        code = """
import sys
import tw_stock_tool.cli.daily_report_artifact_cli
forbidden = (
    "tw_stock_tool.analysis", "tw_stock_tool.data",
    "tw_stock_tool.backtesting", "tw_stock_tool.paper_trading",
    "tw_stock_tool.ml", "yfinance", "sklearn", "shioaji",
)
found = sorted(name for name in sys.modules if any(
    name == prefix or name.startswith(prefix + ".") for prefix in forbidden
))
if found:
    print("forbidden modules: " + ", ".join(found))
    raise SystemExit(1)
"""
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tw_stock_tool.reports.daily_report import build_daily_report_data
from tw_stock_tool.reports.daily_report_export_files import export_daily_report_markdown_file
from tw_stock_tool.reports.daily_report_markdown import render_daily_report_markdown
from tw_stock_tool.reports.daily_report_serialization_files import (
    export_daily_report_json_file,
    load_daily_report_json_file,
)


def _report():
    return build_daily_report_data(
        report_date="2026-07-22",
        stock_universe=["2330"],
        watchlist_candidates=[{
            "Stock": "2330",
            "Note": "\u8cc7\u6599 | \u4f86\u6e90\r\n\u66ab\u6642\u5931\u6557",
            "Optional": None,
        }],
        next_research_actions=["\u96e2\u7dda\u8907\u6838"],
    )


class DailyReportMarkdownFileExportTests(unittest.TestCase):
    def test_path_types_nested_parent_exact_content_and_encoding(self):
        for use_string in (False, True):
            with self.subTest(use_string=use_string), tempfile.TemporaryDirectory() as tempdir:
                target = Path(tempdir) / "nested" / "report.md"
                report = _report()
                expected = render_daily_report_markdown(report)
                written = export_daily_report_markdown_file(
                    report, str(target) if use_string else target
                )
                self.assertEqual(written, target.resolve())
                self.assertTrue(written.is_absolute())
                self.assertEqual(written.read_text(encoding="utf-8"), expected)
                raw = written.read_bytes()
                self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
                self.assertFalse(raw.endswith(b"\n\n"))
                self.assertIn(
                    "\u8cc7\u6599 \\| \u4f86\u6e90<br>\u66ab\u6642\u5931\u6557",
                    expected,
                )

    def test_overwrite_policy_and_existing_content_preservation(self):
        with tempfile.TemporaryDirectory() as tempdir:
            target = Path(tempdir) / "report.md"
            target.write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                export_daily_report_markdown_file(_report(), target)
            self.assertEqual(target.read_text(encoding="utf-8"), "existing")
            written = export_daily_report_markdown_file(_report(), target, overwrite=True)
            self.assertEqual(
                written.read_text(encoding="utf-8"),
                render_daily_report_markdown(_report()),
            )

    def test_renderer_runs_before_writer_with_exact_arguments(self):
        report = _report()
        target = Path("custom.md")
        events = []
        returned = target.resolve()

        def render(value):
            events.append(("render", value))
            return "markdown"

        def write(content, path, *, overwrite):
            events.append(("write", content, path, overwrite))
            return returned

        with patch(
            "tw_stock_tool.reports.daily_report_export_files.render_daily_report_markdown",
            side_effect=render,
        ) as renderer, patch(
            "tw_stock_tool.reports.daily_report_export_files.write_text_report",
            side_effect=write,
        ) as writer:
            result = export_daily_report_markdown_file(report, target, overwrite=True)

        renderer.assert_called_once_with(report)
        writer.assert_called_once_with("markdown", target, overwrite=True)
        self.assertIs(events[0][1], report)
        self.assertEqual([event[0] for event in events], ["render", "write"])
        self.assertEqual(result, returned)

    def test_render_failure_creates_no_file_or_directory(self):
        with tempfile.TemporaryDirectory() as tempdir:
            target = Path(tempdir) / "missing" / "report.md"
            with patch(
                "tw_stock_tool.reports.daily_report_export_files.render_daily_report_markdown",
                side_effect=ValueError("render failed"),
            ), patch(
                "tw_stock_tool.reports.daily_report_export_files.write_text_report",
            ) as writer:
                with self.assertRaisesRegex(ValueError, "render failed"):
                    export_daily_report_markdown_file(_report(), target)
            writer.assert_not_called()
            self.assertFalse(target.exists())
            self.assertFalse(target.parent.exists())

    def test_input_is_not_mutated(self):
        report = _report()
        before = copy.deepcopy(report)
        with tempfile.TemporaryDirectory() as tempdir:
            export_daily_report_markdown_file(report, Path(tempdir) / "report.md")
        self.assertEqual(report, before)

    def test_json_load_to_markdown_round_trip_is_exact_and_offline(self):
        report = _report()
        before = copy.deepcopy(report)
        with tempfile.TemporaryDirectory() as tempdir:
            json_written = export_daily_report_json_file(
                report, Path(tempdir) / "report.json"
            )
            json_before = json_written.read_bytes()
            loaded = load_daily_report_json_file(json_written)
            markdown_path = Path(tempdir) / "restored" / "report.md"
            with patch("socket.create_connection") as network:
                written = export_daily_report_markdown_file(loaded, markdown_path)
            network.assert_not_called()
            restored = written.read_text(encoding="utf-8")
            self.assertEqual(restored, render_daily_report_markdown(loaded))
            self.assertEqual(json_written.read_bytes(), json_before)
            self.assertEqual(report, before)
            self.assertIn("\\|", restored)
            self.assertIn("<br>", restored)


if __name__ == "__main__":
    unittest.main()

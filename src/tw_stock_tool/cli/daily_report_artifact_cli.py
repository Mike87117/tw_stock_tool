"""CLI for existing offline Daily Research Report JSON artifacts."""

from __future__ import annotations

import argparse
import sys

from tw_stock_tool.reports.daily_report_artifact import (
    build_daily_report_artifact_summary,
)
from tw_stock_tool.reports.daily_report_export_files import (
    export_daily_report_markdown_file,
)
from tw_stock_tool.reports.daily_report_serialization import (
    DailyReportSerializationError,
)
from tw_stock_tool.reports.daily_report_serialization_files import (
    load_daily_report_json_file,
)


_DESCRIPTION = (
    "Operate on an existing offline Daily Research Report JSON artifact.\n"
    "Does not fetch market data, run analysis, execute strategies or backtests,\n"
    "connect to brokers, place orders, produce live signals, or provide\n"
    "investment advice."
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate",
        help="Validate an existing Daily Research Report JSON artifact.",
    )
    validate.add_argument("input_json")

    inspect = subparsers.add_parser(
        "inspect",
        help="Inspect metadata and counts from an existing artifact.",
    )
    inspect.add_argument("input_json")

    export_markdown = subparsers.add_parser(
        "export-markdown",
        help="Export Markdown from an existing canonical artifact.",
    )
    export_markdown.add_argument("input_json")
    export_markdown.add_argument("--output-markdown", required=True)
    export_markdown.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing Markdown output file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int | None:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            load_daily_report_json_file(args.input_json)
            print(f"Daily Research Report artifact is valid: {args.input_json}")
        elif args.command == "inspect":
            report_data = load_daily_report_json_file(args.input_json)
            summary = build_daily_report_artifact_summary(report_data)
            print("Daily Research Report Artifact Summary")
            print("--------------------------------------")
            for key, value in summary.items():
                print(f"{key}: {value}")
        elif args.command == "export-markdown":
            report_data = load_daily_report_json_file(args.input_json)
            written_path = export_daily_report_markdown_file(
                report_data,
                args.output_markdown,
                overwrite=args.overwrite,
            )
            print(f"Daily Research Report Markdown written: {written_path}")
    except FileExistsError as exc:
        print(
            f"error: {exc}. Use --overwrite to replace existing files.",
            file=sys.stderr,
        )
        return 1
    except (
        FileNotFoundError,
        IsADirectoryError,
        PermissionError,
        UnicodeDecodeError,
        DailyReportSerializationError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return None


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline, read-only inspection commands for existing Workspaces."""

from __future__ import annotations

import argparse
from dataclasses import fields, is_dataclass
from pprint import pformat
import sys

from tw_stock_tool.application.workspace_query import (
    InspectWorkspaceRunRequest,
    ListWorkspaceRunsRequest,
    inspect_workspace_run,
    list_workspace_runs,
)
from tw_stock_tool.artifacts import WorkspaceError, WorkspaceValidationError, validate_run_id


def _run_id(value: str) -> str:
    try:
        return validate_run_id(value)
    except WorkspaceValidationError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _value(value: object) -> str:
    return "-" if value is None or value == () else str(value)


def _finding_codes(entry) -> str:
    return ", ".join(finding.code.value for finding in entry.findings) or "-"


def _print_entry(entry) -> None:
    print(f"Run ID: {_value(entry.run_id)}")
    print(f"Created At: {_value(entry.created_at)}")
    print(f"Workflow: {_value(entry.workflow)}")
    print(f"Status: {_value(entry.status)}")
    print(f"Health: {entry.health.value}")
    print(f"Canonical Symbols: {', '.join(entry.canonical_symbols) or '-'}")
    print(f"Artifact Count: {entry.artifact_count}")
    print(f"Finding Codes: {_finding_codes(entry)}")
    print(f"Run Directory: {entry.run_directory}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="twstock run", description="Offline, read-only Workspace run inspection")
    commands = parser.add_subparsers(dest="command", required=True)
    list_parser = commands.add_parser("list", help="List existing Workspace runs")
    list_parser.add_argument("--workspace", required=True)
    inspect_parser = commands.add_parser("inspect", help="Inspect one existing Workspace run")
    inspect_parser.add_argument("run_id", type=_run_id, help="Exact canonical lowercase UUID v4")
    inspect_parser.add_argument("--workspace", required=True)
    return parser.parse_args(argv)

def _display_data(value: object) -> object:
    if is_dataclass(value):
        return {field.name: _display_data(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict) or hasattr(value, "items"):
        return {str(key): _display_data(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [_display_data(item) for item in value]
    return value

def _print_details(entry) -> None:
    _print_entry(entry)
    manifest = entry.manifest
    if manifest is None:
        return
    print(f"Tool Version: {manifest.tool_version}")
    print(f"Universe: {_value(manifest.config.universe)}")
    print("Resolved Configuration:")
    print(pformat(_display_data(manifest.config), sort_dicts=True, width=100))
    print("Data Sources:")
    print(pformat([_display_data(item) for item in manifest.data_sources], sort_dicts=True, width=100))
    print("Artifact References:")
    print(pformat([_display_data(item) for item in manifest.artifacts], sort_dicts=True, width=100))
    print("Warnings:")
    print(pformat(list(manifest.limitations), width=100))
    print("Errors:")
    print(pformat(list(manifest.errors), width=100))
    print("Catalog Findings:")
    print(pformat([{"code": item.code.value, "message": item.message, "path": str(item.path)} for item in entry.findings], sort_dicts=True, width=100))
    print(f"Manifest Path: {entry.manifest_path}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "list":
            catalog = list_workspace_runs(ListWorkspaceRunsRequest(args.workspace))
            if not catalog.entries:
                print("No runs found.")
            for index, entry in enumerate(catalog.entries):
                if index:
                    print()
                _print_entry(entry)
            return 0
        _print_details(inspect_workspace_run(InspectWorkspaceRunRequest(args.workspace, args.run_id)))
        return 0
    except WorkspaceError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

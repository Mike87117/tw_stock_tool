"""
Multi-symbol simulated portfolio trading report exporters (Markdown and CSV bundle).
"""

import csv
import io
import json
from typing import Any

from tw_stock_tool.paper_trading.models import PaperTradingModelError
from tw_stock_tool.paper_trading.portfolio_report_data import (
    build_simulated_portfolio_trading_report_data,
)
from tw_stock_tool.paper_trading.portfolio_results import SimulatedPortfolioTradingResult


def _dump_metadata(value: dict[str, Any]) -> str:
    if not isinstance(value, dict):
        raise PaperTradingModelError("metadata must be a dictionary.")
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise PaperTradingModelError(f"Invalid metadata JSON serialization: {exc}") from exc


def _format_markdown_value(value: Any, *, is_pct: bool = False) -> str:
    if value is None:
        formatted = ""
    elif is_pct and isinstance(value, (int, float)) and not isinstance(value, bool):
        formatted = f"{float(value) * 100:,.2f}%"
    elif isinstance(value, dict):
        formatted = _dump_metadata(value)
    elif isinstance(value, float):
        formatted = f"{value:,.2f}"
    else:
        formatted = str(value)

    formatted = formatted.replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")
    return formatted.replace("|", r"\|")


def _format_csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return _dump_metadata(value)
    return str(value)


def export_simulated_portfolio_trading_markdown(
    result: SimulatedPortfolioTradingResult,
) -> str:
    """Export a SimulatedPortfolioTradingResult to a pure Markdown string."""
    report_data = build_simulated_portfolio_trading_report_data(result)

    summary = report_data["summary"]
    position_rows = report_data["position_rows"]
    pending_rows = report_data["pending_order_rows"]
    order_rows = report_data["order_rows"]
    fill_rows = report_data["fill_rows"]
    rejection_rows = report_data["rejection_rows"]
    trade_log_rows = report_data["trade_log_rows"]

    lines = [
        "# Simulated Portfolio Trading Report",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]

    summary_labels = [
        ("Initial Cash", "initial_cash"),
        ("Final Cash", "final_cash"),
        ("Total Market Value", "total_market_value"),
        ("Total Equity", "total_equity"),
        ("Realized PnL", "realized_pnl"),
        ("Unrealized PnL", "unrealized_pnl"),
        ("Total Return", "total_return"),
        ("Total Return %", "total_return_pct"),
        ("Open Position Count", "open_position_count"),
        ("Pending Order Count", "pending_order_count"),
        ("Order Count", "order_count"),
        ("Fill Count", "fill_count"),
        ("Rejection Count", "rejection_count"),
        ("Audit Record Count", "audit_record_count"),
    ]

    for label, key in summary_labels:
        val = summary.get(key)
        formatted_val = _format_markdown_value(val, is_pct=(key == "total_return_pct"))
        lines.append(f"| {label} | {formatted_val} |")

    lines.append("")
    lines.append("## Positions")
    lines.append("")
    if not position_rows:
        lines.append("*No positions to display.*")
    else:
        lines.append("| Symbol | Quantity | Average Cost | Last Price | Market Value | Realized PnL | Unrealized PnL |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for r in position_rows:
            vals = [
                _format_markdown_value(r.get("symbol")),
                _format_markdown_value(r.get("quantity")),
                _format_markdown_value(r.get("average_cost")),
                _format_markdown_value(r.get("last_price")),
                _format_markdown_value(r.get("market_value")),
                _format_markdown_value(r.get("realized_pnl")),
                _format_markdown_value(r.get("unrealized_pnl")),
            ]
            lines.append("| " + " | ".join(vals) + " |")

    lines.append("")
    lines.append("## Pending Orders")
    lines.append("")
    if not pending_rows:
        lines.append("*No pending orders to display.*")
    else:
        lines.append("| Order ID | Symbol | Side | Quantity | Signal Time | Created At | Strategy | Reference Price | Reserved Buy Notional |")
        lines.append("|---|---|---|---:|---|---|---|---:|---:|")
        for r in pending_rows:
            vals = [
                _format_markdown_value(r.get("order_id")),
                _format_markdown_value(r.get("symbol")),
                _format_markdown_value(r.get("side")),
                _format_markdown_value(r.get("quantity")),
                _format_markdown_value(r.get("signal_time")),
                _format_markdown_value(r.get("created_at")),
                _format_markdown_value(r.get("strategy")),
                _format_markdown_value(r.get("reference_price")),
                _format_markdown_value(r.get("reserved_buy_notional")),
            ]
            lines.append("| " + " | ".join(vals) + " |")

    lines.append("")
    lines.append("## Orders")
    lines.append("")
    if not order_rows:
        lines.append("*No orders to display.*")
    else:
        lines.append("| Order ID | Symbol | Side | Quantity | Signal Time | Created At | Strategy |")
        lines.append("|---|---|---|---:|---|---|---|")
        for r in order_rows:
            vals = [
                _format_markdown_value(r.get("order_id")),
                _format_markdown_value(r.get("symbol")),
                _format_markdown_value(r.get("side")),
                _format_markdown_value(r.get("quantity")),
                _format_markdown_value(r.get("signal_time")),
                _format_markdown_value(r.get("created_at")),
                _format_markdown_value(r.get("strategy")),
            ]
            lines.append("| " + " | ".join(vals) + " |")

    lines.append("")
    lines.append("## Fills")
    lines.append("")
    if not fill_rows:
        lines.append("*No fills to display.*")
    else:
        lines.append("| Order ID | Symbol | Side | Quantity | Price | Filled At | Fee | Tax | Slippage | Gross Amount | Net Cash Effect |")
        lines.append("|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|")
        for r in fill_rows:
            vals = [
                _format_markdown_value(r.get("order_id")),
                _format_markdown_value(r.get("symbol")),
                _format_markdown_value(r.get("side")),
                _format_markdown_value(r.get("quantity")),
                _format_markdown_value(r.get("price")),
                _format_markdown_value(r.get("filled_at")),
                _format_markdown_value(r.get("fee")),
                _format_markdown_value(r.get("tax")),
                _format_markdown_value(r.get("slippage")),
                _format_markdown_value(r.get("gross_amount")),
                _format_markdown_value(r.get("net_cash_effect")),
            ]
            lines.append("| " + " | ".join(vals) + " |")

    lines.append("")
    lines.append("## Rejected Simulated Order Intents")
    lines.append("")
    if not rejection_rows:
        lines.append("*No rejected simulated order intents.*")
    else:
        lines.append("| Order ID | Symbol | Side | Quantity | Signal Time | Created At | Strategy | Reasons |")
        lines.append("|---|---|---|---:|---|---|---|---|")
        for r in rejection_rows:
            vals = [
                _format_markdown_value(r.get("order_id")),
                _format_markdown_value(r.get("symbol")),
                _format_markdown_value(r.get("side")),
                _format_markdown_value(r.get("quantity")),
                _format_markdown_value(r.get("signal_time")),
                _format_markdown_value(r.get("created_at")),
                _format_markdown_value(r.get("strategy")),
                _format_markdown_value(r.get("reasons")),
            ]
            lines.append("| " + " | ".join(vals) + " |")

    lines.append("")
    lines.append("## Trade Log")
    lines.append("")
    if not trade_log_rows:
        lines.append("*No audit events to display.*")
    else:
        lines.append("| Sequence | Record ID | Event Type | Status | Order ID | Symbol | Side | Quantity | Signal Time | Order Created At | Expected Execution Model | Fill Time | Fill Price | Fee | Tax | Slippage | Strategy Name | Strategy Metadata | Risk Allowed | Risk Rejection Reasons | Guard Metadata | Error Code | Error Message |")
        lines.append("|---:|---|---|---|---|---|---|---:|---|---|---|---|---:|---:|---:|---:|---|---|---|---|---|---|---|")
        for r in trade_log_rows:
            vals = [
                _format_markdown_value(r.get("sequence")),
                _format_markdown_value(r.get("record_id")),
                _format_markdown_value(r.get("event_type")),
                _format_markdown_value(r.get("status")),
                _format_markdown_value(r.get("order_id")),
                _format_markdown_value(r.get("symbol")),
                _format_markdown_value(r.get("side")),
                _format_markdown_value(r.get("quantity")),
                _format_markdown_value(r.get("signal_time")),
                _format_markdown_value(r.get("order_created_at")),
                _format_markdown_value(r.get("expected_execution_model")),
                _format_markdown_value(r.get("fill_time")),
                _format_markdown_value(r.get("fill_price")),
                _format_markdown_value(r.get("fee")),
                _format_markdown_value(r.get("tax")),
                _format_markdown_value(r.get("slippage")),
                _format_markdown_value(r.get("strategy_name")),
                _format_markdown_value(r.get("strategy_metadata")),
                _format_markdown_value(r.get("risk_allowed")),
                _format_markdown_value(r.get("risk_rejection_reasons")),
                _format_markdown_value(r.get("guard_metadata")),
                _format_markdown_value(r.get("error_code")),
                _format_markdown_value(r.get("error_message")),
            ]
            lines.append("| " + " | ".join(vals) + " |")

    lines.append("")
    return "\n".join(lines)


def export_simulated_portfolio_trading_csv_bundle(
    result: SimulatedPortfolioTradingResult,
) -> dict[str, str]:
    """Export a SimulatedPortfolioTradingResult to a bundle of CSV strings."""
    report_data = build_simulated_portfolio_trading_report_data(result)

    summary = report_data["summary"]
    position_rows = report_data["position_rows"]
    pending_rows = report_data["pending_order_rows"]
    order_rows = report_data["order_rows"]
    fill_rows = report_data["fill_rows"]
    rejection_rows = report_data["rejection_rows"]
    trade_log_rows = report_data["trade_log_rows"]

    summary_keys = [
        "initial_cash",
        "final_cash",
        "total_market_value",
        "total_equity",
        "realized_pnl",
        "unrealized_pnl",
        "total_return",
        "total_return_pct",
        "open_position_count",
        "pending_order_count",
        "order_count",
        "fill_count",
        "rejection_count",
        "audit_record_count",
    ]

    summary_io = io.StringIO()
    summary_writer = csv.writer(summary_io, lineterminator="\n")
    summary_writer.writerow(["metric", "value"])
    for k in summary_keys:
        val = summary.get(k)
        summary_writer.writerow([k, _format_csv_value(val)])

    positions_io = io.StringIO()
    positions_writer = csv.writer(positions_io, lineterminator="\n")
    pos_keys = ["symbol", "quantity", "average_cost", "last_price", "market_value", "realized_pnl", "unrealized_pnl"]
    positions_writer.writerow(pos_keys)
    for r in position_rows:
        positions_writer.writerow([_format_csv_value(r.get(k)) for k in pos_keys])

    pending_io = io.StringIO()
    pending_writer = csv.writer(pending_io, lineterminator="\n")
    pending_keys = ["order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy", "reference_price", "reserved_buy_notional"]
    pending_writer.writerow(pending_keys)
    for r in pending_rows:
        pending_writer.writerow([_format_csv_value(r.get(k)) for k in pending_keys])

    orders_io = io.StringIO()
    orders_writer = csv.writer(orders_io, lineterminator="\n")
    order_keys = ["order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy"]
    orders_writer.writerow(order_keys)
    for r in order_rows:
        orders_writer.writerow([_format_csv_value(r.get(k)) for k in order_keys])

    fills_io = io.StringIO()
    fills_writer = csv.writer(fills_io, lineterminator="\n")
    fill_keys = ["order_id", "symbol", "side", "quantity", "price", "filled_at", "fee", "tax", "slippage", "gross_amount", "net_cash_effect"]
    fills_writer.writerow(fill_keys)
    for r in fill_rows:
        fills_writer.writerow([_format_csv_value(r.get(k)) for k in fill_keys])

    rejections_io = io.StringIO()
    rejections_writer = csv.writer(rejections_io, lineterminator="\n")
    rejection_keys = ["order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy", "reasons"]
    rejections_writer.writerow(rejection_keys)
    for r in rejection_rows:
        rejections_writer.writerow([_format_csv_value(r.get(k)) for k in rejection_keys])

    trade_log_io = io.StringIO()
    trade_log_writer = csv.writer(trade_log_io, lineterminator="\n")
    trade_log_keys = [
        "sequence", "record_id", "event_type", "status", "order_id", "symbol", "side",
        "quantity", "signal_time", "order_created_at", "expected_execution_model", "fill_time",
        "fill_price", "fee", "tax", "slippage", "strategy_name", "strategy_metadata",
        "risk_allowed", "risk_rejection_reasons", "guard_metadata", "error_code", "error_message",
    ]
    trade_log_writer.writerow(trade_log_keys)
    for r in trade_log_rows:
        trade_log_writer.writerow([_format_csv_value(r.get(k)) for k in trade_log_keys])

    return {
        "summary": summary_io.getvalue(),
        "positions": positions_io.getvalue(),
        "pending_orders": pending_io.getvalue(),
        "orders": orders_io.getvalue(),
        "fills": fills_io.getvalue(),
        "rejections": rejections_io.getvalue(),
        "trade_log": trade_log_io.getvalue(),
    }

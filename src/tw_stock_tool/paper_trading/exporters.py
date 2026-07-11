import csv
import io
import json
from typing import Any
from .results import (
    SimulatedPaperTradingResult,
    build_simulated_paper_trading_report_data,
)

def _format_value(value: Any) -> str:
    """Format an arbitrary value for Markdown rendering safely."""
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value).replace("|", r"\|")

def export_simulated_paper_trading_markdown(
    result: SimulatedPaperTradingResult,
) -> str:
    """Export a SimulatedPaperTradingResult to a pure Markdown string."""
    report_data = build_simulated_paper_trading_report_data(result)

    summary = report_data["summary"]
    order_rows = report_data["order_rows"]
    fill_rows = report_data["fill_rows"]
    rejection_rows = report_data.get("rejection_rows", [])
    trade_log_rows = report_data.get("trade_log_rows", [])

    lines = [
        "# Simulated Paper Trading Report",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]

    # Render summary dictionary
    # Provide ordered list of known keys to present them neatly.
    summary_keys = [
        ("Symbol", "symbol"),
        ("Initial Cash", "initial_cash"),
        ("Final Cash", "final_cash"),
        ("Final Position Quantity", "final_position_quantity"),
        ("Average Cost", "average_cost"),
        ("Realized PnL", "realized_pnl"),
        ("Unrealized PnL", "unrealized_pnl"),
        ("Total Equity", "total_equity"),
        ("Order Count", "order_count"),
        ("Fill Count", "fill_count"),
        ("Open Position Count", "open_position_count"),
        ("Total Return", "total_return"),
        ("Total Return %", "total_return_pct"),
    ]

    for label, key in summary_keys:
        value = summary.get(key)
        if key == "total_return_pct" and value is not None:
            formatted_val = f"{value * 100:,.2f}%"
        else:
            formatted_val = _format_value(value)
        lines.append(f"| {label} | {formatted_val} |")

    lines.append("")
    lines.append("## Orders")
    lines.append("")
    if not order_rows:
        lines.append("*No orders to display.*")
    else:
        lines.append("| Order ID | Symbol | Side | Quantity | Signal Time | Created At | Strategy |")
        lines.append("|---|---|---:|---:|---|---|---|")

        for row in order_rows:
            order_id = _format_value(row.get("order_id"))
            symbol = _format_value(row.get("symbol"))
            side = _format_value(row.get("side"))
            quantity = _format_value(row.get("quantity"))
            signal_time = _format_value(row.get("signal_time"))
            created_at = _format_value(row.get("created_at"))
            strategy = _format_value(row.get("strategy"))
            lines.append(f"| {order_id} | {symbol} | {side} | {quantity} | {signal_time} | {created_at} | {strategy} |")

    lines.append("")
    lines.append("## Fills")
    lines.append("")
    if not fill_rows:
        lines.append("*No fills to display.*")
    else:
        lines.append("| Order ID | Symbol | Side | Quantity | Price | Filled At | Fee | Tax | Slippage | Gross Amount | Net Cash Effect |")
        lines.append("|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|")

        for row in fill_rows:
            order_id = _format_value(row.get("order_id"))
            symbol = _format_value(row.get("symbol"))
            side = _format_value(row.get("side"))
            quantity = _format_value(row.get("quantity"))
            price = _format_value(row.get("price"))
            filled_at = _format_value(row.get("filled_at"))
            fee = _format_value(row.get("fee"))
            tax = _format_value(row.get("tax"))
            slippage = _format_value(row.get("slippage"))
            gross_amount = _format_value(row.get("gross_amount"))
            net_cash_effect = _format_value(row.get("net_cash_effect"))

            lines.append(f"| {order_id} | {symbol} | {side} | {quantity} | {price} | {filled_at} | {fee} | {tax} | {slippage} | {gross_amount} | {net_cash_effect} |")

    lines.append("")
    lines.append("## Rejected Simulated Order Intents")
    lines.append("")
    if not rejection_rows:
        lines.append("*No rejected simulated order intents.*")
    else:
        lines.append("| Order ID | Symbol | Side | Quantity | Signal Time | Created At | Strategy | Reasons |")
        lines.append("|---|---|---:|---:|---|---|---|---|")

        for row in rejection_rows:
            order_id = _format_value(row.get("order_id"))
            symbol = _format_value(row.get("symbol"))
            side = _format_value(row.get("side"))
            quantity = _format_value(row.get("quantity"))
            signal_time = _format_value(row.get("signal_time"))
            created_at = _format_value(row.get("created_at"))
            strategy = _format_value(row.get("strategy"))
            reasons = _format_value(row.get("reasons"))
            lines.append(f"| {order_id} | {symbol} | {side} | {quantity} | {signal_time} | {created_at} | {strategy} | {reasons} |")


    lines.append("")
    lines.append("## Trade Log")
    lines.append("")
    if not trade_log_rows:
        lines.append("*No audit events to display.*")
    else:
        lines.append("| Sequence | Event | Status | Order ID | Symbol | Side | Quantity | Signal Time | Fill Time | Fill Price | Risk Allowed | Reasons | Error Code | Error Message |")
        lines.append("|---:|---|---|---|---|---|---:|---|---|---:|---|---|---|---|")
        for row in trade_log_rows:
            values = [
                row.get("sequence"), row.get("event_type"), row.get("status"), row.get("order_id"),
                row.get("symbol"), row.get("side"), row.get("quantity"), row.get("signal_time"),
                row.get("fill_time"), row.get("fill_price"), row.get("risk_allowed"),
                row.get("risk_rejection_reasons"), row.get("error_code"), row.get("error_message"),
            ]
            lines.append("| " + " | ".join(_format_value(value) for value in values) + " |")
    # Append trailing newline
    lines.append("")
    return "\n".join(lines)

def export_simulated_paper_trading_csv_bundle(
    result: SimulatedPaperTradingResult,
) -> dict[str, str]:
    """Export a SimulatedPaperTradingResult to a bundle of CSV strings."""
    report_data = build_simulated_paper_trading_report_data(result)

    summary = report_data["summary"]
    order_rows = report_data["order_rows"]
    fill_rows = report_data["fill_rows"]
    rejection_rows = report_data.get("rejection_rows", [])
    trade_log_rows = report_data.get("trade_log_rows", [])

    # 1. Summary CSV
    summary_keys = [
        "symbol",
        "initial_cash",
        "final_cash",
        "final_position_quantity",
        "average_cost",
        "realized_pnl",
        "unrealized_pnl",
        "total_equity",
        "order_count",
        "fill_count",
        "open_position_count",
        "total_return",
        "total_return_pct",
    ]

    summary_io = io.StringIO()
    summary_writer = csv.writer(summary_io, lineterminator="\n")
    summary_writer.writerow(["metric", "value"])

    for key in summary_keys:
        value = summary.get(key)
        if value is None:
            csv_val = ""
        else:
            csv_val = str(value)
        summary_writer.writerow([key, csv_val])

    # 2. Orders CSV
    order_keys = [
        "order_id",
        "symbol",
        "side",
        "quantity",
        "signal_time",
        "created_at",
        "strategy",
    ]

    orders_io = io.StringIO()
    orders_writer = csv.writer(orders_io, lineterminator="\n")
    orders_writer.writerow(order_keys)

    for row in order_rows:
        row_vals = []
        for k in order_keys:
            v = row.get(k)
            row_vals.append("" if v is None else str(v))
        orders_writer.writerow(row_vals)

    # 3. Fills CSV
    fill_keys = [
        "order_id",
        "symbol",
        "side",
        "quantity",
        "price",
        "filled_at",
        "fee",
        "tax",
        "slippage",
        "gross_amount",
        "net_cash_effect",
    ]

    fills_io = io.StringIO()
    fills_writer = csv.writer(fills_io, lineterminator="\n")
    fills_writer.writerow(fill_keys)

    for row in fill_rows:
        row_vals = []
        for k in fill_keys:
            v = row.get(k)
            row_vals.append("" if v is None else str(v))
        fills_writer.writerow(row_vals)

    # 4. Rejections CSV
    rejection_keys = [
        "order_id",
        "symbol",
        "side",
        "quantity",
        "signal_time",
        "created_at",
        "strategy",
        "reasons",
    ]

    rejections_io = io.StringIO()
    rejections_writer = csv.writer(rejections_io, lineterminator="\n")
    rejections_writer.writerow(rejection_keys)

    for row in rejection_rows:
        row_vals = []
        for k in rejection_keys:
            v = row.get(k)
            row_vals.append("" if v is None else str(v))
        rejections_writer.writerow(row_vals)


    # 5. Canonical trade log CSV
    trade_log_keys = [
        "sequence", "record_id", "event_type", "status", "order_id", "symbol", "side",
        "quantity", "signal_time", "order_created_at", "expected_execution_model", "fill_time",
        "fill_price", "fee", "tax", "slippage", "strategy_name", "strategy_metadata",
        "risk_allowed", "risk_rejection_reasons", "guard_metadata", "error_code", "error_message",
    ]
    trade_log_io = io.StringIO()
    trade_log_writer = csv.writer(trade_log_io, lineterminator="\n")
    trade_log_writer.writerow(trade_log_keys)
    for row in trade_log_rows:
        values = []
        for key in trade_log_keys:
            value = row.get(key)
            if isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
            values.append("" if value is None else str(value))
        trade_log_writer.writerow(values)
    return {
        "summary": summary_io.getvalue(),
        "orders": orders_io.getvalue(),
        "fills": fills_io.getvalue(),
        "rejections": rejections_io.getvalue(),
        "trade_log": trade_log_io.getvalue(),
    }

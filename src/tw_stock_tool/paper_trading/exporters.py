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

    # Append trailing newline
    lines.append("")
    return "\n".join(lines)

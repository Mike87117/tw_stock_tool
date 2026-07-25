"""
Unit tests for portfolio report exporters (Markdown and CSV bundle).
"""

import csv
import io
import unittest

from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedFill,
    SimulatedOrder,
    SimulatedOrderRejection,
    SimulatedTradeEventType,
    SimulatedTradeLogRecord,
    SimulatedTradeStatus,
)
from tw_stock_tool.paper_trading.portfolio_exporters import (
    _dump_metadata,
    export_simulated_portfolio_trading_csv_bundle,
    export_simulated_portfolio_trading_markdown,
)
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioPendingOrderResult,
    SimulatedPortfolioPositionResult,
    SimulatedPortfolioTradingResult,
)


def _make_empty_result() -> SimulatedPortfolioTradingResult:
    return SimulatedPortfolioTradingResult(
        initial_cash=100000.0,
        final_cash=100000.0,
        total_market_value=0.0,
        total_equity=100000.0,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        total_return=0.0,
        total_return_pct=0.0,
        open_position_count=0,
        order_count=0,
        fill_count=0,
        rejection_count=0,
        audit_record_count=0,
        positions=(),
        pending_orders=(),
        orders=(),
        fills=(),
        rejections=(),
        audit_log=(),
    )


def _make_full_result() -> SimulatedPortfolioTradingResult:
    pos_open = SimulatedPortfolioPositionResult(
        symbol="2330.TW",
        quantity=1000,
        average_cost=1234.5,
        last_price=1500.0,
        market_value=1500000.0,
        realized_pnl=10000.0,
        unrealized_pnl=265500.0,
    )
    pending_buy = SimulatedPortfolioPendingOrderResult(
        order_id="ORD_P1",
        symbol="2330.TW",
        side="BUY",
        quantity=500,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="ma_cross",
        reference_price=1400.0,
        reserved_buy_notional=700000.0,
    )
    order1 = SimulatedOrder(
        order_id="ORD_1",
        symbol="2330.TW",
        side="BUY",
        quantity=1000,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="ma_cross",
    )
    fill1 = SimulatedFill(
        order_id="ORD_1",
        symbol="2330.TW",
        side="BUY",
        quantity=1000,
        price=1234.5,
        filled_at="2026-01-02T09:00:01",
        fee=1758.0,
        tax=0.0,
        slippage=0.0,
    )
    rejection1 = SimulatedOrderRejection(
        candidate_order=SimulatedOrder(
            order_id="ORD_R1",
            symbol="2454",
            side="BUY",
            quantity=100,
            signal_time="2026-01-02\nline2|cell",
            created_at="2026-01-02T09:00:00",
            strategy="rsi",
        ),
        reasons=("風控拒絕|高風險", "額度不足\n超限"),
    )
    rec1 = SimulatedTradeLogRecord(
        sequence=2,
        record_id="REC_2",
        event_type=SimulatedTradeEventType.ACCEPTED_PENDING,
        status=SimulatedTradeStatus.PENDING_NEXT_BAR_OPEN,
        order_id="ORD_1",
        symbol="2330.TW",
        side="BUY",
        quantity=1000,
        signal_time="2026-01-02",
        order_created_at="2026-01-02T09:00:00",
        expected_execution_model="next_bar_open",
        fill_time=None,
        fill_price=None,
        fee=0.0,
        tax=0.0,
        slippage=0.0,
        strategy_name="ma_cross",
        strategy_metadata={"z_key": "val", "a_key": 10},
        risk_allowed=True,
        risk_rejection_reasons=(),
        guard_metadata={"guard": "ok"},
        error_code=None,
        error_message=None,
    )
    rec2 = SimulatedTradeLogRecord(
        sequence=1,
        record_id="REC_1",
        event_type=SimulatedTradeEventType.REJECTED,
        status=SimulatedTradeStatus.RISK_REJECTED,
        order_id="ORD_R1",
        symbol="2454",
        side="BUY",
        quantity=100,
        signal_time="2026-01-02",
        order_created_at="2026-01-02T09:00:00",
        expected_execution_model="next_bar_open",
        fill_time=None,
        fill_price=None,
        fee=0.0,
        tax=0.0,
        slippage=0.0,
        strategy_name="rsi",
        strategy_metadata={"period": 14},
        risk_allowed=False,
        risk_rejection_reasons=("Risk fail 1", "Risk fail 2"),
        guard_metadata={"limit": 50000},
        error_code="RISK_REJECTED",
        error_message="Error msg | test\nline2",
    )


    return SimulatedPortfolioTradingResult(
        initial_cash=100000.0,
        final_cash=115000.0,
        total_market_value=1500000.0,
        total_equity=1615000.0,
        realized_pnl=10000.0,
        unrealized_pnl=265500.0,
        total_return=1515000.0,
        total_return_pct=0.125,
        open_position_count=1,
        order_count=1,
        fill_count=1,
        rejection_count=1,
        audit_record_count=2,
        positions=(pos_open,),
        pending_orders=(pending_buy,),
        orders=(order1,),
        fills=(fill1,),
        rejections=(rejection1,),
        audit_log=(rec1, rec2),
    )


class TestPortfolioExporters(unittest.TestCase):

    def test_markdown_exact_empty_structure(self):
        res = _make_empty_result()
        md = export_simulated_portfolio_trading_markdown(res)

        self.assertTrue(md.startswith("# Simulated Portfolio Trading Report\n"))
        self.assertTrue(md.endswith("\n"))
        self.assertFalse(md.endswith("\n\n"))
        self.assertNotIn("\n\n\n", md)

        sections = [
            "## Summary",
            "## Positions",
            "## Pending Orders",
            "## Orders",
            "## Fills",
            "## Rejected Simulated Order Intents",
            "## Trade Log",
        ]
        last_idx = -1
        for s in sections:
            idx = md.find(s)
            self.assertGreater(idx, last_idx, f"Section {s} not found in expected order.")
            last_idx = idx

        # Exact summary table header & separator
        self.assertIn("| Metric | Value |\n|---|---:|", md)

        # Exact 14 summary labels and order
        summary_labels = [
            "Initial Cash",
            "Final Cash",
            "Total Market Value",
            "Total Equity",
            "Realized PnL",
            "Unrealized PnL",
            "Total Return",
            "Total Return %",
            "Open Position Count",
            "Pending Order Count",
            "Order Count",
            "Fill Count",
            "Rejection Count",
            "Audit Record Count",
        ]
        last_lbl_idx = -1
        for lbl in summary_labels:
            lbl_str = f"| {lbl} |"
            idx = md.find(lbl_str)
            self.assertGreater(idx, last_lbl_idx, f"Summary label {lbl} out of order.")
            last_lbl_idx = idx

        # Exact empty-section messages
        empty_messages = [
            "*No positions to display.*",
            "*No pending orders to display.*",
            "*No orders to display.*",
            "*No fills to display.*",
            "*No rejected simulated order intents.*",
            "*No audit events to display.*",
        ]
        for msg in empty_messages:
            self.assertIn(msg, md)

    def test_markdown_exact_table_headers_full_result(self):
        res = _make_full_result()
        md = export_simulated_portfolio_trading_markdown(res)

        headers = [
            "| Symbol | Quantity | Average Cost | Last Price | Market Value | Realized PnL | Unrealized PnL |\n|---|---:|---:|---:|---:|---:|---:|",
            "| Order ID | Symbol | Side | Quantity | Signal Time | Created At | Strategy | Reference Price | Reserved Buy Notional |\n|---|---|---|---:|---|---|---|---:|---:|",
            "| Order ID | Symbol | Side | Quantity | Signal Time | Created At | Strategy |\n|---|---|---|---:|---|---|---|",
            "| Order ID | Symbol | Side | Quantity | Price | Filled At | Fee | Tax | Slippage | Gross Amount | Net Cash Effect |\n|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|",
            "| Order ID | Symbol | Side | Quantity | Signal Time | Created At | Strategy | Reasons |\n|---|---|---|---:|---|---|---|---|",
            "| Sequence | Record ID | Event Type | Status | Order ID | Symbol | Side | Quantity | Signal Time | Order Created At | Expected Execution Model | Fill Time | Fill Price | Fee | Tax | Slippage | Strategy Name | Strategy Metadata | Risk Allowed | Risk Rejection Reasons | Guard Metadata | Error Code | Error Message |\n|---:|---|---|---|---|---|---|---:|---|---|---|---|---:|---:|---:|---:|---|---|---|---|---|---|---|",
        ]

        for h in headers:
            self.assertIn(h, md, f"Header block not found exactly in Markdown:\n{h}")

    def test_markdown_value_formatting_escaping_and_linebreaks(self):
        res = _make_full_result()
        md = export_simulated_portfolio_trading_markdown(res)

        # Thousand comma formatting on float (1234.5 -> 1,234.50)
        self.assertIn("1,234.50", md)

        # Percentage formatting on ratio (0.125 -> 12.50%)
        self.assertIn("| Total Return % | 12.50% |", md)

        # Escaped pipe and linebreaks in cell content
        self.assertIn(r"2026-01-02<br>line2\|cell", md)
        self.assertIn(r"風控拒絕\|高風險 \| 額度不足<br>超限", md)
        self.assertIn(r"Error msg \| test<br>line2", md)

        # No residual \r characters
        self.assertNotIn("\r", md)

        # Stable timestamp string (None renders empty string cell)
        self.assertIn("|  |  | 0.00 | 0.00 | 0.00 |", md)  # Fill time / fill price empty string cells in trade log

    def test_markdown_crlf_cr_lf_linebreaks_and_pipe_escaping(self):
        res = _make_empty_result()
        bad_order = SimulatedOrder(
            order_id="ORD_MB",
            symbol="2330",
            side="BUY",
            quantity=10,
            signal_time="crlf\r\ncr\rlf\npipe|end",
            created_at=None,
            strategy=None,
        )
        res_mb = SimulatedPortfolioTradingResult(
            initial_cash=res.initial_cash,
            final_cash=res.final_cash,
            total_market_value=res.total_market_value,
            total_equity=res.total_equity,
            realized_pnl=res.realized_pnl,
            unrealized_pnl=res.unrealized_pnl,
            total_return=res.total_return,
            total_return_pct=res.total_return_pct,
            open_position_count=0,
            order_count=1,
            fill_count=0,
            rejection_count=0,
            audit_record_count=0,
            positions=(),
            pending_orders=(),
            orders=(bad_order,),
            fills=(),
            rejections=(),
            audit_log=(),
        )
        md = export_simulated_portfolio_trading_markdown(res_mb)
        self.assertIn(r"crlf<br>cr<br>lf<br>pipe\|end", md)
        self.assertNotIn("\r", md)

    def test_markdown_metadata_deterministic_json(self):

        res = _make_full_result()
        md = export_simulated_portfolio_trading_markdown(res)

        # Sorted JSON keys
        self.assertIn('{"a_key": 10, "z_key": "val"}', md)
        self.assertIn('{"guard": "ok"}', md)

    def test_markdown_ordering_and_mutation_safety(self):
        res = _make_full_result()
        orig_audit_log = res.audit_log
        orig_rec0_strat = dict(res.audit_log[0].strategy_metadata)

        md = export_simulated_portfolio_trading_markdown(res)

        # REC_2 sequence 2 appears before REC_1 sequence 1
        rec2_idx = md.find("REC_2")
        rec1_idx = md.find("REC_1")
        self.assertGreater(rec1_idx, rec2_idx)

        # Source result and objects untouched
        self.assertIs(res.audit_log, orig_audit_log)
        self.assertEqual(dict(res.audit_log[0].strategy_metadata), orig_rec0_strat)

    def test_csv_exact_seven_headers_and_empty_datasets(self):
        empty_res = _make_empty_result()
        bundle = export_simulated_portfolio_trading_csv_bundle(empty_res)

        expected_keys = [
            "summary",
            "positions",
            "pending_orders",
            "orders",
            "fills",
            "rejections",
            "trade_log",
        ]
        self.assertEqual(list(bundle.keys()), expected_keys)

        expected_headers = {
            "summary": ["metric", "value"],
            "positions": ["symbol", "quantity", "average_cost", "last_price", "market_value", "realized_pnl", "unrealized_pnl"],
            "pending_orders": ["order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy", "reference_price", "reserved_buy_notional"],
            "orders": ["order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy"],
            "fills": ["order_id", "symbol", "side", "quantity", "price", "filled_at", "fee", "tax", "slippage", "gross_amount", "net_cash_effect"],
            "rejections": ["order_id", "symbol", "side", "quantity", "signal_time", "created_at", "strategy", "reasons"],
            "trade_log": [
                "sequence", "record_id", "event_type", "status", "order_id", "symbol", "side",
                "quantity", "signal_time", "order_created_at", "expected_execution_model", "fill_time",
                "fill_price", "fee", "tax", "slippage", "strategy_name", "strategy_metadata",
                "risk_allowed", "risk_rejection_reasons", "guard_metadata", "error_code", "error_message",
            ],
        }

        for key, exp_header in expected_headers.items():
            csv_text = bundle[key]
            rows = list(csv.reader(io.StringIO(csv_text)))
            self.assertGreaterEqual(len(rows), 1, f"CSV {key} has no header row.")
            self.assertEqual(rows[0], exp_header, f"CSV {key} header mismatch.")

            if key == "summary":
                self.assertEqual(len(rows), 15, "Empty summary CSV must contain header + 14 metrics.")
            else:
                self.assertEqual(len(rows), 1, f"Empty CSV {key} must contain header row only.")

    def test_csv_raw_values_and_formatting(self):
        res = _make_full_result()
        bundle = export_simulated_portfolio_trading_csv_bundle(res)

        summary_rows = list(csv.reader(io.StringIO(bundle["summary"])))
        summary_dict = dict(summary_rows[1:])
        self.assertEqual(summary_dict["total_return_pct"], "0.125")  # Raw ratio, no % sign
        self.assertEqual(summary_dict["initial_cash"], "100000.0")

        pos_rows = list(csv.reader(io.StringIO(bundle["positions"])))
        self.assertEqual(pos_rows[1][2], "1234.5")  # Raw float, no comma separator

        trade_log_rows = list(csv.reader(io.StringIO(bundle["trade_log"])))
        # Metadata column is index 17
        self.assertEqual(trade_log_rows[1][17], '{"a_key": 10, "z_key": "val"}')
        self.assertEqual(trade_log_rows[1][18], "True")  # bool as string

    def test_csv_newline_policy(self):
        res = _make_full_result()
        bundle = export_simulated_portfolio_trading_csv_bundle(res)

        for k, text in bundle.items():
            self.assertTrue(text.endswith("\n"), f"CSV {k} does not end with single newline.")
            self.assertFalse(text.endswith("\n\n"), f"CSV {k} ends with multiple newlines.")
            self.assertNotIn("\r\n", text, f"CSV {k} contains CRLF line endings.")
            self.assertNotIn("\r", text, f"CSV {k} contains CR line endings.")

    def test_csv_ordering_and_mutation_safety(self):
        res = _make_full_result()
        orig_audit_log = res.audit_log

        bundle = export_simulated_portfolio_trading_csv_bundle(res)

        trade_log_rows = list(csv.reader(io.StringIO(bundle["trade_log"])))
        self.assertEqual(trade_log_rows[1][0], "2")  # sequence 2 (REC_2) before sequence 1 (REC_1)
        self.assertEqual(trade_log_rows[2][0], "1")

        self.assertIs(res.audit_log, orig_audit_log)

    def test_error_normalization_invalid_result_type(self):
        invalid_inputs = [None, {}, "not_a_result", 123]
        for inp in invalid_inputs:
            with self.subTest(input=type(inp)):
                with self.assertRaises(PaperTradingModelError):
                    export_simulated_portfolio_trading_markdown(inp)  # type: ignore
                with self.assertRaises(PaperTradingModelError):
                    export_simulated_portfolio_trading_csv_bundle(inp)  # type: ignore

    def test_error_normalization_metadata_serialization_failures(self):
        # non-mapping metadata input
        with self.assertRaises(PaperTradingModelError):
            _dump_metadata("not_a_dict")  # type: ignore

        # NaN float in metadata
        with self.assertRaises(PaperTradingModelError):
            _dump_metadata({"bad_float": float("nan")})

        # Infinity float in metadata
        with self.assertRaises(PaperTradingModelError):
            _dump_metadata({"inf_float": float("inf")})

        # Non-JSON-serializable object
        with self.assertRaises(PaperTradingModelError):
            _dump_metadata({"obj": object()})

        # Circular reference metadata
        circ = {}
        circ["self"] = circ
        with self.assertRaises(PaperTradingModelError):
            _dump_metadata(circ)


if __name__ == "__main__":
    unittest.main()

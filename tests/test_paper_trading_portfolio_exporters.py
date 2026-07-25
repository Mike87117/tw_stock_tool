"""
Unit tests for portfolio report exporters (Markdown and CSV bundle).
"""

import csv
from datetime import datetime
import io
import json
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
    dt_ts = datetime(2026, 1, 2, 9, 0, 1)

    pos_open = SimulatedPortfolioPositionResult(
        symbol="ZZZ.TW",
        quantity=1000,
        average_cost=1234.5,
        last_price=1500.0,
        market_value=1500000.0,
        realized_pnl=10000.0,
        unrealized_pnl=265500.0,
    )
    pos_closed = SimulatedPortfolioPositionResult(
        symbol="AAA.TW",
        quantity=0,
        average_cost=0.0,
        last_price=None,
        market_value=0.0,
        realized_pnl=5000.0,
        unrealized_pnl=0.0,
    )

    pending_p2 = SimulatedPortfolioPendingOrderResult(
        order_id="ORD_P2",
        symbol="ZZZ.TW",
        side="BUY",
        quantity=500,
        signal_time=dt_ts,
        created_at="2026-01-02T09:00:00",
        strategy="ma_cross",
        reference_price=1400.0,
        reserved_buy_notional=700000.0,
    )
    pending_p1 = SimulatedPortfolioPendingOrderResult(
        order_id="ORD_P1",
        symbol="AAA.TW",
        side="SELL",
        quantity=200,
        signal_time="2026-01-02",
        created_at=None,
        strategy=None,
        reference_price=100.0,
        reserved_buy_notional=0.0,
    )

    order_o2 = SimulatedOrder(
        order_id="ORD_O2",
        symbol="ZZZ.TW",
        side="BUY",
        quantity=1000,
        signal_time=dt_ts,
        created_at=None,
        strategy=None,
    )
    order_o1 = SimulatedOrder(
        order_id="ORD_O1",
        symbol="AAA.TW",
        side="SELL",
        quantity=200,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="rsi",
    )

    fill_f2 = SimulatedFill(
        order_id="ORD_F2",
        symbol="ZZZ.TW",
        side="BUY",
        quantity=1000,
        price=1234.5,
        filled_at=dt_ts,
        fee=1758.0,
        tax=0.0,
        slippage=0.0,
    )
    fill_f1 = SimulatedFill(
        order_id="ORD_F1",
        symbol="AAA.TW",
        side="SELL",
        quantity=200,
        price=100.0,
        filled_at="2026-01-02T09:00:02",
        fee=28.0,
        tax=60.0,
        slippage=0.0,
    )

    rejection_r2 = SimulatedOrderRejection(
        candidate_order=SimulatedOrder(
            order_id="ORD_R2",
            symbol="ZZZ.TW",
            side="BUY",
            quantity=100,
            signal_time="2026-01-02\nline2|cell",
            created_at="2026-01-02T09:00:00",
            strategy="rsi",
        ),
        reasons=("風控拒絕|高風險", "額度不足\n超限"),
    )
    rejection_r1 = SimulatedOrderRejection(
        candidate_order=SimulatedOrder(
            order_id="ORD_R1",
            symbol="AAA.TW",
            side="SELL",
            quantity=50,
            signal_time="2026-01-02",
            created_at="2026-01-02T09:00:00",
            strategy="macd",
        ),
        reasons=("Reason B", "Reason A"),
    )

    rec2 = SimulatedTradeLogRecord(
        sequence=2,
        record_id="REC_2",
        event_type=SimulatedTradeEventType.ACCEPTED_PENDING,
        status=SimulatedTradeStatus.PENDING_NEXT_BAR_OPEN,
        order_id="ORD_O2",
        symbol="ZZZ.TW",
        side="BUY",
        quantity=1000,
        signal_time=dt_ts,
        order_created_at=dt_ts,
        expected_execution_model="next_bar_open",
        fill_time=dt_ts,
        fill_price=1234.5,
        fee=1758.0,
        tax=0.0,
        slippage=0.0,
        strategy_name="ma_cross",
        strategy_metadata={"tag": "測試", "a_key": 10},
        risk_allowed=True,
        risk_rejection_reasons=(),
        guard_metadata={"guard": "ok"},
        error_code=None,
        error_message=None,
    )
    rec1 = SimulatedTradeLogRecord(
        sequence=1,
        record_id="REC_1",
        event_type=SimulatedTradeEventType.REJECTED,
        status=SimulatedTradeStatus.RISK_REJECTED,
        order_id="ORD_R2",
        symbol="ZZZ.TW",
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
        risk_rejection_reasons=("Risk fail",),
        guard_metadata={"limit": 50000},
        error_code=None,
        error_message=None,
    )

    return SimulatedPortfolioTradingResult(
        initial_cash=100000.0,
        final_cash=115000.0,
        total_market_value=1500000.0,
        total_equity=1615000.0,
        realized_pnl=15000.0,
        unrealized_pnl=265500.0,
        total_return=1515000.0,
        total_return_pct=0.125,
        open_position_count=1,
        order_count=2,
        fill_count=2,
        rejection_count=2,
        audit_record_count=2,
        positions=(pos_open, pos_closed),
        pending_orders=(pending_p2, pending_p1),
        orders=(order_o2, order_o1),
        fills=(fill_f2, fill_f1),
        rejections=(rejection_r2, rejection_r1),
        audit_log=(rec2, rec1),
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

        # No residual \r characters
        self.assertNotIn("\r", md)

        # Stable timestamp string test with actual datetime object
        dt_str = str(datetime(2026, 1, 2, 9, 0, 1))
        self.assertIn(dt_str, md)

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

        # Sorted JSON keys and ensure_ascii=False
        self.assertIn('{"a_key": 10, "tag": "測試"}', md)
        self.assertIn('{"guard": "ok"}', md)

    def test_markdown_all_collections_ordering_and_mutation_safety(self):
        res = _make_full_result()
        orig_audit_log = res.audit_log
        orig_rec0_strat = dict(res.audit_log[0].strategy_metadata)

        md = export_simulated_portfolio_trading_markdown(res)

        # Positions table: ZZZ.TW before AAA.TW
        pos_zzz = md.find("ZZZ.TW")
        pos_aaa = md.find("AAA.TW")
        self.assertGreater(pos_aaa, pos_zzz)

        # Pending orders table: ORD_P2 before ORD_P1
        p2_idx = md.find("ORD_P2")
        p1_idx = md.find("ORD_P1")
        self.assertGreater(p1_idx, p2_idx)

        # Orders table: ORD_O2 before ORD_O1
        o2_idx = md.find("ORD_O2")
        o1_idx = md.find("ORD_O1")
        self.assertGreater(o1_idx, o2_idx)

        # Fills table: ORD_F2 before ORD_F1
        f2_idx = md.find("ORD_F2")
        f1_idx = md.find("ORD_F1")
        self.assertGreater(f1_idx, f2_idx)

        # Rejections table: ORD_R2 before ORD_R1
        r2_idx = md.find("ORD_R2")
        r1_idx = md.find("ORD_R1")
        self.assertGreater(r1_idx, r2_idx)

        # Trade Log table: REC_2 before REC_1
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

    def test_csv_raw_values_formatting_none_cells_and_unicode(self):
        res = _make_full_result()
        bundle = export_simulated_portfolio_trading_csv_bundle(res)

        # Summary raw ratio
        summary_rows = list(csv.reader(io.StringIO(bundle["summary"])))
        summary_dict = dict(summary_rows[1:])
        self.assertEqual(summary_dict["total_return_pct"], "0.125")
        self.assertEqual(summary_dict["initial_cash"], "100000.0")

        # Positions: raw float 1234.5 (no comma) & None last_price -> empty cell ""
        pos_rows = list(csv.reader(io.StringIO(bundle["positions"])))
        self.assertEqual(pos_rows[1][2], "1234.5")
        self.assertEqual(pos_rows[2][0], "AAA.TW")
        self.assertEqual(pos_rows[2][3], "")  # last_price=None -> ""

        # Pending orders: None created_at and strategy -> empty cells ""
        pending_rows = list(csv.reader(io.StringIO(bundle["pending_orders"])))
        self.assertEqual(pending_rows[2][0], "ORD_P1")
        self.assertEqual(pending_rows[2][5], "")  # created_at=None
        self.assertEqual(pending_rows[2][6], "")  # strategy=None

        # Orders: datetime stable string & None created_at/strategy -> empty cell ""
        order_rows = list(csv.reader(io.StringIO(bundle["orders"])))
        dt_str = str(datetime(2026, 1, 2, 9, 0, 1))
        self.assertEqual(order_rows[1][4], dt_str)
        self.assertEqual(order_rows[1][5], "")
        self.assertEqual(order_rows[1][6], "")

        # Fills: datetime stable string
        fill_rows = list(csv.reader(io.StringIO(bundle["fills"])))
        self.assertEqual(fill_rows[1][5], dt_str)

        # Rejections: Unicode round-trip with pipe (un-escaped) and newline (restored)
        rejection_rows = list(csv.reader(io.StringIO(bundle["rejections"])))
        self.assertEqual(rejection_rows[1][7], "風控拒絕|高風險 | 額度不足\n超限")

        # Trade log: None fill_time, fill_price, error_code, error_message -> empty cells ""
        trade_log_rows = list(csv.reader(io.StringIO(bundle["trade_log"])))

        # Row 1 (REC_2): datetime stable string, Unicode metadata JSON
        self.assertEqual(trade_log_rows[1][8], dt_str)
        self.assertEqual(trade_log_rows[1][9], dt_str)
        self.assertEqual(trade_log_rows[1][11], dt_str)
        self.assertEqual(json.loads(trade_log_rows[1][17]), {"a_key": 10, "tag": "測試"})
        self.assertEqual(trade_log_rows[1][21], "")  # error_code=None
        self.assertEqual(trade_log_rows[1][22], "")  # error_message=None

        # Row 2 (REC_1): fill_time=None, fill_price=None
        self.assertEqual(trade_log_rows[2][11], "")
        self.assertEqual(trade_log_rows[2][12], "")

    def test_csv_newline_policy(self):
        res = _make_full_result()
        bundle = export_simulated_portfolio_trading_csv_bundle(res)

        for k, text in bundle.items():
            self.assertTrue(text.endswith("\n"), f"CSV {k} does not end with single newline.")
            self.assertFalse(text.endswith("\n\n"), f"CSV {k} ends with multiple newlines.")
            self.assertNotIn("\r\n", text, f"CSV {k} contains CRLF line endings.")
            self.assertNotIn("\r", text, f"CSV {k} contains CR line endings.")

    def test_csv_all_collections_ordering_and_mutation_safety(self):
        res = _make_full_result()
        orig_audit_log = res.audit_log

        # Take full snapshot of fields & identities
        orig_pos_elems = list(res.positions)
        orig_pending_elems = list(res.pending_orders)
        orig_order_elems = list(res.orders)
        orig_fill_elems = list(res.fills)
        orig_rejection_elems = list(res.rejections)
        orig_audit_elems = list(res.audit_log)

        pos_snapshot = [(p.symbol, p.quantity, p.average_cost, p.last_price, p.market_value, p.realized_pnl, p.unrealized_pnl) for p in res.positions]
        pending_snapshot = [(po.order_id, po.symbol, po.side, po.quantity, po.signal_time, po.created_at, po.strategy, po.reference_price, po.reserved_buy_notional) for po in res.pending_orders]
        order_snapshot = [(o.order_id, o.symbol, o.side, o.quantity, o.signal_time, o.created_at, o.strategy) for o in res.orders]
        fill_snapshot = [(f.order_id, f.symbol, f.side, f.quantity, f.price, f.filled_at, f.fee, f.tax, f.slippage) for f in res.fills]
        rejection_snapshot = [(r.candidate_order, (r.candidate_order.order_id, r.candidate_order.symbol, r.candidate_order.side, r.candidate_order.quantity, r.candidate_order.signal_time, r.candidate_order.created_at, r.candidate_order.strategy), r.reasons) for r in res.rejections]
        audit_snapshot = [(rec.sequence, rec.record_id, rec.event_type, rec.status, rec.order_id, rec.symbol, rec.side, rec.quantity, rec.signal_time, rec.order_created_at, rec.expected_execution_model, rec.fill_time, rec.fill_price, rec.fee, rec.tax, rec.slippage, rec.strategy_name, dict(rec.strategy_metadata), rec.risk_allowed, rec.risk_rejection_reasons, dict(rec.guard_metadata), rec.error_code, rec.error_message) for rec in res.audit_log]

        # Execute exporters
        export_simulated_portfolio_trading_markdown(res)
        bundle = export_simulated_portfolio_trading_csv_bundle(res)

        # Verify parsed CSV rows match source tuple order exactly
        pos_rows = list(csv.reader(io.StringIO(bundle["positions"])))
        self.assertEqual([r[0] for r in pos_rows[1:]], ["ZZZ.TW", "AAA.TW"])

        pending_rows = list(csv.reader(io.StringIO(bundle["pending_orders"])))
        self.assertEqual([r[0] for r in pending_rows[1:]], ["ORD_P2", "ORD_P1"])

        order_rows = list(csv.reader(io.StringIO(bundle["orders"])))
        self.assertEqual([r[0] for r in order_rows[1:]], ["ORD_O2", "ORD_O1"])

        fill_rows = list(csv.reader(io.StringIO(bundle["fills"])))
        self.assertEqual([r[0] for r in fill_rows[1:]], ["ORD_F2", "ORD_F1"])

        rejection_rows = list(csv.reader(io.StringIO(bundle["rejections"])))
        self.assertEqual([r[0] for r in rejection_rows[1:]], ["ORD_R2", "ORD_R1"])

        trade_log_rows = list(csv.reader(io.StringIO(bundle["trade_log"])))
        self.assertEqual([r[1] for r in trade_log_rows[1:]], ["REC_2", "REC_1"])

        # Verify tuple element identities & field snapshots unchanged
        for current, original in zip(res.positions, orig_pos_elems):
            self.assertIs(current, original)
        for current, original in zip(res.pending_orders, orig_pending_elems):
            self.assertIs(current, original)
        for current, original in zip(res.orders, orig_order_elems):
            self.assertIs(current, original)
        for current, original in zip(res.fills, orig_fill_elems):
            self.assertIs(current, original)
        for current, original in zip(res.rejections, orig_rejection_elems):
            self.assertIs(current, original)
        for current, original in zip(res.audit_log, orig_audit_elems):
            self.assertIs(current, original)

        self.assertEqual([(p.symbol, p.quantity, p.average_cost, p.last_price, p.market_value, p.realized_pnl, p.unrealized_pnl) for p in res.positions], pos_snapshot)
        self.assertEqual([(po.order_id, po.symbol, po.side, po.quantity, po.signal_time, po.created_at, po.strategy, po.reference_price, po.reserved_buy_notional) for po in res.pending_orders], pending_snapshot)
        self.assertEqual([(o.order_id, o.symbol, o.side, o.quantity, o.signal_time, o.created_at, o.strategy) for o in res.orders], order_snapshot)
        self.assertEqual([(f.order_id, f.symbol, f.side, f.quantity, f.price, f.filled_at, f.fee, f.tax, f.slippage) for f in res.fills], fill_snapshot)
        self.assertEqual([(r.candidate_order, (r.candidate_order.order_id, r.candidate_order.symbol, r.candidate_order.side, r.candidate_order.quantity, r.candidate_order.signal_time, r.candidate_order.created_at, r.candidate_order.strategy), r.reasons) for r in res.rejections], rejection_snapshot)
        self.assertEqual([(rec.sequence, rec.record_id, rec.event_type, rec.status, rec.order_id, rec.symbol, rec.side, rec.quantity, rec.signal_time, rec.order_created_at, rec.expected_execution_model, rec.fill_time, rec.fill_price, rec.fee, rec.tax, rec.slippage, rec.strategy_name, dict(rec.strategy_metadata), rec.risk_allowed, rec.risk_rejection_reasons, dict(rec.guard_metadata), rec.error_code, rec.error_message) for rec in res.audit_log], audit_snapshot)

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

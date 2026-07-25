"""
Unit tests for portfolio report data builders.
"""

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
from tw_stock_tool.paper_trading.portfolio_report_data import (
    build_simulated_portfolio_fill_rows,
    build_simulated_portfolio_order_rows,
    build_simulated_portfolio_pending_order_rows,
    build_simulated_portfolio_position_rows,
    build_simulated_portfolio_rejection_rows,
    build_simulated_portfolio_trade_log_rows,
    build_simulated_portfolio_trading_report_data,
    build_simulated_portfolio_trading_summary,
)
from tw_stock_tool.paper_trading.portfolio_results import (
    SimulatedPortfolioPendingOrderResult,
    SimulatedPortfolioPositionResult,
    SimulatedPortfolioTradingResult,
)


def _make_cash_only_result() -> SimulatedPortfolioTradingResult:
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


def _make_sample_result(*, initial_cash: float = 100000.0) -> SimulatedPortfolioTradingResult:
    pos_open = SimulatedPortfolioPositionResult(
        symbol="ZZZ",
        quantity=1000,
        average_cost=500.0,
        last_price=550.0,
        market_value=550000.0,
        realized_pnl=10000.0,
        unrealized_pnl=50000.0,
    )
    pos_closed = SimulatedPortfolioPositionResult(
        symbol="AAA",
        quantity=0,
        average_cost=0.0,
        last_price=None,
        market_value=0.0,
        realized_pnl=5000.0,
        unrealized_pnl=0.0,
    )

    pending_p2 = SimulatedPortfolioPendingOrderResult(
        order_id="ORD_P2",
        symbol="ZZZ",
        side="BUY",
        quantity=500,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="ma_cross",
        reference_price=540.0,
        reserved_buy_notional=270000.0,
    )
    pending_p1 = SimulatedPortfolioPendingOrderResult(
        order_id="ORD_P1",
        symbol="AAA",
        side="SELL",
        quantity=200,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy=None,
        reference_price=900.0,
        reserved_buy_notional=0.0,
    )

    order_o2 = SimulatedOrder(
        order_id="ORD_O2",
        symbol="ZZZ",
        side="BUY",
        quantity=1000,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="ma_cross",
    )
    order_o1 = SimulatedOrder(
        order_id="ORD_O1",
        symbol="AAA",
        side="SELL",
        quantity=200,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="rsi",
    )

    fill_f2 = SimulatedFill(
        order_id="ORD_F2",
        symbol="ZZZ",
        side="BUY",
        quantity=1000,
        price=500.0,
        filled_at="2026-01-02T09:00:01",
        fee=712.0,
        tax=0.0,
        slippage=0.0,
    )
    fill_f1 = SimulatedFill(
        order_id="ORD_F1",
        symbol="AAA",
        side="SELL",
        quantity=200,
        price=100.0,
        filled_at="2026-01-02T09:00:02",
        fee=28.0,
        tax=60.0,
        slippage=0.0,
    )

    candidate_r2 = SimulatedOrder(
        order_id="ORD_R2",
        symbol="ZZZ",
        side="BUY",
        quantity=100,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="rsi",
    )
    rejection_r2 = SimulatedOrderRejection(
        candidate_order=candidate_r2,
        reasons=("Max notional exceeded", "Insufficient cash"),
    )

    candidate_r1 = SimulatedOrder(
        order_id="ORD_R1",
        symbol="AAA",
        side="SELL",
        quantity=50,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="macd",
    )
    rejection_r1 = SimulatedOrderRejection(
        candidate_order=candidate_r1,
        reasons=("Reason B", "Reason A"),
    )

    rec2 = SimulatedTradeLogRecord(
        sequence=2,
        record_id="REC_2",
        event_type=SimulatedTradeEventType.ACCEPTED_PENDING,
        status=SimulatedTradeStatus.PENDING_NEXT_BAR_OPEN,
        order_id="ORD_O2",
        symbol="ZZZ",
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
        strategy_metadata={"window": 10},
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
        symbol="ZZZ",
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
        guard_metadata={"max_notional": 50000},
        error_code="RISK_REJECTION",
        error_message="Order rejected by risk guard.",
    )

    tot_ret = 665000.0 - initial_cash
    tot_ret_pct = tot_ret / initial_cash if initial_cash > 0 else None

    return SimulatedPortfolioTradingResult(
        initial_cash=initial_cash,
        final_cash=115000.0,
        total_market_value=550000.0,
        total_equity=665000.0,
        realized_pnl=15000.0,
        unrealized_pnl=50000.0,
        total_return=tot_ret,
        total_return_pct=tot_ret_pct,
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


class TestPortfolioReportData(unittest.TestCase):

    def test_invalid_result_type_raises_model_error(self):
        builders = [
            build_simulated_portfolio_trading_summary,
            build_simulated_portfolio_position_rows,
            build_simulated_portfolio_pending_order_rows,
            build_simulated_portfolio_order_rows,
            build_simulated_portfolio_fill_rows,
            build_simulated_portfolio_rejection_rows,
            build_simulated_portfolio_trade_log_rows,
            build_simulated_portfolio_trading_report_data,
        ]
        invalid_inputs = [None, {}, "not_a_result", 12345]

        for b in builders:
            for inp in invalid_inputs:
                with self.subTest(builder=b.__name__, input=type(inp)):
                    with self.assertRaises(PaperTradingModelError):
                        b(inp)

    def test_exact_keys_order_for_all_schemas(self):
        res = _make_sample_result()
        data = build_simulated_portfolio_trading_report_data(res)

        expected_bundle_keys = [
            "summary",
            "position_rows",
            "pending_order_rows",
            "order_rows",
            "fill_rows",
            "rejection_rows",
            "trade_log_rows",
        ]
        self.assertEqual(list(data.keys()), expected_bundle_keys)

        expected_summary_keys = [
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
        self.assertEqual(list(data["summary"].keys()), expected_summary_keys)

        expected_pos_keys = [
            "symbol",
            "quantity",
            "average_cost",
            "last_price",
            "market_value",
            "realized_pnl",
            "unrealized_pnl",
        ]
        self.assertEqual(list(data["position_rows"][0].keys()), expected_pos_keys)

        expected_pending_keys = [
            "order_id",
            "symbol",
            "side",
            "quantity",
            "signal_time",
            "created_at",
            "strategy",
            "reference_price",
            "reserved_buy_notional",
        ]
        self.assertEqual(list(data["pending_order_rows"][0].keys()), expected_pending_keys)

        expected_order_keys = [
            "order_id",
            "symbol",
            "side",
            "quantity",
            "signal_time",
            "created_at",
            "strategy",
        ]
        self.assertEqual(list(data["order_rows"][0].keys()), expected_order_keys)

        expected_fill_keys = [
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
        self.assertEqual(list(data["fill_rows"][0].keys()), expected_fill_keys)

        expected_rejection_keys = [
            "order_id",
            "symbol",
            "side",
            "quantity",
            "signal_time",
            "created_at",
            "strategy",
            "reasons",
        ]
        self.assertEqual(list(data["rejection_rows"][0].keys()), expected_rejection_keys)

        expected_trade_log_keys = [
            "sequence",
            "record_id",
            "event_type",
            "status",
            "order_id",
            "symbol",
            "side",
            "quantity",
            "signal_time",
            "order_created_at",
            "expected_execution_model",
            "fill_time",
            "fill_price",
            "fee",
            "tax",
            "slippage",
            "strategy_name",
            "strategy_metadata",
            "risk_allowed",
            "risk_rejection_reasons",
            "guard_metadata",
            "error_code",
            "error_message",
        ]
        self.assertEqual(list(data["trade_log_rows"][0].keys()), expected_trade_log_keys)

    def test_empty_collections_on_cash_only_result(self):
        res = _make_cash_only_result()
        data = build_simulated_portfolio_trading_report_data(res)

        self.assertEqual(data["position_rows"], [])
        self.assertEqual(data["pending_order_rows"], [])
        self.assertEqual(data["order_rows"], [])
        self.assertEqual(data["fill_rows"], [])
        self.assertEqual(data["rejection_rows"], [])
        self.assertEqual(data["trade_log_rows"], [])
        self.assertEqual(data["summary"]["pending_order_count"], 0)

    def test_fresh_output_objects_independence(self):
        res = _make_sample_result()
        data1 = build_simulated_portfolio_trading_report_data(res)
        data2 = build_simulated_portfolio_trading_report_data(res)

        self.assertIsNot(data1, data2)
        self.assertIsNot(data1["summary"], data2["summary"])

        collection_keys = [
            "position_rows",
            "pending_order_rows",
            "order_rows",
            "fill_rows",
            "rejection_rows",
            "trade_log_rows",
        ]
        for key in collection_keys:
            self.assertIsNot(data1[key], data2[key])
            for r1, r2 in zip(data1[key], data2[key]):
                self.assertIsNot(r1, r2)

        # Mutate data1 and verify data2 and res remain untouched
        data1["summary"]["initial_cash"] = 999999.0
        self.assertEqual(data2["summary"]["initial_cash"], 100000.0)
        self.assertEqual(res.initial_cash, 100000.0)

        data1["position_rows"][0]["symbol"] = "MUTATED"
        self.assertEqual(data2["position_rows"][0]["symbol"], "ZZZ")
        self.assertEqual(res.positions[0].symbol, "ZZZ")

    def test_exact_source_order_preservation(self):
        res = _make_sample_result()
        data = build_simulated_portfolio_trading_report_data(res)

        # Positions tuple: ZZZ, AAA (natural sort would be AAA, ZZZ)
        self.assertEqual([r["symbol"] for r in data["position_rows"]], ["ZZZ", "AAA"])
        self.assertEqual([r["symbol"] for r in data["position_rows"]], [p.symbol for p in res.positions])

        # Pending orders tuple: ORD_P2, ORD_P1 (natural sort would be ORD_P1, ORD_P2)
        self.assertEqual([r["order_id"] for r in data["pending_order_rows"]], ["ORD_P2", "ORD_P1"])
        self.assertEqual([r["order_id"] for r in data["pending_order_rows"]], [po.order_id for po in res.pending_orders])

        # Orders tuple: ORD_O2, ORD_O1
        self.assertEqual([r["order_id"] for r in data["order_rows"]], ["ORD_O2", "ORD_O1"])
        self.assertEqual([r["order_id"] for r in data["order_rows"]], [o.order_id for o in res.orders])

        # Fills tuple: ORD_F2, ORD_F1
        self.assertEqual([r["order_id"] for r in data["fill_rows"]], ["ORD_F2", "ORD_F1"])
        self.assertEqual([r["order_id"] for r in data["fill_rows"]], [f.order_id for f in res.fills])

        # Rejections tuple: ORD_R2, ORD_R1
        self.assertEqual([r["order_id"] for r in data["rejection_rows"]], ["ORD_R2", "ORD_R1"])
        self.assertEqual([r["order_id"] for r in data["rejection_rows"]], [r.candidate_order.order_id for r in res.rejections])

        # Trade log tuple: sequence 2 (REC_2) before sequence 1 (REC_1)
        self.assertEqual([r["record_id"] for r in data["trade_log_rows"]], ["REC_2", "REC_1"])
        self.assertEqual([r["sequence"] for r in data["trade_log_rows"]], [2, 1])
        self.assertEqual([r["record_id"] for r in data["trade_log_rows"]], [rec.record_id for rec in res.audit_log])

    def test_metadata_and_joined_values_formatting(self):
        res = _make_sample_result()
        data = build_simulated_portfolio_trading_report_data(res)

        # Verify strategy_metadata and guard_metadata are ordinary dicts
        rec0_strat = data["trade_log_rows"][0]["strategy_metadata"]
        rec0_guard = data["trade_log_rows"][0]["guard_metadata"]
        self.assertIs(type(rec0_strat), dict)
        self.assertIs(type(rec0_guard), dict)
        self.assertIsNot(rec0_strat, res.audit_log[0].strategy_metadata)
        self.assertIsNot(rec0_guard, res.audit_log[0].guard_metadata)
        self.assertEqual(rec0_strat, {"window": 10})
        self.assertEqual(rec0_guard, {"guard": "ok"})

        # Verify joined string formatting and no reordering of reasons
        self.assertEqual(data["trade_log_rows"][1]["risk_rejection_reasons"], "Risk fail 1 | Risk fail 2")
        self.assertEqual(data["rejection_rows"][0]["reasons"], "Max notional exceeded | Insufficient cash")

        # Second rejection with non-alphabetical reasons ("Reason B", "Reason A")
        self.assertEqual(data["rejection_rows"][1]["reasons"], "Reason B | Reason A")

    def test_comprehensive_mutation_safety_and_element_identities(self):
        res = _make_sample_result()

        orig_positions_tuple = res.positions
        orig_pos_elems = list(res.positions)
        orig_pending_tuple = res.pending_orders
        orig_pending_elems = list(res.pending_orders)
        orig_orders_tuple = res.orders
        orig_order_elems = list(res.orders)
        orig_fills_tuple = res.fills
        orig_fill_elems = list(res.fills)
        orig_rejections_tuple = res.rejections
        orig_rejection_elems = list(res.rejections)
        orig_audit_tuple = res.audit_log
        orig_audit_elems = list(res.audit_log)
        orig_rec0_strat = dict(res.audit_log[0].strategy_metadata)
        orig_rec0_guard = dict(res.audit_log[0].guard_metadata)

        # Take full snapshot of fields
        pos_snapshot = [(p.symbol, p.quantity, p.average_cost, p.last_price, p.market_value, p.realized_pnl, p.unrealized_pnl) for p in res.positions]
        pending_snapshot = [(po.order_id, po.symbol, po.side, po.quantity, po.signal_time, po.created_at, po.strategy, po.reference_price, po.reserved_buy_notional) for po in res.pending_orders]
        order_snapshot = [(o.order_id, o.symbol, o.side, o.quantity, o.signal_time, o.created_at, o.strategy) for o in res.orders]
        fill_snapshot = [(f.order_id, f.symbol, f.side, f.quantity, f.price, f.filled_at, f.fee, f.tax, f.slippage) for f in res.fills]
        rejection_snapshot = [(r.candidate_order, (r.candidate_order.order_id, r.candidate_order.symbol, r.candidate_order.side, r.candidate_order.quantity, r.candidate_order.signal_time, r.candidate_order.created_at, r.candidate_order.strategy), r.reasons) for r in res.rejections]
        audit_snapshot = [(rec.sequence, rec.record_id, rec.event_type, rec.status, rec.order_id, rec.symbol, rec.side, rec.quantity, rec.signal_time, rec.order_created_at, rec.expected_execution_model, rec.fill_time, rec.fill_price, rec.fee, rec.tax, rec.slippage, rec.strategy_name, dict(rec.strategy_metadata), rec.risk_allowed, rec.risk_rejection_reasons, dict(rec.guard_metadata), rec.error_code, rec.error_message) for rec in res.audit_log]

        # Invoke all builders
        build_simulated_portfolio_trading_summary(res)
        build_simulated_portfolio_position_rows(res)
        build_simulated_portfolio_pending_order_rows(res)
        build_simulated_portfolio_order_rows(res)
        build_simulated_portfolio_fill_rows(res)
        build_simulated_portfolio_rejection_rows(res)
        build_simulated_portfolio_trade_log_rows(res)
        build_simulated_portfolio_trading_report_data(res)

        # Assert tuple identities unchanged
        self.assertIs(res.positions, orig_positions_tuple)
        self.assertIs(res.pending_orders, orig_pending_tuple)
        self.assertIs(res.orders, orig_orders_tuple)
        self.assertIs(res.fills, orig_fills_tuple)
        self.assertIs(res.rejections, orig_rejections_tuple)
        self.assertIs(res.audit_log, orig_audit_tuple)

        # Assert every single element identity unchanged via assertIs
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

        # Compare field snapshots
        self.assertEqual([(p.symbol, p.quantity, p.average_cost, p.last_price, p.market_value, p.realized_pnl, p.unrealized_pnl) for p in res.positions], pos_snapshot)
        self.assertEqual([(po.order_id, po.symbol, po.side, po.quantity, po.signal_time, po.created_at, po.strategy, po.reference_price, po.reserved_buy_notional) for po in res.pending_orders], pending_snapshot)
        self.assertEqual([(o.order_id, o.symbol, o.side, o.quantity, o.signal_time, o.created_at, o.strategy) for o in res.orders], order_snapshot)
        self.assertEqual([(f.order_id, f.symbol, f.side, f.quantity, f.price, f.filled_at, f.fee, f.tax, f.slippage) for f in res.fills], fill_snapshot)
        self.assertEqual([(r.candidate_order, (r.candidate_order.order_id, r.candidate_order.symbol, r.candidate_order.side, r.candidate_order.quantity, r.candidate_order.signal_time, r.candidate_order.created_at, r.candidate_order.strategy), r.reasons) for r in res.rejections], rejection_snapshot)
        self.assertEqual([(rec.sequence, rec.record_id, rec.event_type, rec.status, rec.order_id, rec.symbol, rec.side, rec.quantity, rec.signal_time, rec.order_created_at, rec.expected_execution_model, rec.fill_time, rec.fill_price, rec.fee, rec.tax, rec.slippage, rec.strategy_name, dict(rec.strategy_metadata), rec.risk_allowed, rec.risk_rejection_reasons, dict(rec.guard_metadata), rec.error_code, rec.error_message) for rec in res.audit_log], audit_snapshot)

        # Assert metadata content unchanged
        self.assertEqual(dict(res.audit_log[0].strategy_metadata), orig_rec0_strat)
        self.assertEqual(dict(res.audit_log[0].guard_metadata), orig_rec0_guard)


if __name__ == "__main__":
    unittest.main()

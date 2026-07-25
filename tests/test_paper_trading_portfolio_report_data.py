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


def _make_sample_result(*, initial_cash: float = 100000.0) -> SimulatedPortfolioTradingResult:
    pos_open = SimulatedPortfolioPositionResult(
        symbol="2330",
        quantity=1000,
        average_cost=500.0,
        last_price=550.0,
        market_value=550000.0,
        realized_pnl=10000.0,
        unrealized_pnl=50000.0,
    )
    pos_closed = SimulatedPortfolioPositionResult(
        symbol="2317",
        quantity=0,
        average_cost=0.0,
        last_price=None,
        market_value=0.0,
        realized_pnl=5000.0,
        unrealized_pnl=0.0,
    )

    pending_buy = SimulatedPortfolioPendingOrderResult(
        order_id="ORD_P1",
        symbol="2330",
        side="BUY",
        quantity=500,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="ma_cross",
        reference_price=540.0,
        reserved_buy_notional=270000.0,
    )
    pending_sell = SimulatedPortfolioPendingOrderResult(
        order_id="ORD_P2",
        symbol="2454",
        side="SELL",
        quantity=200,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy=None,
        reference_price=900.0,
        reserved_buy_notional=0.0,
    )

    order1 = SimulatedOrder(
        order_id="ORD_1",
        symbol="2330",
        side="BUY",
        quantity=1000,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="ma_cross",
    )

    fill1 = SimulatedFill(
        order_id="ORD_1",
        symbol="2330",
        side="BUY",
        quantity=1000,
        price=500.0,
        filled_at="2026-01-02T09:00:01",
        fee=712.0,
        tax=0.0,
        slippage=0.0,
    )

    candidate = SimulatedOrder(
        order_id="ORD_R1",
        symbol="2454",
        side="BUY",
        quantity=100,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="rsi",
    )

    rejection1 = SimulatedOrderRejection(
        candidate_order=candidate,
        reasons=("Max notional exceeded", "Insufficient cash"),
    )

    rec1 = SimulatedTradeLogRecord(
        sequence=2,
        record_id="REC_2",
        event_type=SimulatedTradeEventType.ACCEPTED_PENDING,
        status=SimulatedTradeStatus.PENDING_NEXT_BAR_OPEN,
        order_id="ORD_1",
        symbol="2330",
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
        order_count=1,
        fill_count=1,
        rejection_count=1,
        audit_record_count=2,
        positions=(pos_open, pos_closed),
        pending_orders=(pending_buy, pending_sell),
        orders=(order1,),
        fills=(fill1,),
        rejections=(rejection1,),
        audit_log=(rec1, rec2),
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

    def test_report_data_bundle_exact_keys_and_freshness(self):
        res = _make_sample_result()
        data1 = build_simulated_portfolio_trading_report_data(res)
        data2 = build_simulated_portfolio_trading_report_data(res)

        expected_keys = [
            "summary",
            "position_rows",
            "pending_order_rows",
            "order_rows",
            "fill_rows",
            "rejection_rows",
            "trade_log_rows",
        ]
        self.assertEqual(list(data1.keys()), expected_keys)
        self.assertIsNot(data1, data2)
        self.assertIsNot(data1["summary"], data2["summary"])

    def test_summary_keys_and_zero_cash_handling(self):
        res = _make_sample_result(initial_cash=100000.0)
        summary = build_simulated_portfolio_trading_summary(res)

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
        self.assertEqual(list(summary.keys()), expected_summary_keys)
        self.assertEqual(summary["pending_order_count"], 2)
        self.assertAlmostEqual(summary["total_return_pct"], 5.65)

        # Zero initial cash case
        res_zero = _make_sample_result(initial_cash=0.0)
        summary_zero = build_simulated_portfolio_trading_summary(res_zero)
        self.assertIsNone(summary_zero["total_return_pct"])

    def test_position_rows_closed_positions_and_order(self):
        res = _make_sample_result()
        rows = build_simulated_portfolio_position_rows(res)

        self.assertEqual(len(rows), 2)
        expected_pos_keys = [
            "symbol",
            "quantity",
            "average_cost",
            "last_price",
            "market_value",
            "realized_pnl",
            "unrealized_pnl",
        ]
        self.assertEqual(list(rows[0].keys()), expected_pos_keys)
        self.assertEqual(rows[0]["symbol"], "2330")
        self.assertEqual(rows[0]["quantity"], 1000)

        # Closed position retained in order
        self.assertEqual(rows[1]["symbol"], "2317")
        self.assertEqual(rows[1]["quantity"], 0)
        self.assertIsNone(rows[1]["last_price"])

    def test_pending_order_rows_buy_and_sell(self):
        res = _make_sample_result()
        rows = build_simulated_portfolio_pending_order_rows(res)

        self.assertEqual(len(rows), 2)
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
        self.assertEqual(list(rows[0].keys()), expected_pending_keys)
        self.assertEqual(rows[0]["side"], "BUY")
        self.assertEqual(rows[0]["reserved_buy_notional"], 270000.0)

        self.assertEqual(rows[1]["side"], "SELL")
        self.assertEqual(rows[1]["reserved_buy_notional"], 0.0)

    def test_orders_fills_rejections_rows(self):
        res = _make_sample_result()
        orders = build_simulated_portfolio_order_rows(res)
        fills = build_simulated_portfolio_fill_rows(res)
        rejections = build_simulated_portfolio_rejection_rows(res)

        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["order_id"], "ORD_1")

        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0]["gross_amount"], 500000.0)
        self.assertEqual(fills[0]["net_cash_effect"], -500712.0)

        self.assertEqual(len(rejections), 1)
        self.assertEqual(rejections[0]["reasons"], "Max notional exceeded | Insufficient cash")

    def test_trade_log_rows_chronology_and_no_sequence_sorting(self):
        res = _make_sample_result()
        rows = build_simulated_portfolio_trade_log_rows(res)

        self.assertEqual(len(rows), 2)
        # Verify sequence order in rows matches result.audit_log order exactly (sequence 2 before sequence 1)
        self.assertEqual(rows[0]["sequence"], 2)
        self.assertEqual(rows[0]["event_type"], "accepted_pending")
        self.assertEqual(rows[0]["status"], "pending_next_bar_open")

        self.assertEqual(rows[1]["sequence"], 1)
        self.assertEqual(rows[1]["event_type"], "rejected")
        self.assertEqual(rows[1]["status"], "risk_rejected")


        # Metadata dictionary copying
        self.assertIsNot(rows[0]["strategy_metadata"], res.audit_log[0].strategy_metadata)
        self.assertEqual(rows[0]["strategy_metadata"], {"window": 10})

    def test_mutation_safety(self):
        res = _make_sample_result()
        orig_positions = res.positions
        orig_pending = res.pending_orders
        orig_audit = res.audit_log

        build_simulated_portfolio_trading_report_data(res)

        self.assertIs(res.positions, orig_positions)
        self.assertIs(res.pending_orders, orig_pending)
        self.assertIs(res.audit_log, orig_audit)


if __name__ == "__main__":
    unittest.main()

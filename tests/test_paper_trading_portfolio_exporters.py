"""
Unit tests for portfolio report exporters (Markdown and CSV bundle).
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
        average_cost=500.0,
        last_price=550.0,
        market_value=550000.0,
        realized_pnl=10000.0,
        unrealized_pnl=50000.0,
    )
    pending_buy = SimulatedPortfolioPendingOrderResult(
        order_id="ORD_P1",
        symbol="2330.TW",
        side="BUY",
        quantity=500,
        signal_time="2026-01-02",
        created_at="2026-01-02T09:00:00",
        strategy="ma_cross",
        reference_price=540.0,
        reserved_buy_notional=270000.0,
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
        price=500.0,
        filled_at="2026-01-02T09:00:01",
        fee=712.0,
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
        risk_rejection_reasons=("Risk fail",),
        guard_metadata={"limit": 50000},
        error_code="RISK_REJECTED",
        error_message="Error msg | test",
    )

    return SimulatedPortfolioTradingResult(
        initial_cash=100000.0,
        final_cash=115000.0,
        total_market_value=550000.0,
        total_equity=665000.0,
        realized_pnl=10000.0,
        unrealized_pnl=50000.0,
        total_return=565000.0,
        total_return_pct=5.65,
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

    def test_markdown_empty_result_formatting_and_headers(self):
        res = _make_empty_result()
        md = export_simulated_portfolio_trading_markdown(res)

        self.assertTrue(md.startswith("# Simulated Portfolio Trading Report\n"))
        self.assertTrue(md.endswith("\n"))
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

    def test_markdown_full_result_escaping_multiline_and_pct(self):
        res = _make_full_result()
        md = export_simulated_portfolio_trading_markdown(res)

        # Percentage formatting
        self.assertIn("| Total Return % | 565.00% |", md)

        # Escaped pipe and multiline <br> in signal_time
        self.assertIn(r"2026-01-02<br>line2\|cell", md)

        # Escaped pipe in rejection reasons
        self.assertIn(r"風控拒絕\|高風險 \| 額度不足<br>超限", md)


        # Deterministic sorted JSON metadata
        self.assertIn('{"a_key": 10, "z_key": "val"}', md)

        # Audit chronology preserved (REC_2 sequence 2 before REC_1 sequence 1)
        rec2_idx = md.find("REC_2")
        rec1_idx = md.find("REC_1")
        self.assertGreater(rec1_idx, rec2_idx)

    def test_csv_bundle_empty_and_full_formatting(self):
        res = _make_full_result()
        bundle = export_simulated_portfolio_trading_csv_bundle(res)

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

        for k, csv_text in bundle.items():
            self.assertTrue(csv_text.endswith("\n"), f"CSV {k} does not end with newline.")

        # Check raw ratio in summary CSV
        self.assertIn("total_return_pct,5.65\n", bundle["summary"])

        # Check deterministic metadata in trade log CSV
        self.assertIn('"{""a_key"": 10, ""z_key"": ""val""}"', bundle["trade_log"])

        # Check CSV bundle on empty result retains headers
        empty_bundle = export_simulated_portfolio_trading_csv_bundle(_make_empty_result())
        self.assertEqual(list(empty_bundle.keys()), expected_keys)
        self.assertTrue(empty_bundle["positions"].startswith("symbol,quantity,average_cost"))

    def test_error_normalization_invalid_result_type(self):
        with self.assertRaises(PaperTradingModelError):
            export_simulated_portfolio_trading_markdown(None)  # type: ignore

        with self.assertRaises(PaperTradingModelError):
            export_simulated_portfolio_trading_csv_bundle({})  # type: ignore

    def test_error_normalization_non_serializable_metadata(self):
        with self.assertRaises(PaperTradingModelError):
            _dump_metadata("not_a_dict")  # type: ignore

        with self.assertRaises(PaperTradingModelError):
            _dump_metadata({"bad_float": float("nan")})

        with self.assertRaises(PaperTradingModelError):
            _dump_metadata({"bad_obj": object()})


if __name__ == "__main__":
    unittest.main()

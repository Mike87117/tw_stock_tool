import csv
import io
import unittest
from dataclasses import FrozenInstanceError

import pandas as pd

from tw_stock_tool.paper_trading.engine import run_simulated_paper_trading, run_simulated_paper_trading_result
from tw_stock_tool.paper_trading.exporters import (
    export_simulated_paper_trading_csv_bundle,
    export_simulated_paper_trading_markdown,
)
from tw_stock_tool.paper_trading.models import (
    PaperTradingModelError,
    SimulatedOrder,
    SimulatedPortfolio,
    SimulatedTradeEventType,
    SimulatedTradeLog,
    SimulatedTradeLogRecord,
    SimulatedTradeStatus,
)
from tw_stock_tool.paper_trading.runtime import SimulatedPaperTradingRuntimeState, SimulatedPendingOrderState
from tw_stock_tool.paper_trading.serialization import (
    deserialize_simulated_paper_trading_result,
    serialize_simulated_paper_trading_result,
)
from tw_stock_tool.paper_trading.stepper import process_simulated_pending_fill
from tw_stock_tool.simulated_paper_trading_guard.models import SimulatedPaperTradingGuardDecision


class TestCanonicalSimulatedTradeLog(unittest.TestCase):
    def record(self, **overrides):
        values = dict(
            sequence=1,
            record_id="audit-000001",
            event_type=SimulatedTradeEventType.CANDIDATE_CREATED,
            status=SimulatedTradeStatus.CANDIDATE,
            order_id="2330-BUY-0",
            symbol="2330",
            side="BUY",
            quantity=10,
            signal_time="2026-01-01",
            order_created_at="2026-01-01",
            strategy_name="ma_cross",
            strategy_metadata={"short_window": 5},
        )
        values.update(overrides)
        return SimulatedTradeLogRecord(**values)

    def test_model_validation_and_immutability(self):
        record = self.record()
        self.assertEqual(record.expected_execution_model, "next_bar_open")
        self.assertEqual(dict(record.strategy_metadata), {"short_window": 5})
        with self.assertRaises(FrozenInstanceError):
            record.status = SimulatedTradeStatus.FILLED
        for overrides in (
            {"symbol": ""}, {"side": "HOLD"}, {"quantity": 0},
            {"fill_price": float("nan")}, {"fee": -1.0},
            {"event_type": "candidate_created"}, {"status": "candidate"},
            {"strategy_metadata": {"bad": object()}},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(PaperTradingModelError):
                self.record(**overrides)

    def test_deterministic_sequence(self):
        log = SimulatedTradeLog()
        order = SimulatedOrder("o1", "2330", "BUY", 10, "t")
        first = log.record_event(order, SimulatedTradeEventType.CANDIDATE_CREATED, SimulatedTradeStatus.CANDIDATE)
        second = log.record_event(order, SimulatedTradeEventType.ACCEPTED_PENDING, SimulatedTradeStatus.PENDING_NEXT_BAR_OPEN)
        self.assertEqual([(r.sequence, r.record_id) for r in log.records], [(1, "audit-000001"), (2, "audit-000002")])
        self.assertEqual(first.order_id, second.order_id)

    def test_successful_guarded_next_bar_open_lifecycle(self):
        df = pd.DataFrame(
            {"Open": [100.0, 110.0], "entry_signal": [True, False], "exit_signal": [False, False]},
            index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
        )
        portfolio = run_simulated_paper_trading(
            df, "2330", 5000.0, quantity_per_trade=10, fee_rate=0.01,
            slippage_per_share=0.5, guard_decision=SimulatedPaperTradingGuardDecision.allow(metadata={"kill_switch": "clear"}),
            strategy="ma_cross", strategy_metadata={"short_window": 5, "long_window": 20},
        )
        records = portfolio.trade_log.records
        self.assertEqual([r.event_type for r in records], [
            SimulatedTradeEventType.CANDIDATE_CREATED,
            SimulatedTradeEventType.RISK_EVALUATED,
            SimulatedTradeEventType.ACCEPTED_PENDING,
            SimulatedTradeEventType.FILLED,
        ])
        fill = records[-1]
        self.assertEqual((fill.fill_time, fill.fill_price, fill.fee, fill.slippage), (df.index[1], 110.0, 11.0, 5.0))
        self.assertEqual(fill.strategy_name, "ma_cross")
        self.assertEqual(dict(fill.strategy_metadata), {"short_window": 5, "long_window": 20})
        self.assertEqual(records[1].risk_allowed, True)
        self.assertEqual(dict(records[1].guard_metadata), {"kill_switch": "clear"})

    def test_no_guard_is_explicitly_not_evaluated(self):
        df = pd.DataFrame({"Open": [10.0], "entry_signal": [True], "exit_signal": [False]})
        portfolio = run_simulated_paper_trading(df, "2330", 1000.0, quantity_per_trade=10)
        self.assertEqual(len(portfolio.trade_log.records), 2)
        self.assertEqual(portfolio.trade_log.records[-1].status, SimulatedTradeStatus.PENDING_NEXT_BAR_OPEN)
        self.assertIsNone(portfolio.trade_log.records[-1].risk_allowed)
        self.assertNotIn(SimulatedTradeEventType.RISK_EVALUATED, [r.event_type for r in portfolio.trade_log.records])

    def test_guard_rejection_is_terminal_and_complete(self):
        df = pd.DataFrame({"Open": [10.0, 11.0], "entry_signal": [True, False], "exit_signal": [False, False]})
        portfolio = run_simulated_paper_trading(
            df, "2330", 1000.0, quantity_per_trade=10,
            guard_decision=SimulatedPaperTradingGuardDecision.block(["max_order_notional"], {"kill_switch": "clear"}),
        )
        self.assertEqual(len(portfolio.trade_log.orders), 0)
        self.assertEqual(len(portfolio.trade_log.fills), 0)
        self.assertEqual(len(portfolio.trade_log.rejections), 1)
        terminal = portfolio.trade_log.records[-1]
        self.assertEqual(terminal.status, SimulatedTradeStatus.REJECTED)
        self.assertFalse(terminal.risk_allowed)
        self.assertEqual(terminal.risk_rejection_reasons, ("max_order_notional",))

    def test_invalid_open_and_portfolio_failures_are_retained(self):
        df = pd.DataFrame({"Open": [10.0, float("nan")], "entry_signal": [True, False], "exit_signal": [False, False]})
        portfolio = run_simulated_paper_trading(df, "2330", 1000.0, quantity_per_trade=10)
        skipped = portfolio.trade_log.records[-1]
        self.assertEqual(skipped.status, SimulatedTradeStatus.SKIPPED_INVALID_OPEN)
        self.assertEqual(skipped.error_code, "invalid_next_bar_open")

        df.loc[df.index[1], "Open"] = 100.0
        portfolio = run_simulated_paper_trading(df, "2330", 50.0, quantity_per_trade=10)
        failed = portfolio.trade_log.records[-1]
        self.assertEqual(failed.status, SimulatedTradeStatus.FAILED_PORTFOLIO_VALIDATION)
        self.assertIn("Insufficient simulated cash", failed.error_message)

        sell = SimulatedOrder("sell-1", "2330", "SELL", 10, "t", "t")
        state = SimulatedPaperTradingRuntimeState(SimulatedPortfolio(1000.0), {"2330": SimulatedPendingOrderState(sell, 10.0)})
        process_simulated_pending_fill(state, symbol="2330", open_price=10.0, index_label="next")
        self.assertIn("Insufficient simulated shares", state.portfolio.trade_log.records[-1].error_message)
        self.assertNotIn("2330", state.pending_orders)

    def test_schema_v3_round_trip_strictness_and_exports(self):
        df = pd.DataFrame(
            {"Open": [10.0, 11.0], "entry_signal": [True, False], "exit_signal": [False, False]},
            index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
        )
        result = run_simulated_paper_trading_result(df, "2330", 1000.0, quantity_per_trade=10, last_price=11.0)
        payload = serialize_simulated_paper_trading_result(result)
        self.assertEqual(payload["schema_version"], 3)
        restored = deserialize_simulated_paper_trading_result(payload)
        self.assertEqual(serialize_simulated_paper_trading_result(restored), payload)
        payload["audit_log"][0]["unknown"] = True
        with self.assertRaisesRegex(PaperTradingModelError, "extra fields"):
            deserialize_simulated_paper_trading_result(payload)

        markdown = export_simulated_paper_trading_markdown(result)
        self.assertIn("## Trade Log", markdown)
        bundle = export_simulated_paper_trading_csv_bundle(result)
        rows = list(csv.reader(io.StringIO(bundle["trade_log"])))
        self.assertEqual(rows[0][0:4], ["sequence", "record_id", "event_type", "status"])
        self.assertGreater(len(rows), 1)

    def test_v2_payload_loads_with_empty_audit_log(self):
        df = pd.DataFrame({"Open": [10.0], "entry_signal": [False], "exit_signal": [False]})
        payload = serialize_simulated_paper_trading_result(
            run_simulated_paper_trading_result(df, "2330", 1000.0)
        )
        payload["schema_version"] = 2
        del payload["audit_log"]
        restored = deserialize_simulated_paper_trading_result(payload)
        self.assertEqual(restored.audit_log, ())


if __name__ == "__main__":
    unittest.main()
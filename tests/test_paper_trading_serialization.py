import json
import unittest
from datetime import datetime

from tw_stock_tool.paper_trading.models import (
    SimulatedOrder,
    SimulatedFill,
    SimulatedOrderRejection,
    PaperTradingModelError,
)
from tw_stock_tool.paper_trading.results import SimulatedPaperTradingResult
from tw_stock_tool.paper_trading.serialization import (
    serialize_simulated_paper_trading_result,
    deserialize_simulated_paper_trading_result,
    export_simulated_paper_trading_result_json,
    load_simulated_paper_trading_result_json,
)
import tw_stock_tool.paper_trading


class TestPaperTradingSerialization(unittest.TestCase):
    def setUp(self) -> None:
        self.dt = datetime(2023, 1, 1, 12, 0, 0)
        self.dt_str = self.dt.isoformat()
        
        self.order1 = SimulatedOrder(
            order_id="o1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            signal_time=self.dt,
            created_at=self.dt,
            strategy="test_strategy",
            metadata={"reason": "test"}
        )
        self.fill1 = SimulatedFill(
            order_id="o1",
            symbol="2330",
            side="BUY",
            quantity=1000,
            price=100.5,
            filled_at=self.dt,
            fee=20.0,
            tax=0.0,
            slippage=0.0
        )
        self.result = SimulatedPaperTradingResult(
            symbol="2330",
            initial_cash=1000000.0,
            final_cash=899307.0,
            final_position_quantity=1000,
            average_cost=100.5,
            realized_pnl=0.0,
            unrealized_pnl=5000.0,
            total_equity=1004307.0,
            order_count=1,
            fill_count=1,
            open_position_count=1,
            orders=(self.order1,),
            fills=(self.fill1,),
            rejections=(
                SimulatedOrderRejection(
                    candidate_order=SimulatedOrder(
                        order_id="blocked-1",
                        symbol="2330",
                        side="BUY",
                        quantity=1000,
                        signal_time="2026-01-01",
                        created_at="2026-01-01",
                        strategy="unit-test-strategy",
                    ),
                    reasons=("Risk limit exceeded", "Kill switch active"),
                ),
            )
        )

    def test_serialize_to_dict(self):
        data = serialize_simulated_paper_trading_result(self.result)
        self.assertEqual(data["schema_version"], 2)
        self.assertEqual(data["result_type"], "simulated_paper_trading_result")
        
        o = data["orders"][0]
        self.assertEqual(o["metadata"], {"reason": "test"})
        self.assertEqual(o["signal_time"], self.dt_str)

        f = data["fills"][0]
        self.assertNotIn("gross_amount", f)
        self.assertNotIn("net_cash_effect", f)

        self.assertEqual(len(data["rejections"]), 1)
        self.assertEqual(data["rejections"][0]["candidate_order"]["order_id"], "blocked-1")
        self.assertEqual(data["rejections"][0]["reasons"], ["Risk limit exceeded", "Kill switch active"])

    def test_deserialize_to_result(self):
        data = serialize_simulated_paper_trading_result(self.result)
        restored = deserialize_simulated_paper_trading_result(data)
        
        self.assertEqual(restored.symbol, "2330")
        self.assertEqual(restored.orders[0].signal_time, self.dt_str)
        self.assertEqual(restored.orders[0].metadata, {"reason": "test"})
        self.assertEqual(restored.fills[0].price, 100.5)

        self.assertEqual(restored.rejections, self.result.rejections)
        self.assertEqual(restored.rejections[0].candidate_order.order_id, "blocked-1")
        self.assertEqual(restored.rejections[0].reasons, ("Risk limit exceeded", "Kill switch active"))

    def test_round_trip(self):
        # Result -> dict -> Result
        # (datetime will be strings, so we test with strings initially)
        self.result.orders[0].signal_time = self.dt_str
        self.result.orders[0].created_at = self.dt_str
        self.result.fills[0].filled_at = self.dt_str

        data = serialize_simulated_paper_trading_result(self.result)
        restored = deserialize_simulated_paper_trading_result(data)
        
        # Dataclasses with same content should be equal
        self.assertEqual(self.result, restored)

    def test_json_string_export_import(self):
        json_str = export_simulated_paper_trading_result_json(self.result)
        self.assertIsInstance(json_str, str)
        self.assertIn('"schema_version": 2', json_str)
        
        restored = load_simulated_paper_trading_result_json(json_str)
        self.assertEqual(restored.symbol, "2330")

    def test_datetime_serialization_isoformat(self):
        data = serialize_simulated_paper_trading_result(self.result)
        self.assertEqual(data["orders"][0]["signal_time"], self.dt_str)
        
    def test_deserialization_restores_as_string(self):
        data = serialize_simulated_paper_trading_result(self.result)
        restored = deserialize_simulated_paper_trading_result(data)
        self.assertIsInstance(restored.orders[0].signal_time, str)
        self.assertIsInstance(restored.orders[0].created_at, str)
        self.assertIsInstance(restored.fills[0].filled_at, str)

    def test_reject_missing_top_level_fields(self):
        data = serialize_simulated_paper_trading_result(self.result)
        del data["symbol"]
        with self.assertRaisesRegex(PaperTradingModelError, "Missing required top-level fields"):
            deserialize_simulated_paper_trading_result(data)

    def test_reject_extra_top_level_fields(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["extra"] = 123
        with self.assertRaisesRegex(PaperTradingModelError, "Extra unknown top-level fields"):
            deserialize_simulated_paper_trading_result(data)

    def test_reject_wrong_schema_version(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["schema_version"] = 3
        with self.assertRaisesRegex(PaperTradingModelError, "Unsupported schema_version: 3"):
            deserialize_simulated_paper_trading_result(data)

    def test_reject_wrong_result_type(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["result_type"] = "invalid"
        with self.assertRaisesRegex(PaperTradingModelError, "Unsupported result_type: invalid"):
            deserialize_simulated_paper_trading_result(data)

    def test_strict_v2_top_level_schema_keys(self):
        data = serialize_simulated_paper_trading_result(self.result)
        expected_keys = [
            "schema_version", "result_type", "symbol", "initial_cash",
            "final_cash", "final_position_quantity", "average_cost",
            "realized_pnl", "unrealized_pnl", "total_equity",
            "order_count", "fill_count", "open_position_count",
            "orders", "fills", "rejections"
        ]
        self.assertCountEqual(list(data.keys()), expected_keys)
        self.assertEqual(data["schema_version"], 2)
        self.assertEqual(data["result_type"], "simulated_paper_trading_result")
        self.assertIsInstance(data["orders"], list)
        self.assertIsInstance(data["fills"], list)
        self.assertIsInstance(data["rejections"], list)

    def test_strict_rejection_payload_shape(self):
        data = serialize_simulated_paper_trading_result(self.result)
        rej = data["rejections"][0]
        self.assertCountEqual(list(rej.keys()), ["candidate_order", "reasons"])
        
        cand = rej["candidate_order"]
        expected_cand_keys = [
            "order_id", "symbol", "side", "quantity",
            "signal_time", "created_at", "strategy", "metadata"
        ]
        self.assertCountEqual(list(cand.keys()), expected_cand_keys)
        
        self.assertIsInstance(rej["reasons"], list)
        self.assertIsInstance(cand["metadata"], dict)
        self.assertIsInstance(cand["quantity"], int)
        self.assertIsInstance(cand["signal_time"], str)
        self.assertIsInstance(cand["created_at"], str)

    def test_v2_round_trip_stability(self):
        data1 = serialize_simulated_paper_trading_result(self.result)
        restored = deserialize_simulated_paper_trading_result(data1)
        data2 = serialize_simulated_paper_trading_result(restored)
        self.assertEqual(data1, data2)

    def test_legacy_v1_payload_without_rejections(self):
        data = {
            "schema_version": 1,
            "result_type": "simulated_paper_trading_result",
            "symbol": "2330",
            "initial_cash": 1000000.0,
            "final_cash": 899307.0,
            "final_position_quantity": 1000,
            "average_cost": 100.5,
            "realized_pnl": 0.0,
            "unrealized_pnl": 5000.0,
            "total_equity": 1004307.0,
            "order_count": 0,
            "fill_count": 0,
            "open_position_count": 1,
            "orders": [],
            "fills": []
        }
        restored = deserialize_simulated_paper_trading_result(data)
        self.assertEqual(restored.rejections, ())

    def test_v1_payload_with_accidental_rejections_rejected(self):
        data = {
            "schema_version": 1,
            "result_type": "simulated_paper_trading_result",
            "symbol": "2330",
            "initial_cash": 1000000.0,
            "final_cash": 899307.0,
            "final_position_quantity": 1000,
            "average_cost": 100.5,
            "realized_pnl": 0.0,
            "unrealized_pnl": 5000.0,
            "total_equity": 1004307.0,
            "order_count": 0,
            "fill_count": 0,
            "open_position_count": 1,
            "orders": [],
            "fills": [],
            "rejections": []
        }
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_paper_trading_result(data)

    def test_v2_missing_rejections_behavior(self):
        data = serialize_simulated_paper_trading_result(self.result)
        del data["rejections"]
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_paper_trading_result(data)

    def test_malformed_rejections_not_a_list(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["rejections"] = "not a list"
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_paper_trading_result(data)

    def test_malformed_rejection_item_not_a_dict(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["rejections"] = ["not a dict"]
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_paper_trading_result(data)

    def test_malformed_rejection_candidate_order_missing_field(self):
        data = serialize_simulated_paper_trading_result(self.result)
        del data["rejections"][0]["candidate_order"]["quantity"]
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_paper_trading_result(data)

    def test_malformed_rejection_reasons_not_a_list(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["rejections"][0]["reasons"] = "not a list"
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_paper_trading_result(data)

    def test_malformed_rejection_candidate_order_quantity_is_fractional(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["rejections"][0]["candidate_order"]["quantity"] = 1.5
        with self.assertRaises(PaperTradingModelError):
            deserialize_simulated_paper_trading_result(data)

    def test_reject_malformed_orders(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["orders"] = "not a list"
        with self.assertRaisesRegex(PaperTradingModelError, "Field 'orders' must be a list."):
            deserialize_simulated_paper_trading_result(data)

    def test_reject_malformed_fills(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["fills"] = "not a list"
        with self.assertRaisesRegex(PaperTradingModelError, "Field 'fills' must be a list."):
            deserialize_simulated_paper_trading_result(data)
            
    def test_reject_invalid_side_values(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["orders"][0]["side"] = "HOLD"
        with self.assertRaisesRegex(PaperTradingModelError, "Invalid side: HOLD"):
            deserialize_simulated_paper_trading_result(data)

    def test_reject_non_finite_numeric_values(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["final_cash"] = float("inf")
        with self.assertRaisesRegex(PaperTradingModelError, "must be finite"):
            deserialize_simulated_paper_trading_result(data)
            
    def test_reject_bool_used_as_numeric(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["final_cash"] = True
        with self.assertRaisesRegex(PaperTradingModelError, "cannot be a boolean"):
            deserialize_simulated_paper_trading_result(data)

    def test_reject_non_dict_metadata(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["orders"][0]["metadata"] = "not a dict"
        with self.assertRaisesRegex(PaperTradingModelError, "metadata must be a dict"):
            deserialize_simulated_paper_trading_result(data)
            
    def test_reject_non_json_serializable_metadata(self):
        data = serialize_simulated_paper_trading_result(self.result)
        class CustomObj:
            pass
        data["orders"][0]["metadata"] = {"obj": CustomObj()}
        with self.assertRaisesRegex(PaperTradingModelError, "metadata is not JSON serializable"):
            deserialize_simulated_paper_trading_result(data)

    def test_public_api_exports(self):
        self.assertTrue(hasattr(tw_stock_tool.paper_trading, "serialize_simulated_paper_trading_result"))
        self.assertTrue(hasattr(tw_stock_tool.paper_trading, "deserialize_simulated_paper_trading_result"))
        self.assertTrue(hasattr(tw_stock_tool.paper_trading, "export_simulated_paper_trading_result_json"))
        self.assertTrue(hasattr(tw_stock_tool.paper_trading, "load_simulated_paper_trading_result_json"))
        
        self.assertIs(tw_stock_tool.paper_trading.serialize_simulated_paper_trading_result, serialize_simulated_paper_trading_result)

    def test_serialize_rejects_bool_top_level_numeric_field(self):
        # We need to bypass __post_init__ or mutate after init if dataclass isn't frozen,
        # but SimulatedPaperTradingResult is frozen. We can use object.__setattr__
        object.__setattr__(self.result, "initial_cash", True)
        with self.assertRaisesRegex(PaperTradingModelError, "cannot be a boolean"):
            serialize_simulated_paper_trading_result(self.result)

    def test_serialize_rejects_bool_order_quantity(self):
        self.order1.quantity = True
        with self.assertRaisesRegex(PaperTradingModelError, "cannot be a boolean"):
            serialize_simulated_paper_trading_result(self.result)

    def test_serialize_rejects_bool_fill_quantity(self):
        self.fill1.quantity = True
        with self.assertRaisesRegex(PaperTradingModelError, "cannot be a boolean"):
            serialize_simulated_paper_trading_result(self.result)

    def test_serialize_rejects_non_finite_top_level_float(self):
        object.__setattr__(self.result, "initial_cash", float("nan"))
        with self.assertRaisesRegex(PaperTradingModelError, "must be finite"):
            serialize_simulated_paper_trading_result(self.result)

    def test_serialize_rejects_non_finite_fill_price(self):
        self.fill1.price = float("inf")
        with self.assertRaisesRegex(PaperTradingModelError, "must be finite"):
            serialize_simulated_paper_trading_result(self.result)

    def test_serialize_rejects_non_dict_metadata(self):
        self.order1.metadata = "not a dict"
        with self.assertRaisesRegex(PaperTradingModelError, "metadata must be a dict"):
            serialize_simulated_paper_trading_result(self.result)

    def test_serialize_rejects_non_json_serializable_metadata(self):
        class CustomObj:
            pass
        self.order1.metadata = {"obj": CustomObj()}
        with self.assertRaisesRegex(PaperTradingModelError, "metadata is not JSON serializable"):
            serialize_simulated_paper_trading_result(self.result)

    def test_export_json_raises_paper_trading_model_error_for_non_json_serializable(self):
        # Actually already covered by serialize_rejects_non_json_serializable_metadata because
        # export calls serialize. But we can also test if we somehow bypassed serialize and went to dumps.
        class CustomObj:
            pass
        self.order1.metadata = {"obj": CustomObj()}
        with self.assertRaisesRegex(PaperTradingModelError, "metadata is not JSON serializable"):
            export_simulated_paper_trading_result_json(self.result)

    def test_export_json_does_not_allow_nan_or_infinity(self):
        # If we somehow bypassed the numeric validation (or if something returns NaN),
        # json.dumps should reject it because of allow_nan=False.
        # But we also have explicit validation in serialization.
        # We can test that export raises an error by forcing a float("nan") into a field not checked?
        # All numeric fields are checked now, but we can verify the error comes from our wrapper.
        object.__setattr__(self.result, "initial_cash", float("nan"))
        with self.assertRaises(PaperTradingModelError):
            export_simulated_paper_trading_result_json(self.result)

    def test_deserialize_rejects_fractional_top_level_int_field(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["final_position_quantity"] = 1.5
        with self.assertRaisesRegex(PaperTradingModelError, "must be an integer, got fractional value"):
            deserialize_simulated_paper_trading_result(data)

    def test_deserialize_rejects_fractional_order_quantity(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["orders"][0]["quantity"] = 1.5
        with self.assertRaisesRegex(PaperTradingModelError, "must be an integer, got fractional value"):
            deserialize_simulated_paper_trading_result(data)

    def test_deserialize_rejects_fractional_fill_quantity(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["fills"][0]["quantity"] = 1.5
        with self.assertRaisesRegex(PaperTradingModelError, "must be an integer, got fractional value"):
            deserialize_simulated_paper_trading_result(data)

    def test_serialize_rejects_fractional_top_level_int_field(self):
        object.__setattr__(self.result, "final_position_quantity", 1.5)
        with self.assertRaisesRegex(PaperTradingModelError, "must be an integer, got fractional value"):
            serialize_simulated_paper_trading_result(self.result)

    def test_serialize_rejects_fractional_order_quantity(self):
        self.order1.quantity = 1.5
        with self.assertRaisesRegex(PaperTradingModelError, "must be an integer, got fractional value"):
            serialize_simulated_paper_trading_result(self.result)

    def test_serialize_rejects_fractional_fill_quantity(self):
        self.fill1.quantity = 1.5
        with self.assertRaisesRegex(PaperTradingModelError, "must be an integer, got fractional value"):
            serialize_simulated_paper_trading_result(self.result)

    def test_deserialize_rejects_infinity_used_for_int_field_as_paper_trading_model_error(self):
        data = serialize_simulated_paper_trading_result(self.result)
        data["final_position_quantity"] = float("inf")
        with self.assertRaisesRegex(PaperTradingModelError, "finite|must be convertible"):
            deserialize_simulated_paper_trading_result(data)

    def test_serialize_rejects_infinity_used_for_int_field_as_paper_trading_model_error(self):
        object.__setattr__(self.result, "final_position_quantity", float("inf"))
        with self.assertRaisesRegex(PaperTradingModelError, "finite|must be convertible"):
            serialize_simulated_paper_trading_result(self.result)


if __name__ == "__main__":
    unittest.main()

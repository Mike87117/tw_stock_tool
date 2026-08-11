"""Strict mapping from sanitized Fubon Neo TEST observations to A2 facts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math
import re
from zoneinfo import ZoneInfo

from tw_stock_tool.broker_adapters.fubon_neo.config import (
    FUBON_NEO_BROKER_ID,
    FUBON_NEO_CURRENCY,
    FUBON_NEO_MARKET,
    FUBON_NEO_SOURCE_VERSION,
    FubonNeoTestConfig,
)
from tw_stock_tool.broker_adapters.fubon_neo.errors import (
    FubonNeoErrorCode,
    FubonNeoReadError,
)
from tw_stock_tool.broker_safety import (
    CAPABILITIES_ARTIFACT_TYPE,
    OPEN_ORDER_ARTIFACT_TYPE,
    POSITION_ARTIFACT_TYPE,
    SCHEMA_VERSION,
    AccountDataFreshness,
    BrokerCapabilities,
    BrokerEnvironment,
    BrokerOpenOrderSnapshot,
    BrokerOrderStatus,
    BrokerPositionSnapshot,
    CancelReplaceSemantics,
    FieldReliability,
    OrderSide,
    OrderType,
    SupportState,
    TimeInForce,
    TradingPermission,
)


_DECIMAL = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?\Z")
_SYMBOL = re.compile(r"\d{4}\Z")
_DATE = re.compile(r"\d{4}/\d{2}/\d{2}\Z")
_TIME = re.compile(r"\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?\Z")
_MAX_ABS_NUMBER = Decimal("1000000000000000")
_ACTIVE_STATUSES = {0, 4, 8, 10}
_TERMINAL_OR_HISTORY_STATUSES = {14, 15, 19, 20, 24, 29, 30, 34, 39, 40, 50, 90}


@dataclass(frozen=True, slots=True)
class FubonNeoCashObservation:
    cash: Decimal
    unclassified_available_balance: Decimal


def _malformed(message: str) -> FubonNeoReadError:
    return FubonNeoReadError(FubonNeoErrorCode.PROVIDER_RESPONSE_MALFORMED, message)


def _record(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _malformed("provider record must be a mapping")
    return value


def unwrap_provider_result(response: object, *, expect_list: bool) -> object:
    result = _record(response)
    if type(result.get("is_success")) is not bool:
        raise _malformed("provider result success flag is missing or malformed")
    if result["is_success"] is not True:
        raise FubonNeoReadError(
            FubonNeoErrorCode.PROVIDER_READ_FAILED,
            "provider read did not succeed",
        )
    if "data" not in result or result["data"] is None:
        raise _malformed("provider result data is missing")
    data = result["data"]
    if expect_list and type(data) is not list:
        raise _malformed("provider result data must be a list")
    if not expect_list and not isinstance(data, Mapping):
        raise _malformed("provider result data must be a mapping")
    return data


def exact_decimal(value: object, *, nonnegative: bool = False) -> Decimal:
    if type(value) is bool:
        raise _malformed("numeric value must not be bool")
    try:
        if type(value) is Decimal:
            parsed = value
        elif type(value) is int:
            parsed = Decimal(value)
        elif type(value) is float:
            if not math.isfinite(value):
                raise _malformed("numeric value must be finite")
            parsed = Decimal(str(value))
        elif type(value) is str and _DECIMAL.fullmatch(value) is not None:
            parsed = Decimal(value)
        else:
            raise _malformed("numeric value has unsupported syntax or type")
    except InvalidOperation as exc:
        raise _malformed("numeric value is malformed") from exc
    if not parsed.is_finite() or abs(parsed) > _MAX_ABS_NUMBER:
        raise _malformed("numeric value is nonfinite or outside the reviewed range")
    if nonnegative and parsed < 0:
        raise _malformed("numeric value must be non-negative")
    return parsed


def _exact_int(record: Mapping[str, object], name: str, *, positive: bool = False) -> int:
    value = record.get(name)
    if type(value) is not int or value < (1 if positive else 0):
        raise _malformed(f"{name} must be an exact non-negative integer")
    if value > int(_MAX_ABS_NUMBER):
        raise _malformed(f"{name} is outside the reviewed range")
    return value


def _provider_date(value: object) -> datetime:
    if type(value) is not str or _DATE.fullmatch(value) is None:
        raise _malformed("provider date must be complete YYYY/MM/DD")
    try:
        return datetime.strptime(value, "%Y/%m/%d")
    except ValueError as exc:
        raise _malformed("provider date is not a real calendar date") from exc


def _canonical_timestamp(date: object, clock: object) -> str:
    parsed_date = _provider_date(date)
    if type(clock) is not str or _TIME.fullmatch(clock) is None:
        raise _malformed("provider time must be complete to seconds")
    try:
        parsed_time = datetime.strptime(
            clock,
            "%H:%M:%S.%f" if "." in clock else "%H:%M:%S",
        ).time()
    except ValueError as exc:
        raise _malformed("provider time is invalid") from exc
    local = datetime.combine(parsed_date.date(), parsed_time, ZoneInfo("Asia/Taipei"))
    return local.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _retrieval_local_date(retrieved_at: str) -> datetime:
    try:
        parsed = datetime.strptime(retrieved_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as exc:
        raise _malformed("retrieved_at must be canonical UTC seconds") from exc
    return parsed.astimezone(ZoneInfo("Asia/Taipei")).replace(tzinfo=None)


def _verify_identity(record: Mapping[str, object], config: FubonNeoTestConfig) -> None:
    if not config.matches_provider_account(record.get("account"), record.get("branch_no")):
        raise FubonNeoReadError(
            FubonNeoErrorCode.ACCOUNT_IDENTITY_MISMATCH,
            "provider account identity does not match the runtime binding",
        )


def _symbol(record: Mapping[str, object]) -> str:
    if "canonical_symbol" in record or "symbol_override" in record:
        raise FubonNeoReadError(
            FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
            "provider-symbol overrides are not accepted",
        )
    value = record.get("stock_no")
    if type(value) is not str or _SYMBOL.fullmatch(value) is None:
        raise _malformed("stock_no is not a reviewed Taiwan securities identifier")
    if record.get("market") not in (None, "TAIEX", "TAISDAQ"):
        raise FubonNeoReadError(
            FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
            "provider market is outside the reviewed listed/OTC securities scope",
        )
    if record.get("market_type") not in (None, "Common"):
        raise FubonNeoReadError(
            FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
            "provider session or lot type is outside the reviewed common-lot scope",
        )
    return value


def map_capabilities(*, capability_snapshot_id: str, observed_at: str) -> BrokerCapabilities:
    return BrokerCapabilities(
        schema_version=SCHEMA_VERSION,
        artifact_type=CAPABILITIES_ARTIFACT_TYPE,
        capability_snapshot_id=capability_snapshot_id,
        broker_id=FUBON_NEO_BROKER_ID,
        environment=BrokerEnvironment.SANDBOX,
        market=FUBON_NEO_MARKET,
        currency=FUBON_NEO_CURRENCY,
        client_order_id_support=SupportState.UNKNOWN,
        client_order_id_max_length=None,
        query_by_client_id_support=SupportState.UNKNOWN,
        fractional_quantity_support=SupportState.UNKNOWN,
        supported_order_types=(OrderType.LIMIT, OrderType.MARKET),
        supported_time_in_force=(TimeInForce.DAY, TimeInForce.FOK, TimeInForce.IOC),
        partial_fill_reporting=SupportState.SUPPORTED,
        cancel_replace_semantics=CancelReplaceSemantics.UNKNOWN,
        account_data_freshness=AccountDataFreshness.POLLING,
        trading_permission=TradingPermission.UNKNOWN,
        short_selling_support=SupportState.UNKNOWN,
        borrow_availability_support=SupportState.UNKNOWN,
        fee_estimate_support=SupportState.UNKNOWN,
        observed_at=observed_at,
        source_version=FUBON_NEO_SOURCE_VERSION,
    )


def map_cash(data: object, config: FubonNeoTestConfig) -> FubonNeoCashObservation:
    record = _record(data)
    _verify_identity(record, config)
    if record.get("currency") != FUBON_NEO_CURRENCY:
        raise FubonNeoReadError(
            FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
            "provider currency is outside the reviewed TWD scope",
        )
    if "balance" not in record:
        raise FubonNeoReadError(
            FubonNeoErrorCode.MANDATORY_ACCOUNT_FIELD_UNAVAILABLE,
            "the documented cash observation is incomplete",
        )
    if "available_balance" not in record:
        raise _malformed("the documented available balance observation is missing")
    # v2.2.8 documents balance as bank balance; available_balance stays unclassified.
    return FubonNeoCashObservation(
        cash=exact_decimal(record["balance"]),
        unclassified_available_balance=exact_decimal(
            record["available_balance"], nonnegative=True
        ),
    )


def _validate_observation_date(record: Mapping[str, object], retrieved_at: str) -> None:
    observed = _provider_date(record.get("date"))
    if observed.date() != _retrieval_local_date(retrieved_at).date():
        raise _malformed("provider observation date does not match retrieval date")


def map_positions(
    inventory_data: object,
    unrealized_data: object,
    config: FubonNeoTestConfig,
    *,
    retrieved_at: str,
) -> tuple[BrokerPositionSnapshot, ...]:
    if type(inventory_data) is not list or type(unrealized_data) is not list:
        raise _malformed("position inputs must be provider lists")
    inventories: dict[tuple[str, str], tuple[Mapping[str, object], int, int]] = {}
    for item in inventory_data:
        record = _record(item)
        _verify_identity(record, config)
        _validate_observation_date(record, retrieved_at)
        symbol = _symbol(record)
        if record.get("order_type") != "Stock":
            raise FubonNeoReadError(
                FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
                "non-cash securities inventory cannot be represented losslessly",
            )
        odd = record.get("odd")
        if odd is not None:
            odd_record = _record(odd)
            if any(_exact_int(odd_record, name) != 0 for name in (
                "lastday_qty", "buy_qty", "buy_filled_qty", "buy_value",
                "today_qty", "tradable_qty", "sell_qty", "sell_filled_qty", "sell_value",
            )):
                raise FubonNeoReadError(
                    FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
                    "odd-lot inventory is outside the reviewed common-lot scope",
                )
        quantities = {
            name: _exact_int(record, name)
            for name in (
                "lastday_qty", "buy_qty", "buy_filled_qty", "today_qty",
                "tradable_qty", "sell_qty", "sell_filled_qty",
            )
        }
        _exact_int(record, "buy_value")
        _exact_int(record, "sell_value")
        if (
            quantities["buy_filled_qty"] > quantities["buy_qty"]
            or quantities["sell_filled_qty"] > quantities["sell_qty"]
            or quantities["today_qty"]
            != quantities["lastday_qty"]
            + quantities["buy_filled_qty"]
            - quantities["sell_filled_qty"]
            or quantities["tradable_qty"] > quantities["today_qty"]
        ):
            raise _malformed("inventory quantities are contradictory")
        key = (symbol, "Stock")
        if key in inventories:
            raise FubonNeoReadError(
                FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS,
                "duplicate canonical inventory records are ambiguous",
            )
        inventories[key] = (record, quantities["today_qty"], quantities["tradable_qty"])

    pnl_by_key: dict[tuple[str, str], Mapping[str, object]] = {}
    for item in unrealized_data:
        record = _record(item)
        _verify_identity(record, config)
        _validate_observation_date(record, retrieved_at)
        symbol = _symbol(record)
        if record.get("order_type") != "Stock" or record.get("buy_sell") != "Buy":
            raise FubonNeoReadError(
                FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
                "unrealized record is outside the reviewed cash-long scope",
            )
        key = (symbol, "Stock")
        if key in pnl_by_key:
            raise FubonNeoReadError(
                FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS,
                "duplicate unrealized records are ambiguous",
            )
        pnl_by_key[key] = record
    if not set(pnl_by_key).issubset(inventories):
        raise FubonNeoReadError(
            FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS,
            "unrealized records do not join uniquely to inventory",
        )

    positions: list[BrokerPositionSnapshot] = []
    for key, (_, quantity, available) in inventories.items():
        pnl = pnl_by_key.get(key)
        average_cost = None
        unrealized_pnl = None
        average_reliability = FieldReliability.UNAVAILABLE
        pnl_reliability = FieldReliability.UNAVAILABLE
        if pnl is not None:
            pnl_quantity = _exact_int(pnl, "today_qty")
            pnl_available = _exact_int(pnl, "tradable_qty")
            if pnl_quantity != quantity or pnl_available != available:
                raise FubonNeoReadError(
                    FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS,
                    "inventory and unrealized quantities contradict",
                )
            average_cost = exact_decimal(pnl.get("cost_price"), nonnegative=True)
            profit = exact_decimal(pnl.get("unrealized_profit"), nonnegative=True)
            loss = exact_decimal(pnl.get("unrealized_loss"), nonnegative=True)
            unrealized_pnl = profit - loss
            average_reliability = FieldReliability.RELIABLE
            pnl_reliability = FieldReliability.RELIABLE
        positions.append(
            BrokerPositionSnapshot(
                schema_version=SCHEMA_VERSION,
                artifact_type=POSITION_ARTIFACT_TYPE,
                canonical_symbol=key[0],
                broker_symbol=key[0],
                quantity=Decimal(quantity),
                available_quantity=Decimal(available),
                average_cost=average_cost,
                average_cost_reliability=average_reliability,
                market_value=None,
                market_value_reliability=FieldReliability.UNAVAILABLE,
                realized_pnl=None,
                realized_pnl_reliability=FieldReliability.UNAVAILABLE,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_reliability=pnl_reliability,
                as_of=retrieved_at,
            )
        )
    return tuple(sorted(positions, key=lambda item: item.canonical_symbol))


def _map_open_order(
    record: Mapping[str, object],
    config: FubonNeoTestConfig,
    *,
    retrieved_at: str,
) -> BrokerOpenOrderSnapshot:
    _verify_identity(record, config)
    _validate_observation_date(record, retrieved_at)
    if _exact_int(record, "asset_type") != 0:
        raise FubonNeoReadError(
            FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
            "non-securities order record is outside scope",
        )
    symbol = _symbol(record)
    if record.get("order_type") != "Stock":
        raise FubonNeoReadError(
            FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
            "non-cash securities order cannot be represented losslessly",
        )
    if type(record.get("is_pre_order")) is not bool:
        raise _malformed("is_pre_order must be an exact bool")
    function_type = record.get("function_type")
    if function_type is not None and (type(function_type) is not int or function_type not in (0, 10)):
        raise FubonNeoReadError(
            FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
            "change-log order rows are not current exposure records",
        )
    order_no = record.get("order_no")
    if type(order_no) is not str or not order_no or order_no.strip() != order_no:
        raise _malformed("active order requires a stable broker order number")
    original = _exact_int(record, "quantity", positive=True)
    effective = _exact_int(record, "after_qty", positive=True)
    filled = _exact_int(record, "filled_qty")
    _exact_int(record, "unit", positive=True)
    if original != effective or filled > original:
        raise _malformed("order quantities cannot be represented by exact A2 accounting")
    side = {"Buy": OrderSide.BUY, "Sell": OrderSide.SELL}.get(record.get("buy_sell"))
    if side is None:
        raise FubonNeoReadError(
            FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
            "provider side is unknown",
        )
    price_type = record.get("after_price_type") or record.get("price_type")
    order_type = {"Limit": OrderType.LIMIT, "Market": OrderType.MARKET}.get(price_type)
    if order_type is None:
        raise FubonNeoReadError(
            FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
            "provider price type is not losslessly supported",
        )
    for name in ("price", "after_price"):
        value = record.get(name)
        if value is not None:
            parsed_price = exact_decimal(value, nonnegative=True)
            if order_type is OrderType.LIMIT and parsed_price <= 0:
                raise _malformed("limit price must be positive")
    time_in_force = {
        "ROD": TimeInForce.DAY,
        "FOK": TimeInForce.FOK,
        "IOC": TimeInForce.IOC,
    }.get(record.get("time_in_force"))
    if time_in_force is None:
        raise FubonNeoReadError(
            FubonNeoErrorCode.UNSUPPORTED_PROVIDER_RECORD,
            "provider time-in-force is unknown",
        )
    status_code = record.get("status")
    if status_code == 0:
        status = BrokerOrderStatus.PENDING_SUBMIT
    elif filled == 0:
        status = BrokerOrderStatus.OPEN
    elif filled < original:
        status = BrokerOrderStatus.PARTIALLY_FILLED
    else:
        raise _malformed("active provider status contradicts fully filled quantity")
    updated_at = _canonical_timestamp(record.get("date"), record.get("last_time"))
    return BrokerOpenOrderSnapshot(
        schema_version=SCHEMA_VERSION,
        artifact_type=OPEN_ORDER_ARTIFACT_TYPE,
        broker_order_id=order_no,
        client_order_id=None,
        economic_intent_id=None,
        canonical_symbol=symbol,
        broker_symbol=symbol,
        side=side,
        order_type=order_type,
        time_in_force=time_in_force,
        original_quantity=Decimal(original),
        cumulative_filled_quantity=Decimal(filled),
        remaining_quantity=Decimal(original - filled),
        status=status,
        submitted_at=updated_at,
        last_broker_update=updated_at,
        fees=None,
        taxes=None,
    )


def map_open_orders(
    data: object,
    config: FubonNeoTestConfig,
    *,
    retrieved_at: str,
) -> tuple[BrokerOpenOrderSnapshot, ...]:
    if type(data) is not list:
        raise _malformed("order input must be a provider list")
    active: dict[str, BrokerOpenOrderSnapshot] = {}
    terminal_ids: set[str] = set()
    for item in data:
        record = _record(item)
        _verify_identity(record, config)
        status = record.get("status")
        if type(status) is not int:
            raise FubonNeoReadError(
                FubonNeoErrorCode.PROVIDER_STATUS_UNKNOWN,
                "provider order status is missing or unknown",
            )
        if status == 9 or status not in _ACTIVE_STATUSES | _TERMINAL_OR_HISTORY_STATUSES:
            raise FubonNeoReadError(
                FubonNeoErrorCode.PROVIDER_STATUS_UNKNOWN,
                "provider order status is not safe to classify",
            )
        order_no = record.get("order_no")
        if status in _TERMINAL_OR_HISTORY_STATUSES:
            if type(order_no) is str and order_no:
                terminal_ids.add(order_no)
            continue
        mapped = _map_open_order(record, config, retrieved_at=retrieved_at)
        prior = active.get(mapped.broker_order_id)
        if prior is not None and prior != mapped:
            raise FubonNeoReadError(
                FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS,
                "duplicate broker order number has conflicting current facts",
            )
        active[mapped.broker_order_id] = mapped
    if terminal_ids & set(active):
        raise FubonNeoReadError(
            FubonNeoErrorCode.AMBIGUOUS_PROVIDER_RECORDS,
            "broker order number has both terminal and active records",
        )
    return tuple(sorted(active.values(), key=lambda item: item.broker_order_id))


__all__ = [
    "FubonNeoCashObservation",
    "exact_decimal",
    "map_capabilities",
    "map_cash",
    "map_open_orders",
    "map_positions",
    "unwrap_provider_result",
]

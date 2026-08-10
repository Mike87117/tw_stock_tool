"""Pure reconciliation, preflight, and conservative limit evaluation."""

from __future__ import annotations

from decimal import Decimal

from tw_stock_tool.broker_safety.models import (
    RECONCILIATION_ARTIFACT_TYPE,
    SCHEMA_VERSION,
    BrokerAccountSnapshot,
    BrokerLimitRequest,
    BrokerLocalExpectation,
    BrokerReconciliationResult,
    BrokerSafetyFinding,
    BrokerSafetyModelError,
    BrokerSafetyPolicy,
    CapabilityName,
    FieldReliability,
    FindingCode,
    FindingSeverity,
    FindingSubjectType,
    OrderSide,
    PermissionState,
    SupportState,
    TradingPermission,
    TradingSessionSnapshot,
    TradingSessionState,
    _timestamp,
)


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _text(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is Decimal:
        return _decimal_text(value)
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _finding(
    code: FindingCode,
    subject_type: FindingSubjectType,
    subject_id: str,
    *,
    observed: object = None,
    expected: object = None,
    message: str,
) -> BrokerSafetyFinding:
    return BrokerSafetyFinding(
        code=code,
        severity=FindingSeverity.ERROR,
        subject_type=subject_type,
        subject_id=subject_id,
        observed=_text(observed),
        expected=_text(expected),
        message=message,
        blocking=True,
    )


def _finding_key(item: BrokerSafetyFinding) -> tuple[str, ...]:
    return (
        item.code.value,
        item.subject_type.value,
        item.subject_id,
        item.observed or "",
        item.expected or "",
        item.message,
    )


def _ordered(findings: list[BrokerSafetyFinding]) -> tuple[BrokerSafetyFinding, ...]:
    unique = {_finding_key(item): item for item in findings}
    return tuple(unique[key] for key in sorted(unique))


def _economic_conflict(expected, observed) -> bool:
    expected_broker_order_id = getattr(expected, "broker_order_id", None)
    return (
        (
            expected_broker_order_id is not None
            and expected_broker_order_id != observed.broker_order_id
        )
        or expected.economic_intent_id != observed.economic_intent_id
        or expected.canonical_symbol != observed.canonical_symbol
        or expected.side is not observed.side
        or expected.original_quantity != observed.original_quantity
    )


def reconcile_broker_account(
    snapshot: BrokerAccountSnapshot,
    expectation: BrokerLocalExpectation,
    *,
    reconciliation_id: str,
    completed_at: str,
) -> BrokerReconciliationResult:
    """Compare broker observations with local expectations without repairing either."""
    if type(snapshot) is not BrokerAccountSnapshot:
        raise BrokerSafetyModelError("snapshot must be exact BrokerAccountSnapshot")
    if type(expectation) is not BrokerLocalExpectation:
        raise BrokerSafetyModelError("expectation must be exact BrokerLocalExpectation")
    if _timestamp("completed_at", completed_at) < _timestamp(
        "snapshot.retrieved_at", snapshot.retrieved_at
    ):
        raise BrokerSafetyModelError("reconciliation cannot complete before retrieval")

    findings: list[BrokerSafetyFinding] = []
    identities = (
        ("account_reference", snapshot.account_reference, expectation.account_reference),
        ("broker_id", snapshot.broker_id, expectation.broker_id),
        ("environment", snapshot.environment, expectation.environment),
    )
    for name, observed, expected in identities:
        if observed != expected:
            findings.append(
                _finding(
                    FindingCode.IDENTITY_MISMATCH,
                    FindingSubjectType.ACCOUNT,
                    snapshot.account_reference,
                    observed=observed,
                    expected=expected,
                    message=f"broker account {name} differs from local expectation",
                )
            )

    observed_positions = {item.canonical_symbol: item for item in snapshot.positions}
    expected_positions = {item.canonical_symbol: item for item in expectation.expected_positions}
    for symbol in sorted(set(observed_positions) | set(expected_positions)):
        observed = observed_positions.get(symbol)
        expected = expected_positions.get(symbol)
        if observed is None or expected is None or observed.quantity != expected.quantity:
            findings.append(
                _finding(
                    FindingCode.POSITION_MISMATCH,
                    FindingSubjectType.POSITION,
                    symbol,
                    observed=None if observed is None else observed.quantity,
                    expected=None if expected is None else expected.quantity,
                    message="broker position quantity differs from local expectation",
                )
            )

    by_broker_id = {item.broker_order_id: item for item in snapshot.open_orders}
    by_client_id = {
        item.client_order_id: item
        for item in snapshot.open_orders
        if item.client_order_id is not None
    }
    matched_broker_ids: set[str] = set()
    for expected in expectation.expected_open_orders:
        observed = (
            by_client_id.get(expected.client_order_id)
            if expected.client_order_id is not None
            else by_broker_id.get(expected.broker_order_id)
        )
        subject_id = expected.client_order_id or expected.broker_order_id or "missing-order-id"
        if observed is None:
            findings.append(
                _finding(
                    FindingCode.UNRESOLVED_LOCAL_ORDER,
                    FindingSubjectType.OPEN_ORDER,
                    subject_id,
                    expected=expected.economic_intent_id,
                    message="expected local open order is absent from broker observations",
                )
            )
            continue
        matched_broker_ids.add(observed.broker_order_id)
        if _economic_conflict(expected, observed):
            findings.append(
                _finding(
                    FindingCode.CLIENT_ORDER_ID_CONFLICT,
                    FindingSubjectType.OPEN_ORDER,
                    subject_id,
                    observed=observed.economic_intent_id,
                    expected=expected.economic_intent_id,
                    message="client order ID maps to conflicting economic facts",
                )
            )

    for expected in expectation.expected_nonterminal_submissions:
        observed = by_client_id.get(expected.client_order_id)
        if observed is None:
            findings.append(
                _finding(
                    FindingCode.UNRESOLVED_SUBMISSION,
                    FindingSubjectType.SUBMISSION,
                    expected.local_submission_id,
                    expected=expected.client_order_id,
                    message="nonterminal local submission has no broker-correlated order",
                )
            )
            continue
        matched_broker_ids.add(observed.broker_order_id)
        if _economic_conflict(expected, observed):
            findings.append(
                _finding(
                    FindingCode.CLIENT_ORDER_ID_CONFLICT,
                    FindingSubjectType.SUBMISSION,
                    expected.local_submission_id,
                    observed=observed.economic_intent_id,
                    expected=expected.economic_intent_id,
                    message="submission client order ID maps to conflicting economic facts",
                )
            )

    for order in snapshot.open_orders:
        if order.broker_order_id not in matched_broker_ids:
            findings.append(
                _finding(
                    FindingCode.UNKNOWN_BROKER_OPEN_ORDER,
                    FindingSubjectType.OPEN_ORDER,
                    order.broker_order_id,
                    observed=order.client_order_id,
                    message="broker open order is not known to local state",
                )
            )

    ordered = _ordered(findings)
    return BrokerReconciliationResult(
        schema_version=SCHEMA_VERSION,
        artifact_type=RECONCILIATION_ARTIFACT_TYPE,
        reconciliation_id=reconciliation_id,
        snapshot_id=snapshot.snapshot_id,
        local_state_version=expectation.local_state_version,
        account_reference=snapshot.account_reference,
        broker_id=snapshot.broker_id,
        environment=snapshot.environment,
        findings=ordered,
        completed_at=completed_at,
        is_reconciled=not any(item.blocking for item in ordered),
    )


def evaluate_broker_preflight(
    account: BrokerAccountSnapshot,
    session: TradingSessionSnapshot,
    policy: BrokerSafetyPolicy,
    reconciliation: BrokerReconciliationResult,
    *,
    evaluated_at: str,
) -> tuple[BrokerSafetyFinding, ...]:
    """Evaluate observations and freshness only; this never authorizes an order."""
    for name, value, expected in (
        ("account", account, BrokerAccountSnapshot),
        ("session", session, TradingSessionSnapshot),
        ("policy", policy, BrokerSafetyPolicy),
        ("reconciliation", reconciliation, BrokerReconciliationResult),
    ):
        if type(value) is not expected:
            raise BrokerSafetyModelError(f"{name} must be exact {expected.__name__}")
    evaluated = _timestamp("evaluated_at", evaluated_at)
    findings: list[BrokerSafetyFinding] = []

    allowlist_checks = (
        (account.broker_id, policy.allowed_broker_ids, FindingCode.BROKER_NOT_ALLOWED, "broker"),
        (account.account_reference, policy.allowed_account_references, FindingCode.ACCOUNT_NOT_ALLOWED, "account"),
        (account.environment, policy.allowed_environments, FindingCode.ENVIRONMENT_NOT_ALLOWED, "environment"),
        (account.capabilities.market, policy.allowed_markets, FindingCode.MARKET_NOT_ALLOWED, "market"),
    )
    for observed, allowed, code, label in allowlist_checks:
        if observed not in allowed:
            findings.append(
                _finding(
                    code,
                    FindingSubjectType.POLICY,
                    policy.policy_id,
                    observed=observed,
                    expected=",".join(item.value if hasattr(item, "value") else item for item in allowed) or "none",
                    message=f"{label} is not explicitly allowed by safety policy",
                )
            )

    if account.currency != policy.currency or account.capabilities.currency != policy.currency:
        findings.append(
            _finding(
                FindingCode.CURRENCY_MISMATCH,
                FindingSubjectType.ACCOUNT,
                account.account_reference,
                observed=account.currency,
                expected=policy.currency,
                message="account/capability currency differs from policy currency",
            )
        )
    if session.market != account.capabilities.market:
        findings.append(
            _finding(
                FindingCode.IDENTITY_MISMATCH,
                FindingSubjectType.SESSION,
                session.session_snapshot_id,
                observed=session.market,
                expected=account.capabilities.market,
                message="session market differs from account capability market",
            )
        )

    for capability in policy.required_capabilities:
        state = account.capabilities.capability_state(capability)
        if state is not SupportState.SUPPORTED:
            findings.append(
                _finding(
                    FindingCode.CAPABILITY_UNKNOWN
                    if state is SupportState.UNKNOWN
                    else FindingCode.CAPABILITY_UNSUPPORTED,
                    FindingSubjectType.CAPABILITY,
                    capability.value,
                    observed=state,
                    expected=SupportState.SUPPORTED,
                    message="required broker capability is not proven supported",
                )
            )
    unsupported_policy_types = tuple(
        item for item in policy.allowed_order_types if item not in account.capabilities.supported_order_types
    )
    for order_type in unsupported_policy_types:
        findings.append(
            _finding(
                FindingCode.CAPABILITY_UNSUPPORTED,
                FindingSubjectType.CAPABILITY,
                order_type.value,
                observed="not-supported",
                expected="supported",
                message="policy allows an order type absent from broker capabilities",
            )
        )

    if account.capabilities.trading_permission is TradingPermission.UNKNOWN:
        findings.append(
            _finding(
                FindingCode.TRADING_PERMISSION_UNKNOWN,
                FindingSubjectType.CAPABILITY,
                CapabilityName.TRADING_PERMISSION.value,
                observed=TradingPermission.UNKNOWN,
                expected=TradingPermission.ENABLED,
                message="broker trading permission is unknown",
            )
        )
    elif account.capabilities.trading_permission is TradingPermission.DISABLED:
        findings.append(
            _finding(
                FindingCode.TRADING_PERMISSION_DISABLED,
                FindingSubjectType.CAPABILITY,
                CapabilityName.TRADING_PERMISSION.value,
                observed=TradingPermission.DISABLED,
                expected=TradingPermission.ENABLED,
                message="broker trading permission is disabled",
            )
        )

    snapshot_age = (evaluated - _timestamp("account.retrieved_at", account.retrieved_at)).total_seconds()
    if snapshot_age < 0 or snapshot_age >= policy.snapshot_ttl_seconds:
        findings.append(
            _finding(
                FindingCode.SNAPSHOT_STALE,
                FindingSubjectType.ACCOUNT,
                account.snapshot_id,
                observed=str(int(snapshot_age)),
                expected=f"<{policy.snapshot_ttl_seconds}",
                message="account snapshot is stale at the frozen TTL boundary",
            )
        )
    capability_age = (
        evaluated
        - _timestamp("capabilities.observed_at", account.capabilities.observed_at)
    ).total_seconds()
    if capability_age < 0 or capability_age >= policy.snapshot_ttl_seconds:
        findings.append(
            _finding(
                FindingCode.SNAPSHOT_STALE,
                FindingSubjectType.CAPABILITY,
                account.capabilities.capability_snapshot_id,
                observed=str(int(capability_age)),
                expected=f"<{policy.snapshot_ttl_seconds}",
                message="capability snapshot is stale at the frozen TTL boundary",
            )
        )
    reconciliation_age = (
        evaluated - _timestamp("reconciliation.completed_at", reconciliation.completed_at)
    ).total_seconds()
    if reconciliation_age < 0 or reconciliation_age >= policy.reconciliation_ttl_seconds:
        findings.append(
            _finding(
                FindingCode.RECONCILIATION_STALE,
                FindingSubjectType.RECONCILIATION,
                reconciliation.reconciliation_id,
                observed=str(int(reconciliation_age)),
                expected=f"<{policy.reconciliation_ttl_seconds}",
                message="reconciliation is stale at the frozen TTL boundary",
            )
        )
    if (
        not reconciliation.is_reconciled
        or reconciliation.snapshot_id != account.snapshot_id
        or reconciliation.account_reference != account.account_reference
        or reconciliation.broker_id != account.broker_id
        or reconciliation.environment is not account.environment
    ):
        findings.append(
            _finding(
                FindingCode.RECONCILIATION_REQUIRED,
                FindingSubjectType.RECONCILIATION,
                reconciliation.reconciliation_id,
                observed=reconciliation.is_reconciled,
                expected=True,
                message="account lacks a matching reconciled result",
            )
        )

    if session.state is TradingSessionState.UNKNOWN:
        findings.append(
            _finding(
                FindingCode.SESSION_UNKNOWN,
                FindingSubjectType.SESSION,
                session.session_snapshot_id,
                observed=session.state,
                expected=TradingSessionState.REGULAR,
                message="trading session state is unknown",
            )
        )
    elif not session.submit_allowed:
        findings.append(
            _finding(
                FindingCode.SESSION_NOT_PERMITTED,
                FindingSubjectType.SESSION,
                session.session_snapshot_id,
                observed=session.submission_permissions,
                expected=PermissionState.PERMITTED,
                message="session does not permit submission",
            )
        )
    session_age = (evaluated - _timestamp("session.as_of", session.as_of)).total_seconds()
    if session_age < 0 or session_age >= policy.snapshot_ttl_seconds:
        findings.append(
            _finding(
                FindingCode.SESSION_UNKNOWN,
                FindingSubjectType.SESSION,
                session.session_snapshot_id,
                observed=str(int(session_age)),
                expected=f"0..<{policy.snapshot_ttl_seconds}",
                message="session observation is stale or from the future",
            )
        )
    return _ordered(findings)


def _capability_finding(
    account: BrokerAccountSnapshot,
    capability: CapabilityName,
) -> BrokerSafetyFinding | None:
    state = account.capabilities.capability_state(capability)
    if state is SupportState.SUPPORTED:
        return None
    return _finding(
        FindingCode.CAPABILITY_UNKNOWN
        if state is SupportState.UNKNOWN
        else FindingCode.CAPABILITY_UNSUPPORTED,
        FindingSubjectType.CAPABILITY,
        capability.value,
        observed=state,
        expected=SupportState.SUPPORTED,
        message="limit evaluation requires a supported capability",
    )


def evaluate_broker_limits(
    account: BrokerAccountSnapshot,
    policy: BrokerSafetyPolicy,
    request: BrokerLimitRequest,
) -> tuple[BrokerSafetyFinding, ...]:
    """Evaluate projected limits conservatively without creating an order intent."""
    if type(account) is not BrokerAccountSnapshot:
        raise BrokerSafetyModelError("account must be exact BrokerAccountSnapshot")
    if type(policy) is not BrokerSafetyPolicy:
        raise BrokerSafetyModelError("policy must be exact BrokerSafetyPolicy")
    if type(request) is not BrokerLimitRequest:
        raise BrokerSafetyModelError("request must be exact BrokerLimitRequest")
    findings: list[BrokerSafetyFinding] = []

    if request.currency != account.currency or request.currency != policy.currency:
        findings.append(
            _finding(
                FindingCode.CURRENCY_MISMATCH,
                FindingSubjectType.LIMIT,
                request.canonical_symbol,
                observed=request.currency,
                expected=policy.currency,
                message="limit request currency is incompatible",
            )
        )
    if request.order_type not in policy.allowed_order_types:
        findings.append(
            _finding(
                FindingCode.ORDER_TYPE_NOT_ALLOWED,
                FindingSubjectType.LIMIT,
                request.canonical_symbol,
                observed=request.order_type,
                expected=",".join(item.value for item in policy.allowed_order_types) or "none",
                message="order type is not enabled by safety policy",
            )
        )
    if request.order_type not in account.capabilities.supported_order_types:
        findings.append(
            _finding(
                FindingCode.CAPABILITY_UNSUPPORTED,
                FindingSubjectType.CAPABILITY,
                request.order_type.value,
                observed="unsupported",
                expected="supported",
                message="broker does not report requested order type support",
            )
        )

    if request.quantity != request.quantity.to_integral_value():
        item = _capability_finding(account, CapabilityName.FRACTIONAL_QUANTITY)
        if item is not None:
            findings.append(item)

    position = next(
        (item for item in account.positions if item.canonical_symbol == request.canonical_symbol),
        None,
    )
    available_long_quantity = (
        Decimal("0") if position is None else position.available_quantity
    )
    if request.side is OrderSide.SELL and request.quantity > available_long_quantity:
        for capability in (CapabilityName.SHORT_SELLING, CapabilityName.BORROW_AVAILABILITY):
            item = _capability_finding(account, capability)
            if item is not None:
                findings.append(item)

    for name, estimate in (
        ("fees", request.estimated_fees),
        ("taxes", request.estimated_taxes),
    ):
        if estimate is None:
            item = _capability_finding(account, CapabilityName.FEE_ESTIMATE)
            if item is not None:
                findings.append(item)
            findings.append(
                _finding(
                    FindingCode.INSUFFICIENT_LIMIT_INPUT,
                    FindingSubjectType.LIMIT,
                    request.canonical_symbol,
                    observed=None,
                    expected=name,
                    message=f"{name} estimate is required for conservative limits",
                )
            )

    charges = (request.estimated_fees or Decimal("0")) + (
        request.estimated_taxes or Decimal("0")
    )
    order_notional = request.projected_order_notional + charges
    if order_notional > policy.maximum_order_notional:
        findings.append(
            _finding(
                FindingCode.ORDER_NOTIONAL_LIMIT,
                FindingSubjectType.LIMIT,
                request.canonical_symbol,
                observed=order_notional,
                expected=policy.maximum_order_notional,
                message="conservative order notional exceeds policy limit",
            )
        )

    exposure_known = all(
        item.market_value_reliability is FieldReliability.RELIABLE
        and item.market_value is not None
        for item in account.positions
    )
    reserved = (
        request.broker_open_order_reserved_notional
        + request.unknown_submission_reserved_notional
    )
    if not exposure_known:
        findings.append(
            _finding(
                FindingCode.INSUFFICIENT_LIMIT_INPUT,
                FindingSubjectType.LIMIT,
                request.canonical_symbol,
                observed="unreliable-position-market-value",
                expected="reliable",
                message="account exposure cannot be proven from position values",
            )
        )
    else:
        current_exposure = sum(
            (abs(item.market_value) for item in account.positions if item.market_value is not None),
            Decimal("0"),
        )
        projected_account = current_exposure + reserved + order_notional
        if projected_account > policy.maximum_post_fill_account_exposure:
            findings.append(
                _finding(
                    FindingCode.ACCOUNT_EXPOSURE_LIMIT,
                    FindingSubjectType.LIMIT,
                    account.account_reference,
                    observed=projected_account,
                    expected=policy.maximum_post_fill_account_exposure,
                    message="conservative post-fill account exposure exceeds policy limit",
                )
            )
        symbol_exposure = (
            Decimal("0")
            if position is None or position.market_value is None
            else abs(position.market_value)
        )
        projected_symbol = symbol_exposure + reserved + order_notional
        if projected_symbol > policy.maximum_per_symbol_exposure:
            findings.append(
                _finding(
                    FindingCode.SYMBOL_EXPOSURE_LIMIT,
                    FindingSubjectType.LIMIT,
                    request.canonical_symbol,
                    observed=projected_symbol,
                    expected=policy.maximum_per_symbol_exposure,
                    message="conservative per-symbol exposure exceeds policy limit",
                )
            )

    current_quantity = Decimal("0") if position is None else abs(position.quantity)
    broker_open_quantity = sum(
        (
            item.remaining_quantity
            for item in account.open_orders
            if item.canonical_symbol == request.canonical_symbol
        ),
        Decimal("0"),
    )
    projected_quantity = current_quantity + broker_open_quantity + request.quantity
    if projected_quantity > policy.maximum_per_symbol_quantity:
        findings.append(
            _finding(
                FindingCode.SYMBOL_QUANTITY_LIMIT,
                FindingSubjectType.LIMIT,
                request.canonical_symbol,
                observed=projected_quantity,
                expected=policy.maximum_per_symbol_quantity,
                message="conservative per-symbol quantity exceeds policy limit",
            )
        )

    if request.unresolved_submission_count:
        findings.append(
            _finding(
                FindingCode.INSUFFICIENT_LIMIT_INPUT,
                FindingSubjectType.LIMIT,
                request.canonical_symbol,
                observed=request.unresolved_submission_count,
                expected=0,
                message="unresolved submission symbol and quantity exposure is unknown",
            )
        )

    projected_open_orders = (
        len(account.open_orders) + request.unresolved_submission_count + 1
    )
    if projected_open_orders > policy.maximum_simultaneous_open_orders:
        findings.append(
            _finding(
                FindingCode.OPEN_ORDER_LIMIT,
                FindingSubjectType.LIMIT,
                account.account_reference,
                observed=projected_open_orders,
                expected=policy.maximum_simultaneous_open_orders,
                message="broker open orders plus unresolved submissions exceed limit",
            )
        )

    projected_daily = (
        request.current_daily_submitted_notional
        + request.broker_open_order_reserved_notional
        + request.unknown_submission_reserved_notional
        + order_notional
    )
    if projected_daily > policy.maximum_daily_submitted_notional:
        findings.append(
            _finding(
                FindingCode.DAILY_NOTIONAL_LIMIT,
                FindingSubjectType.LIMIT,
                account.account_reference,
                observed=projected_daily,
                expected=policy.maximum_daily_submitted_notional,
                message="daily submitted notional including unknown attempts exceeds limit",
            )
        )

    if policy.maximum_daily_loss > 0:
        if (
            request.daily_loss_reliability is not FieldReliability.RELIABLE
            or request.current_daily_loss is None
        ):
            findings.append(
                _finding(
                    FindingCode.DAILY_LOSS_UNRELIABLE,
                    FindingSubjectType.LIMIT,
                    account.account_reference,
                    observed=request.daily_loss_reliability,
                    expected=FieldReliability.RELIABLE,
                    message="daily loss is required and must be reliable",
                )
            )
        elif request.current_daily_loss > policy.maximum_daily_loss:
            findings.append(
                _finding(
                    FindingCode.DAILY_LOSS_LIMIT,
                    FindingSubjectType.LIMIT,
                    account.account_reference,
                    observed=request.current_daily_loss,
                    expected=policy.maximum_daily_loss,
                    message="daily loss exceeds policy limit",
                )
            )

    if request.is_initial_allocation and order_notional > policy.initial_allocation_ceiling:
        findings.append(
            _finding(
                FindingCode.INITIAL_ALLOCATION_LIMIT,
                FindingSubjectType.LIMIT,
                request.canonical_symbol,
                observed=order_notional,
                expected=policy.initial_allocation_ceiling,
                message="initial allocation exceeds policy ceiling",
            )
        )
    return _ordered(findings)


__all__ = [
    "evaluate_broker_limits",
    "evaluate_broker_preflight",
    "reconcile_broker_account",
]

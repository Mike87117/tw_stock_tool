"""Pure Phase 56.5A4 authorization gates and lifecycle reducers."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from tw_stock_tool.broker_safety.evaluation import evaluate_broker_limits, evaluate_broker_preflight
from tw_stock_tool.broker_safety.execution_models import (
    A4_SCHEMA_VERSION, AUTHORIZATION_ARTIFACT_TYPE, AUTHORIZATION_USE_ARTIFACT_TYPE,
    ORDER_INTENT_ARTIFACT_TYPE, SUBMISSION_ARTIFACT_TYPE, AuthorizationUseState,
    BrokerA4ModelError, BrokerAuthorizationUseRecord, BrokerExecutionAuthorization,
    BrokerExecutionRecord, BrokerKillSwitchSnapshot, BrokerOrderIntent,
    BrokerOrderIntentKeyPayload, BrokerSubmissionEvidence, BrokerSubmissionRecord,
    BrokerSubmissionState, KillSwitchState, QuantityMode,
    canonical_broker_client_order_id, derive_broker_order_intent_key_v1,
)
from tw_stock_tool.broker_safety.models import (
    BrokerAccountSnapshot, BrokerLimitRequest, BrokerLocalExpectation,
    BrokerReconciliationResult, BrokerSafetyFinding,
    BrokerSafetyPolicy, FindingCode, FindingSeverity, FindingSubjectType,
    OrderType, TimeInForce, TradingSessionSnapshot, _timestamp,
)
from tw_stock_tool.broker_safety.source_models import BrokerSafetySourceHandoff, ForwardEligibilityProgression


def _finding(code, subject_type, subject_id, observed, expected, message):
    def text(value):
        if value is None:
            return None
        return value.value if hasattr(value, "value") else str(value)
    return BrokerSafetyFinding(code, FindingSeverity.ERROR, subject_type, subject_id, text(observed), text(expected), message, True)


def _ordered(items):
    return tuple(sorted(items, key=lambda item: (item.code.value, item.subject_type.value, item.subject_id, item.observed or "", item.expected or "", item.message)))


def _require(name, value, expected):
    if type(value) is not expected:
        raise BrokerA4ModelError(f"{name} must be exact {expected.__name__}")


def _mismatch(findings, subject_type, subject_id, name, observed, expected):
    if observed != expected:
        findings.append(_finding(FindingCode.IDENTITY_MISMATCH, subject_type, subject_id, observed, expected, f"{name} does not match the frozen fact"))


def _validate(source, head, account, reconciliation, expectation, policy, session, kill_switch, request):
    for name, value, expected in (
        ("source", source, BrokerSafetySourceHandoff), ("current_head", head, ForwardEligibilityProgression),
        ("account", account, BrokerAccountSnapshot), ("reconciliation", reconciliation, BrokerReconciliationResult),
        ("expectation", expectation, BrokerLocalExpectation), ("policy", policy, BrokerSafetyPolicy),
        ("session", session, TradingSessionSnapshot), ("kill_switch", kill_switch, BrokerKillSwitchSnapshot),
        ("request", request, BrokerLimitRequest),
    ):
        _require(name, value, expected)


def evaluate_broker_execution_authorization(
    authorization, source, current_head, account, reconciliation, expectation,
    policy, session, kill_switch, request, *, preflight_findings,
    limit_findings, evaluated_at,
):
    """Recompute and bind every prerequisite; uncertainty always blocks."""
    _require("authorization", authorization, BrokerExecutionAuthorization)
    _validate(source, current_head, account, reconciliation, expectation, policy, session, kill_switch, request)
    for name, items in (("preflight_findings", preflight_findings), ("limit_findings", limit_findings)):
        if type(items) is not tuple or any(type(item) is not BrokerSafetyFinding for item in items):
            raise BrokerA4ModelError(f"{name} must be an exact finding tuple")
    evaluated = _timestamp("evaluated_at", evaluated_at)
    actual_preflight = evaluate_broker_preflight(account, session, policy, reconciliation, evaluated_at=evaluated_at)
    actual_limits = evaluate_broker_limits(account, expectation, policy, request)
    findings = list(actual_preflight) + list(actual_limits)
    if preflight_findings != actual_preflight or limit_findings != actual_limits:
        findings.append(_finding(FindingCode.SAFETY_FINDINGS_MISMATCH, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, "caller-supplied", "exact-recomputed", "supplied safety findings differ from recomputation"))
    bindings = (
        ("source run", authorization.source_workspace_run_id, source.workspace_run_id),
        ("publication", authorization.publication_id, source.publication_id),
        ("publication digest", authorization.publication_index_sha256, source.publication_index_sha256),
        ("activation", authorization.activation_id, source.activation_id),
        ("qualification", authorization.qualification_evaluation_id, source.qualification_evaluation_id),
        ("strategy", authorization.strategy_id, source.strategy_id),
        ("eligibility", authorization.eligibility_id, source.eligibility_id),
        ("eligibility policy", authorization.eligibility_policy_id, source.policy_id),
        ("eligibility policy version", authorization.eligibility_policy_version, source.policy_version),
        ("progression", authorization.progression_fingerprint, source.progression_fingerprint),
        ("ledger", authorization.ledger_id, source.ledger_id),
        ("recommendation", authorization.recommendation_id, source.recommendation_id),
        ("recommendation digest", authorization.recommendation_sha256, source.recommendation_sha256),
        ("current head", authorization.current_lineage_head_fingerprint, current_head.progression_fingerprint),
        ("account", authorization.account_reference, account.account_reference),
        ("broker", authorization.broker_id, account.broker_id),
        ("environment", authorization.environment, account.environment),
        ("reconciliation", authorization.reconciliation_id, reconciliation.reconciliation_id),
        ("snapshot", authorization.snapshot_id, account.snapshot_id),
        ("local state", authorization.local_state_version, expectation.local_state_version),
        ("reconciliation local state", reconciliation.local_state_version, expectation.local_state_version),
        ("safety policy", authorization.broker_safety_policy_id, policy.policy_id),
        ("safety policy version", authorization.broker_safety_policy_version, policy.policy_version),
        ("currency", authorization.currency, policy.currency),
        ("request currency", request.currency, authorization.currency),
        ("session", authorization.session_date, session.session_date),
        ("kill version", authorization.kill_switch_version, kill_switch.kill_switch_version),
        ("kill account", kill_switch.account_reference, account.account_reference),
        ("kill broker", kill_switch.broker_id, account.broker_id),
        ("kill environment", kill_switch.environment, account.environment),
    )
    for name, observed, expected in bindings:
        _mismatch(findings, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, name, observed, expected)
    anchor_matches = any(anchor.recommendation_id == source.recommendation_id and anchor.recommendation_sha256 == source.recommendation_sha256 and anchor.symbol == source.decision_symbol for anchor in current_head.recommendation_anchors)
    head_matches = source.lineage_key == current_head.lineage_key and source.workspace_run_id == current_head.run_id and source.publication_id == current_head.publication_id and source.publication_index_sha256 == current_head.publication_index_sha256 and source.qualification_evaluation_id == current_head.qualification_evaluation_id and source.eligibility_id == current_head.eligibility_id and source.ledger_id == current_head.ledger_id and source.progression_fingerprint == current_head.progression_fingerprint and anchor_matches
    if not head_matches or source.eligibility_state.value != "ACTIVE" or current_head.eligibility_state.value != "ACTIVE":
        findings.append(_finding(FindingCode.IDENTITY_MISMATCH, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, "source", "exact ACTIVE current head", "source is not the exact active lineage head"))
    if request.canonical_symbol not in authorization.allowed_symbols or any(symbol not in source.qualified_symbols for symbol in authorization.allowed_symbols):
        findings.append(_finding(FindingCode.AUTHORIZATION_BOUNDS_EXCEEDED, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, request.canonical_symbol, ",".join(source.qualified_symbols), "symbol is outside the qualified universe"))
    if authorization.allowed_order_types != (request.order_type,) or any(order_type not in account.capabilities.supported_order_types or order_type not in policy.allowed_order_types for order_type in authorization.allowed_order_types):
        findings.append(_finding(FindingCode.AUTHORIZATION_BOUNDS_EXCEEDED, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, ",".join(item.value for item in authorization.allowed_order_types), request.order_type, "authorization order types exceed the evaluated request"))
    if any(time_in_force not in account.capabilities.supported_time_in_force for time_in_force in authorization.allowed_time_in_force):
        findings.append(_finding(FindingCode.AUTHORIZATION_BOUNDS_EXCEEDED, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, ",".join(item.value for item in authorization.allowed_time_in_force), "broker-supported", "authorization time-in-force exceeds capabilities"))
    if authorization.allowed_side is not request.side or request.order_type not in authorization.allowed_order_types:
        findings.append(_finding(FindingCode.AUTHORIZATION_BOUNDS_EXCEEDED, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, f"{request.side.value}/{request.order_type.value}", "authorized", "side or order type exceeds authorization"))
    if request.order_type not in account.capabilities.supported_order_types or request.order_type not in policy.allowed_order_types:
        findings.append(_finding(FindingCode.ORDER_TYPE_NOT_ALLOWED, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, request.order_type, "supported-and-allowed", "order type is not supported and policy allowed"))
    notional = request.projected_order_notional + (request.estimated_fees or Decimal(0)) + (request.estimated_taxes or Decimal(0))
    if authorization.maximum_quantity > request.quantity or authorization.maximum_notional > notional:
        findings.append(_finding(FindingCode.AUTHORIZATION_BOUNDS_EXCEEDED, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, f"{authorization.maximum_quantity}/{authorization.maximum_notional}", f"<={request.quantity}/<={notional}", "authorization widens evaluated quantity or notional"))
    if request.quantity > authorization.maximum_quantity or notional > authorization.maximum_notional:
        findings.append(_finding(FindingCode.AUTHORIZATION_BOUNDS_EXCEEDED, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, f"{request.quantity}/{notional}", f"<={authorization.maximum_quantity}/<={authorization.maximum_notional}", "request exceeds authorization"))
    ttl = (_timestamp("expires_at", authorization.expires_at) - _timestamp("not_before", authorization.not_before)).total_seconds()
    if ttl >= policy.authorization_ttl_seconds:
        findings.append(_finding(FindingCode.AUTHORIZATION_TTL_EXCEEDED, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, ttl, f"<{policy.authorization_ttl_seconds}", "authorization reaches the frozen TTL boundary"))
    if evaluated < _timestamp("not_before", authorization.not_before):
        findings.append(_finding(FindingCode.AUTHORIZATION_NOT_YET_VALID, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, evaluated_at, authorization.not_before, "authorization is not yet valid"))
    if evaluated >= _timestamp("expires_at", authorization.expires_at):
        findings.append(_finding(FindingCode.AUTHORIZATION_EXPIRED, FindingSubjectType.AUTHORIZATION, authorization.authorization_id, evaluated_at, f"<{authorization.expires_at}", "authorization is expired"))
    if kill_switch.stop_new_orders_state is KillSwitchState.UNKNOWN:
        findings.append(_finding(FindingCode.KILL_SWITCH_UNKNOWN, FindingSubjectType.KILL_SWITCH, kill_switch.kill_switch_version, KillSwitchState.UNKNOWN, KillSwitchState.INACTIVE, "stop-new-orders state is unknown"))
    elif kill_switch.stop_new_orders_state is KillSwitchState.ACTIVE:
        findings.append(_finding(FindingCode.KILL_SWITCH_ACTIVE, FindingSubjectType.KILL_SWITCH, kill_switch.kill_switch_version, KillSwitchState.ACTIVE, KillSwitchState.INACTIVE, "stop-new-orders state is active"))
    return _ordered(findings)


def build_broker_execution_authorization(
    source, current_head, account, reconciliation, expectation, policy, session,
    kill_switch, request, *, authorization_id, time_in_force, approved_at,
    not_before, expires_at, approver_identity_ref, preflight_findings, limit_findings,
):
    _validate(source, current_head, account, reconciliation, expectation, policy, session, kill_switch, request)
    if type(time_in_force) is not TimeInForce or time_in_force not in account.capabilities.supported_time_in_force:
        raise BrokerA4ModelError("time_in_force is not supported")
    authorization = BrokerExecutionAuthorization(
        A4_SCHEMA_VERSION, AUTHORIZATION_ARTIFACT_TYPE, authorization_id,
        account.account_reference, account.broker_id, account.environment,
        source.workspace_run_id, source.publication_id, source.publication_index_sha256,
        source.activation_id, source.qualification_evaluation_id, source.strategy_id,
        source.eligibility_id, source.policy_id, source.policy_version,
        current_head.progression_fingerprint, source.progression_fingerprint,
        source.ledger_id, source.recommendation_id, source.recommendation_sha256,
        reconciliation.reconciliation_id, account.snapshot_id, expectation.local_state_version,
        policy.policy_id, policy.policy_version, (request.canonical_symbol,), request.side,
        (request.order_type,), (time_in_force,), request.quantity,
        request.projected_order_notional + (request.estimated_fees or Decimal(0)) + (request.estimated_taxes or Decimal(0)),
        request.currency, session.session_date, not_before, expires_at, approved_at,
        approver_identity_ref, kill_switch.kill_switch_version,
    )
    findings = evaluate_broker_execution_authorization(
        authorization, source, current_head, account, reconciliation, expectation,
        policy, session, kill_switch, request, preflight_findings=preflight_findings,
        limit_findings=limit_findings, evaluated_at=approved_at,
    )
    if findings:
        raise BrokerA4ModelError("authorization blocked: " + ",".join(item.code.value for item in findings))
    return authorization


def evaluate_broker_order_intent(intent, authorization, source, current_head, kill_switch, *, evaluated_at):
    for name, value, expected in (("intent", intent, BrokerOrderIntent), ("authorization", authorization, BrokerExecutionAuthorization), ("source", source, BrokerSafetySourceHandoff), ("current_head", current_head, ForwardEligibilityProgression), ("kill_switch", kill_switch, BrokerKillSwitchSnapshot)):
        _require(name, value, expected)
    findings = []
    if kill_switch.kill_switch_version != authorization.kill_switch_version:
        findings.append(_finding(FindingCode.IDENTITY_MISMATCH, FindingSubjectType.INTENT, intent.economic_intent_id, kill_switch.kill_switch_version, authorization.kill_switch_version, "kill-switch version differs from authorization"))
    if (kill_switch.account_reference, kill_switch.broker_id, kill_switch.environment) != (authorization.account_reference, authorization.broker_id, authorization.environment):
        findings.append(_finding(FindingCode.IDENTITY_MISMATCH, FindingSubjectType.INTENT, intent.economic_intent_id, "kill-switch identity", "authorization identity", "kill-switch identity differs from authorization"))
    if kill_switch.stop_new_orders_state is KillSwitchState.UNKNOWN:
        findings.append(_finding(FindingCode.KILL_SWITCH_UNKNOWN, FindingSubjectType.KILL_SWITCH, kill_switch.kill_switch_version, KillSwitchState.UNKNOWN, KillSwitchState.INACTIVE, "stop-new-orders state is unknown"))
    elif kill_switch.stop_new_orders_state is KillSwitchState.ACTIVE:
        findings.append(_finding(FindingCode.KILL_SWITCH_ACTIVE, FindingSubjectType.KILL_SWITCH, kill_switch.kill_switch_version, KillSwitchState.ACTIVE, KillSwitchState.INACTIVE, "stop-new-orders state is active"))
    bindings = (
        ("authorization", intent.authorization_id, authorization.authorization_id),
        ("source run", intent.source_workspace_run_id, source.workspace_run_id),
        ("publication", intent.publication_id, source.publication_id),
        ("publication digest", intent.publication_index_sha256, source.publication_index_sha256),
        ("current head", intent.current_lineage_head_fingerprint, current_head.progression_fingerprint),
        ("progression", intent.progression_fingerprint, source.progression_fingerprint),
        ("ledger", intent.ledger_id, source.ledger_id),
        ("recommendation", intent.recommendation_id, source.recommendation_id),
        ("recommendation digest", intent.recommendation_sha256, source.recommendation_sha256),
        ("account", intent.account_reference, authorization.account_reference),
        ("broker", intent.broker_id, authorization.broker_id),
        ("environment", intent.environment, authorization.environment),
        ("session", intent.session_date, authorization.session_date),
        ("currency", intent.currency, authorization.currency),
    )
    for name, observed, expected in bindings:
        _mismatch(findings, FindingSubjectType.INTENT, intent.economic_intent_id, name, observed, expected)
    if intent.canonical_symbol not in authorization.allowed_symbols or intent.side is not authorization.allowed_side or intent.order_type not in authorization.allowed_order_types or intent.time_in_force not in authorization.allowed_time_in_force:
        findings.append(_finding(FindingCode.INTENT_BOUNDS_EXCEEDED, FindingSubjectType.INTENT, intent.economic_intent_id, "economic-facts", "authorization-bounds", "intent exceeds authorization"))
    if intent.order_type is OrderType.LIMIT:
        notional = intent.quantity * intent.limit_price
        if intent.notional != notional:
            findings.append(_finding(FindingCode.INTENT_BOUNDS_EXCEEDED, FindingSubjectType.INTENT, intent.economic_intent_id, intent.notional, notional, "priced intent notional differs from exact executable principal"))
    else:
        notional = intent.notional
        if intent.quantity_mode is QuantityMode.NOTIONAL or notional != authorization.maximum_notional:
            findings.append(_finding(FindingCode.INTENT_BOUNDS_EXCEEDED, FindingSubjectType.INTENT, intent.economic_intent_id, notional, authorization.maximum_notional, "unpriced intent lacks the exact reviewed conservative notional"))
    if intent.quantity > authorization.maximum_quantity or notional > authorization.maximum_notional:
        findings.append(_finding(FindingCode.INTENT_BOUNDS_EXCEEDED, FindingSubjectType.INTENT, intent.economic_intent_id, f"{intent.quantity}/{notional}", f"<={authorization.maximum_quantity}/<={authorization.maximum_notional}", "intent exceeds quantity or notional"))
    evaluated = _timestamp("evaluated_at", evaluated_at)
    if evaluated < _timestamp("not_before", authorization.not_before):
        findings.append(_finding(FindingCode.AUTHORIZATION_NOT_YET_VALID, FindingSubjectType.INTENT, intent.economic_intent_id, evaluated_at, authorization.not_before, "authorization is not yet valid"))
    if evaluated >= _timestamp("expires_at", authorization.expires_at):
        findings.append(_finding(FindingCode.AUTHORIZATION_EXPIRED, FindingSubjectType.INTENT, intent.economic_intent_id, evaluated_at, f"<{authorization.expires_at}", "authorization is expired"))
    return _ordered(findings)


def build_broker_order_intent(
    authorization, source, current_head, kill_switch, *, economic_intent_id, canonical_symbol,
    side, quantity_mode, quantity, notional, order_type,
    time_in_force, limit_price, currency, created_at, intent_revision,
    broker_client_order_id_max_length=None,
):
    payload = BrokerOrderIntentKeyPayload(
        A4_SCHEMA_VERSION, authorization.account_reference, authorization.environment,
        source.publication_id, source.publication_index_sha256,
        current_head.progression_fingerprint, source.ledger_id, source.recommendation_id,
        source.recommendation_sha256, canonical_symbol, side, quantity_mode,
        quantity if quantity_mode is QuantityMode.QUANTITY else notional,
        order_type, limit_price, time_in_force, authorization.session_date, intent_revision,
    )
    key = derive_broker_order_intent_key_v1(payload)
    intent = BrokerOrderIntent(
        A4_SCHEMA_VERSION, ORDER_INTENT_ARTIFACT_TYPE, economic_intent_id, key,
        canonical_broker_client_order_id(key, broker_max_length=broker_client_order_id_max_length),
        authorization.authorization_id, source.workspace_run_id, source.publication_id,
        source.publication_index_sha256, current_head.progression_fingerprint,
        source.progression_fingerprint, source.ledger_id, source.recommendation_id,
        source.recommendation_sha256, authorization.account_reference,
        authorization.broker_id, authorization.environment, authorization.session_date,
        canonical_symbol, side, quantity_mode, quantity, notional,
        order_type, time_in_force, limit_price, currency, created_at, intent_revision,
    )
    findings = evaluate_broker_order_intent(intent, authorization, source, current_head, kill_switch, evaluated_at=created_at)
    if findings:
        raise BrokerA4ModelError("intent blocked: " + ",".join(item.code.value for item in findings))
    return intent


def reserve_broker_authorization_use(authorization, intent, *, authorization_use_id, reserved_at):
    _require("authorization", authorization, BrokerExecutionAuthorization)
    _require("intent", intent, BrokerOrderIntent)
    if (intent.authorization_id, intent.account_reference, intent.environment) != (authorization.authorization_id, authorization.account_reference, authorization.environment):
        raise BrokerA4ModelError("intent is not bound to authorization")
    return BrokerAuthorizationUseRecord(A4_SCHEMA_VERSION, AUTHORIZATION_USE_ARTIFACT_TYPE, authorization_use_id, authorization.authorization_id, authorization.account_reference, authorization.environment, intent.economic_intent_id, intent.idempotency_key, AuthorizationUseState.RESERVED, reserved_at, None, None, None)


def transition_broker_authorization_use(record, target_state, *, authorization_id, economic_intent_id, idempotency_key, occurred_at, reason=None):
    _require("record", record, BrokerAuthorizationUseRecord)
    if type(target_state) is not AuthorizationUseState or target_state not in (AuthorizationUseState.CONSUMED, AuthorizationUseState.ABANDONED):
        raise BrokerA4ModelError("target must be CONSUMED or ABANDONED")
    if record.state is not AuthorizationUseState.RESERVED:
        raise BrokerA4ModelError("authorization use is terminal")
    if (authorization_id, economic_intent_id, idempotency_key) != (record.authorization_id, record.economic_intent_id, record.idempotency_key):
        raise BrokerA4ModelError("authorization-use identity substitution")
    if _timestamp("occurred_at", occurred_at) < _timestamp("reserved_at", record.reserved_at):
        raise BrokerA4ModelError("transition precedes reservation")
    return replace(record, state=target_state, consumed_at=occurred_at if target_state is AuthorizationUseState.CONSUMED else None, abandoned_at=occurred_at if target_state is AuthorizationUseState.ABANDONED else None, reason=reason)


def prepare_broker_submission(intent, *, attempt_id, recorded_at):
    _require("intent", intent, BrokerOrderIntent)
    return BrokerSubmissionRecord(
        A4_SCHEMA_VERSION, SUBMISSION_ARTIFACT_TYPE, intent.economic_intent_id,
        attempt_id, BrokerSubmissionState.PREPARED, intent.canonical_client_order_id,
        None, None, None, None, None, None, Decimal(0), intent.quantity, (), recorded_at,
    )


def _evaluate_authoritative_submission_gate(
    intent, authorization, source, current_head, account, reconciliation,
    expectation, policy, session, kill_switch, request, *, evaluated_at,
):
    _require("intent", intent, BrokerOrderIntent)
    _require("authorization", authorization, BrokerExecutionAuthorization)
    _validate(source, current_head, account, reconciliation, expectation, policy, session, kill_switch, request)
    preflight = evaluate_broker_preflight(account, session, policy, reconciliation, evaluated_at=evaluated_at)
    limits = evaluate_broker_limits(account, expectation, policy, request)
    return _ordered((
        *evaluate_broker_execution_authorization(
            authorization, source, current_head, account, reconciliation,
            expectation, policy, session, kill_switch, request,
            preflight_findings=preflight, limit_findings=limits,
            evaluated_at=evaluated_at,
        ),
        *evaluate_broker_order_intent(
            intent, authorization, source, current_head, kill_switch,
            evaluated_at=evaluated_at,
        ),
    ))


def transition_broker_submission(
    record, intent, evidence, *, recorded_at, broker_order_id=None,
    pre_submit_persistence_version=None, sanitized_outcome=None,
    last_reconciliation_id=None, authorization=None, source=None,
    current_head=None, account=None, reconciliation=None, expectation=None,
    policy=None, session=None, kill_switch=None, request=None,
    authorization_use=None,
):
    _require("record", record, BrokerSubmissionRecord)
    _require("intent", intent, BrokerOrderIntent)
    if type(evidence) is not BrokerSubmissionEvidence:
        raise BrokerA4ModelError("evidence must be exact BrokerSubmissionEvidence")
    if record.intent_id != intent.economic_intent_id or record.stable_client_order_id != intent.canonical_client_order_id:
        raise BrokerA4ModelError("submission identity substitution")
    if _timestamp("recorded_at", recorded_at) < _timestamp("prior recorded_at", record.recorded_at):
        raise BrokerA4ModelError("submission time must be monotonic")
    terminal = (BrokerSubmissionState.FILLED, BrokerSubmissionState.CANCELLED,
                BrokerSubmissionState.REJECTED, BrokerSubmissionState.EXPIRED,
                BrokerSubmissionState.UNKNOWN_SUBMISSION_STATE,
                BrokerSubmissionState.RECONCILIATION_REQUIRED)
    if record.state in terminal:
        raise BrokerA4ModelError("terminal or uncertain submission cannot transition")
    pair = (record.state, evidence)
    updates = {"recorded_at": recorded_at}
    if pair == (BrokerSubmissionState.PREPARED, BrokerSubmissionEvidence.AUTHORIZATION_GATE):
        if _evaluate_authoritative_submission_gate(
            intent, authorization, source, current_head, account, reconciliation,
            expectation, policy, session, kill_switch, request,
            evaluated_at=recorded_at,
        ):
            raise BrokerA4ModelError("authorization gate is blocking")
        target = BrokerSubmissionState.AUTHORIZED
    elif pair == (BrokerSubmissionState.AUTHORIZED, BrokerSubmissionEvidence.SUBMIT_REQUEST):
        if _evaluate_authoritative_submission_gate(
            intent, authorization, source, current_head, account, reconciliation,
            expectation, policy, session, kill_switch, request,
            evaluated_at=recorded_at,
        ):
            raise BrokerA4ModelError("pre-submit authorization gate is blocking")
        _require("authorization_use", authorization_use, BrokerAuthorizationUseRecord)
        if authorization_use.state is not AuthorizationUseState.CONSUMED:
            raise BrokerA4ModelError("SUBMITTING requires a consumed authorization use")
        if (
            authorization_use.authorization_id,
            authorization_use.account_reference,
            authorization_use.environment,
            authorization_use.economic_intent_id,
            authorization_use.idempotency_key,
        ) != (
            authorization.authorization_id,
            authorization.account_reference,
            authorization.environment,
            intent.economic_intent_id,
            intent.idempotency_key,
        ):
            raise BrokerA4ModelError("authorization-use identity substitution")
        if _timestamp("consumed_at", authorization_use.consumed_at) > _timestamp("recorded_at", recorded_at):
            raise BrokerA4ModelError("authorization use cannot follow submission")
        if pre_submit_persistence_version is None:
            raise BrokerA4ModelError("SUBMITTING requires an opaque persistence version reference")
        target = BrokerSubmissionState.SUBMITTING
        updates.update(pre_submit_persistence_version=pre_submit_persistence_version, request_timestamp=recorded_at)
    elif pair == (BrokerSubmissionState.SUBMITTING, BrokerSubmissionEvidence.BROKER_ACK):
        if broker_order_id is None:
            raise BrokerA4ModelError("acknowledgement requires broker_order_id")
        target = BrokerSubmissionState.ACKNOWLEDGED
        updates.update(broker_order_id=broker_order_id, ack_timestamp=recorded_at)
    elif pair in ((BrokerSubmissionState.SUBMITTING, BrokerSubmissionEvidence.BROKER_REJECTION),
                  (BrokerSubmissionState.ACKNOWLEDGED, BrokerSubmissionEvidence.BROKER_REJECTION)):
        target = BrokerSubmissionState.REJECTED
        updates["sanitized_outcome"] = sanitized_outcome or "broker-rejected"
        if broker_order_id is not None:
            updates.update(broker_order_id=broker_order_id, ack_timestamp=record.ack_timestamp or recorded_at)
    elif pair in ((BrokerSubmissionState.SUBMITTING, BrokerSubmissionEvidence.AMBIGUOUS_OUTCOME),
                  (BrokerSubmissionState.CANCEL_PENDING, BrokerSubmissionEvidence.AMBIGUOUS_OUTCOME)):
        target = BrokerSubmissionState.UNKNOWN_SUBMISSION_STATE
        updates.update(sanitized_outcome=sanitized_outcome or "ambiguous-outcome", last_reconciliation_id=last_reconciliation_id)
    elif record.state in (BrokerSubmissionState.ACKNOWLEDGED, BrokerSubmissionState.PARTIALLY_FILLED) and evidence is BrokerSubmissionEvidence.CANCEL_REQUEST:
        target = BrokerSubmissionState.CANCEL_PENDING
    elif pair == (BrokerSubmissionState.CANCEL_PENDING, BrokerSubmissionEvidence.BROKER_CANCELLATION):
        target = BrokerSubmissionState.CANCELLED
        updates["sanitized_outcome"] = sanitized_outcome or "broker-cancelled"
    elif record.state in (BrokerSubmissionState.ACKNOWLEDGED, BrokerSubmissionState.PARTIALLY_FILLED, BrokerSubmissionState.CANCEL_PENDING) and evidence is BrokerSubmissionEvidence.BROKER_EXPIRATION:
        target = BrokerSubmissionState.EXPIRED
        updates["sanitized_outcome"] = sanitized_outcome or "broker-expired"
    elif record.state in (BrokerSubmissionState.SUBMITTING, BrokerSubmissionState.ACKNOWLEDGED, BrokerSubmissionState.PARTIALLY_FILLED, BrokerSubmissionState.CANCEL_PENDING):
        target = BrokerSubmissionState.RECONCILIATION_REQUIRED
        updates.update(sanitized_outcome=sanitized_outcome or "contradictory-evidence", last_reconciliation_id=last_reconciliation_id)
    else:
        raise BrokerA4ModelError("evidence is invalid for submission state")
    if broker_order_id is not None and record.broker_order_id not in (None, broker_order_id):
        raise BrokerA4ModelError("broker order identity substitution")
    return replace(record, state=target, **updates)


def apply_broker_execution(record, intent, execution):
    for name, value, expected in (("record", record, BrokerSubmissionRecord), ("intent", intent, BrokerOrderIntent), ("execution", execution, BrokerExecutionRecord)):
        _require(name, value, expected)
    if record.state not in (BrokerSubmissionState.ACKNOWLEDGED, BrokerSubmissionState.PARTIALLY_FILLED, BrokerSubmissionState.CANCEL_PENDING):
        raise BrokerA4ModelError("execution cannot apply in this state")
    if (record.intent_id, record.attempt_id, record.broker_order_id, record.stable_client_order_id) != (execution.intent_id, execution.attempt_id, execution.broker_order_id, intent.canonical_client_order_id):
        raise BrokerA4ModelError("execution identity substitution")
    if execution.execution_id in record.execution_ids:
        raise BrokerA4ModelError("duplicate execution_id")
    if record.request_timestamp is None or _timestamp("fill_time", execution.fill_time) < _timestamp("request_timestamp", record.request_timestamp):
        raise BrokerA4ModelError("execution fill precedes SUBMITTING request")
    if _timestamp("received_at", execution.received_at) < _timestamp("recorded_at", record.recorded_at):
        raise BrokerA4ModelError("execution precedes lifecycle record")
    cumulative = record.cumulative_filled_quantity + execution.fill_quantity
    if execution.cumulative_quantity != cumulative or cumulative > intent.quantity:
        raise BrokerA4ModelError("execution cumulative quantity is invalid")
    remaining = intent.quantity - cumulative
    return replace(record, state=BrokerSubmissionState.FILLED if remaining == 0 else BrokerSubmissionState.PARTIALLY_FILLED, cumulative_filled_quantity=cumulative, remaining_quantity=remaining, execution_ids=tuple(sorted((*record.execution_ids, execution.execution_id))), recorded_at=execution.received_at)


__all__ = [name for name in globals() if name.startswith(("apply_", "build_", "evaluate_", "prepare_", "reserve_", "transition_"))]

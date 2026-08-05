"""Research-only strategy qualification models and pure evaluation boundary."""

from tw_stock_tool.qualification.derivation import derive_qualification_outcome
from tw_stock_tool.qualification.evaluator import evaluate_strategy_qualification
from tw_stock_tool.qualification.findings import (
    SUPPORTED_FINDING_CODES,
    QualificationFindingError,
    finding_reason_codes,
    normalize_findings,
)
from tw_stock_tool.qualification.models import (
    STRATEGY_QUALIFICATION_ARTIFACT_TYPE,
    STRATEGY_QUALIFICATION_SCHEMA_VERSION,
    EvidenceScope,
    FindingSeverity,
    PromotionState,
    PromotionDecision,
    DEFAULT_FINDING_SEVERITIES,
    QualificationFinding,
    QualificationMetricSet,
    QualificationModelError,
    QualificationPolicy,
    StrategyDescriptor,
    StrategyQualificationRequest,
    StrategyQualificationResult,
)
from tw_stock_tool.qualification.policies import (
    SUPPORTED_QUALIFICATION_POLICIES,
    TAIWAN_EQUITY_DAILY_V1,
    QualificationPolicyError,
    is_supported_qualification_policy,
    resolve_finding_severity,
    resolve_qualification_policy,
)
from tw_stock_tool.qualification.serialization import (
    QualificationSerializationError,
    deserialize_strategy_qualification_result,
    export_strategy_qualification_json,
    load_strategy_qualification_json,
    serialize_strategy_qualification_result,
)

__all__ = [
    "DEFAULT_FINDING_SEVERITIES",
    "STRATEGY_QUALIFICATION_ARTIFACT_TYPE",
    "STRATEGY_QUALIFICATION_SCHEMA_VERSION",
    "SUPPORTED_FINDING_CODES",
    "SUPPORTED_QUALIFICATION_POLICIES",
    "TAIWAN_EQUITY_DAILY_V1",
    "EvidenceScope",
    "FindingSeverity",
    "PromotionState",
    "PromotionDecision",
    "QualificationFinding",
    "QualificationFindingError",
    "QualificationMetricSet",
    "QualificationModelError",
    "QualificationPolicy",
    "QualificationPolicyError",
    "QualificationSerializationError",
    "StrategyDescriptor",
    "StrategyQualificationRequest",
    "StrategyQualificationResult",
    "deserialize_strategy_qualification_result",
    "derive_qualification_outcome",
    "evaluate_strategy_qualification",
    "export_strategy_qualification_json",
    "finding_reason_codes",
    "is_supported_qualification_policy",
    "load_strategy_qualification_json",
    "normalize_findings",
    "resolve_finding_severity",
    "resolve_qualification_policy",
    "serialize_strategy_qualification_result",
]

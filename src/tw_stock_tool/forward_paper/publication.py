"""Immutable schema-1.0 anchor for a published forward-paper package."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any
from uuid import UUID

from tw_stock_tool.artifacts.workspace import validate_artifact_path
from tw_stock_tool.forward_paper.eligibility_models import (
    FORWARD_ELIGIBILITY_POLICY_ID,
    FORWARD_ELIGIBILITY_POLICY_VERSION,
    ForwardEligibilityState,
)


PUBLICATION_SCHEMA_VERSION = "1.0"
PUBLICATION_ARTIFACT_TYPE = "forward_paper_publication_index"
PUBLICATION_INDEX_PATH = "artifacts/forward-paper/publication-index.json"
RECOMMENDATION_DIRECTORY = "artifacts/forward-paper/recommendations"
PUBLICATION_ARTIFACT_SPECS = (
    ("qualification", "universe_oos_evidence", "1.0", "artifacts/forward-paper/qualification.json"),
    ("activation", "forward_paper_activation", "1.0", "artifacts/forward-paper/activation.json"),
    ("decision_ledger", "forward_paper_decision_ledger", "1.0", "artifacts/forward-paper/decision-ledger.json"),
    ("portfolio_result", "simulated_portfolio_trading_result", 1, "artifacts/forward-paper/portfolio-result.json"),
    ("execution_evidence", "forward_execution_evidence", "1.0", "artifacts/forward-paper/execution-evidence.json"),
    ("portfolio_trace", "forward_portfolio_trace", "1.0", "artifacts/forward-paper/portfolio-trace.json"),
    ("metrics_evidence", "forward_metrics_evidence", "1.0", "artifacts/forward-paper/metrics-evidence.json"),
    ("eligibility_evidence", "forward_eligibility_evidence", "1.0", "artifacts/forward-paper/eligibility-evidence.json"),
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class ForwardPaperPublicationError(ValueError):
    """Raised when a publication index violates schema 1.0."""


def _clean(name: str, value: object) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ForwardPaperPublicationError(f"{name} must be an exact clean non-empty string")
    return value


def _uuid(name: str, value: object) -> str:
    value = _clean(name, value)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ForwardPaperPublicationError(f"{name} must be a canonical lowercase UUID v4") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ForwardPaperPublicationError(f"{name} must be a canonical lowercase UUID v4")
    return value


def _timestamp(name: str, value: object) -> str:
    value = _clean(name, value)
    try:
        parsed = datetime.strptime(value, _TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise ForwardPaperPublicationError(f"{name} must use YYYY-MM-DDTHH:MM:SSZ") from exc
    if parsed.strftime(_TIMESTAMP_FORMAT) != value:
        raise ForwardPaperPublicationError(f"{name} must use YYYY-MM-DDTHH:MM:SSZ")
    return value


def _sha(name: str, value: object) -> str:
    value = _clean(name, value)
    if _SHA256.fullmatch(value) is None:
        raise ForwardPaperPublicationError(f"{name} must be a lowercase SHA-256")
    return value


def _path(name: str, value: object) -> str:
    value = _clean(name, value)
    try:
        validate_artifact_path(value)
    except ValueError as exc:
        raise ForwardPaperPublicationError(f"{name} must be a safe Workspace artifact path") from exc
    return value


@dataclass(frozen=True, slots=True)
class ForwardRecommendationAnchor:
    recommendation_id: str
    recommendation_sha256: str
    path: str

    def __post_init__(self) -> None:
        recommendation_id = _uuid("recommendation_id", self.recommendation_id)
        _sha("recommendation_sha256", self.recommendation_sha256)
        expected = f"{RECOMMENDATION_DIRECTORY}/{recommendation_id}.json"
        if _path("path", self.path) != expected:
            raise ForwardPaperPublicationError("recommendation path is not canonical")


@dataclass(frozen=True, slots=True)
class ForwardPublishedArtifactAnchor:
    role: str
    artifact_type: str
    schema_version: int | str
    media_type: str
    path: str
    sha256: str

    def __post_init__(self) -> None:
        _clean("role", self.role)
        _clean("artifact_type", self.artifact_type)
        if type(self.schema_version) is int:
            if self.schema_version < 1:
                raise ForwardPaperPublicationError("schema_version integer must be positive")
        elif type(self.schema_version) is str:
            _clean("schema_version", self.schema_version)
        else:
            raise ForwardPaperPublicationError("schema_version must be an exact int or str")
        if self.media_type != "application/json":
            raise ForwardPaperPublicationError("media_type must be application/json")
        _path("path", self.path)
        _sha("sha256", self.sha256)


@dataclass(frozen=True, slots=True)
class ForwardPaperPublicationIndex:
    schema_version: str
    artifact_type: str
    publication_id: str
    created_at: str
    activation_id: str
    qualification_evaluation_id: str
    ledger_id: str
    execution_evidence_id: str
    metrics_id: str
    eligibility_id: str
    strategy_id: str
    policy_id: str
    policy_version: str
    eligibility_state: ForwardEligibilityState
    qualification_sha256: str
    activation_sha256: str
    ledger_sha256: str
    portfolio_result_sha256: str
    execution_evidence_sha256: str
    portfolio_trace_sha256: str
    metrics_sha256: str
    eligibility_sha256: str
    recommendation_anchors: tuple[ForwardRecommendationAnchor, ...]
    artifact_anchors: tuple[ForwardPublishedArtifactAnchor, ...]

    def __post_init__(self) -> None:
        if self.schema_version != PUBLICATION_SCHEMA_VERSION:
            raise ForwardPaperPublicationError("schema_version must be '1.0'")
        if self.artifact_type != PUBLICATION_ARTIFACT_TYPE:
            raise ForwardPaperPublicationError("artifact_type is not supported")
        _uuid("publication_id", self.publication_id)
        _timestamp("created_at", self.created_at)
        for name in (
            "activation_id", "qualification_evaluation_id", "ledger_id",
            "execution_evidence_id", "metrics_id", "eligibility_id",
        ):
            _uuid(name, getattr(self, name))
        for name in (
            "qualification_sha256", "activation_sha256", "ledger_sha256",
            "portfolio_result_sha256", "execution_evidence_sha256",
            "portfolio_trace_sha256", "metrics_sha256",
            "eligibility_sha256",
        ):
            _sha(name, getattr(self, name))
        _clean("strategy_id", self.strategy_id)
        if (
            self.policy_id != FORWARD_ELIGIBILITY_POLICY_ID
            or self.policy_version != FORWARD_ELIGIBILITY_POLICY_VERSION
        ):
            raise ForwardPaperPublicationError("eligibility policy is not supported")
        if type(self.eligibility_state) is not ForwardEligibilityState:
            raise ForwardPaperPublicationError("eligibility_state must be ForwardEligibilityState")
        if type(self.recommendation_anchors) is not tuple or any(
            type(item) is not ForwardRecommendationAnchor for item in self.recommendation_anchors
        ):
            raise ForwardPaperPublicationError("recommendation_anchors must be an exact anchor tuple")
        recommendation_ids = tuple(item.recommendation_id for item in self.recommendation_anchors)
        recommendation_paths = tuple(item.path for item in self.recommendation_anchors)
        recommendation_hashes = tuple(item.recommendation_sha256 for item in self.recommendation_anchors)
        if (
            len(set(recommendation_ids)) != len(recommendation_ids)
            or len(set(recommendation_paths)) != len(recommendation_paths)
            or len(set(recommendation_hashes)) != len(recommendation_hashes)
        ):
            raise ForwardPaperPublicationError("recommendation anchors must be unique")
        if type(self.artifact_anchors) is not tuple or any(
            type(item) is not ForwardPublishedArtifactAnchor for item in self.artifact_anchors
        ):
            raise ForwardPaperPublicationError("artifact_anchors must be an exact anchor tuple")
        expected = tuple(
            ForwardPublishedArtifactAnchor(
                role,
                artifact_type,
                schema,
                "application/json",
                path,
                getattr(
                    self,
                    {
                        "decision_ledger": "ledger_sha256",
                        "metrics_evidence": "metrics_sha256",
                        "eligibility_evidence": "eligibility_sha256",
                    }.get(role, f"{role}_sha256"),
                ),
            )
            for role, artifact_type, schema, path in PUBLICATION_ARTIFACT_SPECS
        )
        if self.artifact_anchors != expected:
            raise ForwardPaperPublicationError("artifact anchors must match the frozen role order and root hashes")


_ROOT_FIELDS = (
    "schema_version", "artifact_type", "publication_id", "created_at",
    "activation_id", "qualification_evaluation_id", "ledger_id",
    "execution_evidence_id", "metrics_id", "eligibility_id", "strategy_id",
    "policy_id", "policy_version", "eligibility_state", "qualification_sha256",
    "activation_sha256", "ledger_sha256", "portfolio_result_sha256",
    "execution_evidence_sha256", "portfolio_trace_sha256",
    "metrics_sha256", "eligibility_sha256",
    "recommendation_anchors", "artifact_anchors",
)
_RECOMMENDATION_FIELDS = ("recommendation_id", "recommendation_sha256", "path")
_ARTIFACT_FIELDS = ("role", "artifact_type", "schema_version", "media_type", "path", "sha256")


def _strict_object(value: Any, fields: tuple[str, ...], path: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise ForwardPaperPublicationError(f"{path} must be an exact object")
    missing = [field for field in fields if field not in value]
    unknown = [field for field in value if field not in fields]
    if missing or unknown:
        raise ForwardPaperPublicationError(f"{path} fields mismatch: missing={missing}, unknown={unknown}")
    return value


def serialize_forward_paper_publication_index(artifact: ForwardPaperPublicationIndex) -> dict[str, Any]:
    if type(artifact) is not ForwardPaperPublicationIndex:
        raise ForwardPaperPublicationError("expected an exact ForwardPaperPublicationIndex")
    result = {field: getattr(artifact, field) for field in _ROOT_FIELDS[:-2]}
    result["eligibility_state"] = artifact.eligibility_state.value
    result["recommendation_anchors"] = [
        {field: getattr(anchor, field) for field in _RECOMMENDATION_FIELDS}
        for anchor in artifact.recommendation_anchors
    ]
    result["artifact_anchors"] = [
        {field: getattr(anchor, field) for field in _ARTIFACT_FIELDS}
        for anchor in artifact.artifact_anchors
    ]
    return result


def export_forward_paper_publication_index_json(artifact: ForwardPaperPublicationIndex) -> str:
    try:
        return json.dumps(
            serialize_forward_paper_publication_index(artifact),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise ForwardPaperPublicationError(str(exc)) from exc


def deserialize_forward_paper_publication_index(data: dict[str, Any]) -> ForwardPaperPublicationIndex:
    root = _strict_object(data, _ROOT_FIELDS, "$")
    recommendations = root["recommendation_anchors"]
    artifacts = root["artifact_anchors"]
    if type(recommendations) is not list or type(artifacts) is not list:
        raise ForwardPaperPublicationError("anchor collections must be exact arrays")
    try:
        recommendation_anchors = tuple(
            ForwardRecommendationAnchor(**_strict_object(value, _RECOMMENDATION_FIELDS, f"$.recommendation_anchors[{index}]"))
            for index, value in enumerate(recommendations)
        )
        artifact_anchors = tuple(
            ForwardPublishedArtifactAnchor(**_strict_object(value, _ARTIFACT_FIELDS, f"$.artifact_anchors[{index}]"))
            for index, value in enumerate(artifacts)
        )
        values = {field: root[field] for field in _ROOT_FIELDS[:-2]}
        values["eligibility_state"] = ForwardEligibilityState(values["eligibility_state"])
        return ForwardPaperPublicationIndex(
            **values,
            recommendation_anchors=recommendation_anchors,
            artifact_anchors=artifact_anchors,
        )
    except (TypeError, ValueError) as exc:
        raise ForwardPaperPublicationError(f"$ model validation failed: {exc}") from exc


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ForwardPaperPublicationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ForwardPaperPublicationError(f"non-finite JSON constant is not allowed: {value}")


def load_forward_paper_publication_index_json(text: str) -> ForwardPaperPublicationIndex:
    if type(text) is not str:
        raise ForwardPaperPublicationError("JSON input must be an exact string")
    try:
        payload = json.loads(text, object_pairs_hook=_object_pairs, parse_constant=_constant)
    except ForwardPaperPublicationError:
        raise
    except json.JSONDecodeError as exc:
        raise ForwardPaperPublicationError(f"invalid JSON: {exc.msg}") from exc
    return deserialize_forward_paper_publication_index(payload)


__all__ = [
    "PUBLICATION_ARTIFACT_SPECS", "PUBLICATION_ARTIFACT_TYPE",
    "PUBLICATION_INDEX_PATH", "PUBLICATION_SCHEMA_VERSION",
    "ForwardPaperPublicationError", "ForwardPaperPublicationIndex",
    "ForwardPublishedArtifactAnchor", "ForwardRecommendationAnchor",
    "deserialize_forward_paper_publication_index",
    "export_forward_paper_publication_index_json",
    "load_forward_paper_publication_index_json",
    "serialize_forward_paper_publication_index",
]


"""Immutable Phase 56.5C persistence, audit, and recovery facts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import re
from typing import Protocol

from tw_stock_tool.broker_safety.models import BrokerEnvironment, _clean, _timestamp


STORE_SCHEMA_VERSION = 1
ZERO_AUDIT_DIGEST = "0" * 64
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class BrokerSafetyStoreError(RuntimeError):
    """Fail-closed durable-store error without raw database details."""


class LeaseConflictError(BrokerSafetyStoreError):
    """The account lease belongs to another live owner."""


class StaleFenceError(BrokerSafetyStoreError):
    """A controller write presented a stale fencing token."""


class PersistenceConflictError(BrokerSafetyStoreError):
    """An immutable identity maps to conflicting facts."""


class StoreCorruptionError(BrokerSafetyStoreError):
    """Persisted bytes, schema, references, or audit linkage are invalid."""


class RestoreRejectedError(BrokerSafetyStoreError):
    """A backup cannot safely become the active store."""


def _exact_nonnegative(name: str, value: int) -> None:
    if type(value) is not int or value < 0:
        raise BrokerSafetyStoreError(f"{name} must be an exact non-negative integer")


def _exact_positive(name: str, value: int) -> None:
    if type(value) is not int or value <= 0:
        raise BrokerSafetyStoreError(f"{name} must be an exact positive integer")


def _digest(name: str, value: str) -> None:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise BrokerSafetyStoreError(f"{name} must be a lowercase SHA-256 digest")


def _optional_text(name: str, value: str | None) -> None:
    if value is not None:
        _clean(name, value)


class ClaimDisposition(StrEnum):
    ACQUIRED = "ACQUIRED"
    ALREADY_CLAIMED = "ALREADY_CLAIMED"


class PreSubmitDisposition(StrEnum):
    COMMITTED = "COMMITTED"
    ALREADY_COMMITTED = "ALREADY_COMMITTED"


@dataclass(frozen=True, slots=True)
class BrokerAccountScope:
    broker_id: str
    environment: BrokerEnvironment
    account_reference: str

    def __post_init__(self) -> None:
        _clean("broker_id", self.broker_id)
        if type(self.environment) is not BrokerEnvironment:
            raise BrokerSafetyStoreError("environment must be an exact BrokerEnvironment")
        _clean("account_reference", self.account_reference)


@dataclass(frozen=True, slots=True)
class BrokerAccountLease:
    scope: BrokerAccountScope
    owner_id: str
    fencing_token: int
    acquired_at: str
    expires_at: str
    last_renewed_at: str

    def __post_init__(self) -> None:
        if type(self.scope) is not BrokerAccountScope:
            raise BrokerSafetyStoreError("scope must be an exact BrokerAccountScope")
        _clean("owner_id", self.owner_id)
        _exact_positive("fencing_token", self.fencing_token)
        acquired = _timestamp("acquired_at", self.acquired_at)
        renewed = _timestamp("last_renewed_at", self.last_renewed_at)
        expires = _timestamp("expires_at", self.expires_at)
        if not acquired <= renewed < expires:
            raise BrokerSafetyStoreError("lease chronology is invalid")


@dataclass(frozen=True, slots=True)
class AuthorizationClaimResult:
    disposition: ClaimDisposition
    authorization_use_id: str

    def __post_init__(self) -> None:
        if type(self.disposition) is not ClaimDisposition:
            raise BrokerSafetyStoreError("disposition must be an exact ClaimDisposition")
        _clean("authorization_use_id", self.authorization_use_id)


@dataclass(frozen=True, slots=True)
class PreSubmitCommit:
    disposition: PreSubmitDisposition
    persistence_version: str
    authorization_use_id: str
    intent_id: str
    attempt_id: str
    fencing_token: int
    audit_sequence: int
    audit_root_digest: str

    def __post_init__(self) -> None:
        if type(self.disposition) is not PreSubmitDisposition:
            raise BrokerSafetyStoreError("disposition must be an exact PreSubmitDisposition")
        for name in (
            "persistence_version",
            "authorization_use_id",
            "intent_id",
            "attempt_id",
        ):
            _clean(name, getattr(self, name))
        _exact_positive("fencing_token", self.fencing_token)
        _exact_positive("audit_sequence", self.audit_sequence)
        _digest("audit_root_digest", self.audit_root_digest)


@dataclass(frozen=True, slots=True)
class BrokerAuditRecord:
    store_id: str
    scope_key: str
    sequence: int
    record_id: str
    event_type: str
    occurred_at: str
    recorded_at: str
    actor_reference: str
    references_json: str
    sanitized_payload_digest: str
    previous_record_digest: str
    record_digest: str
    external_anchor_reference: str | None

    def __post_init__(self) -> None:
        for name in ("store_id", "scope_key", "record_id", "event_type", "actor_reference"):
            _clean(name, getattr(self, name))
        _exact_positive("sequence", self.sequence)
        if _timestamp("occurred_at", self.occurred_at) > _timestamp("recorded_at", self.recorded_at):
            raise BrokerSafetyStoreError("audit chronology is invalid")
        try:
            references = json.loads(self.references_json)
        except (TypeError, json.JSONDecodeError) as exc:
            raise BrokerSafetyStoreError("references_json must be valid JSON") from exc
        if (
            json.dumps(
                references,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            != self.references_json
        ):
            raise BrokerSafetyStoreError("references_json must be canonical")
        if type(references) is not dict or any(type(name) is not str or type(value) is not str for name, value in references.items()):
            raise BrokerSafetyStoreError("audit references must be string mappings")
        _digest("sanitized_payload_digest", self.sanitized_payload_digest)
        _digest("previous_record_digest", self.previous_record_digest)
        _digest("record_digest", self.record_digest)
        _optional_text("external_anchor_reference", self.external_anchor_reference)


@dataclass(frozen=True, slots=True)
class AuditAnchorBundle:
    schema_version: str
    store_id: str
    scope_key: str
    store_schema_version: int
    first_audit_sequence: int
    last_audit_sequence: int
    audit_root_digest: str
    created_at: str
    previous_receipt_reference: str | None

    def __post_init__(self) -> None:
        if self.schema_version != "audit_anchor_bundle_v1":
            raise BrokerSafetyStoreError("unsupported audit anchor bundle schema")
        _clean("store_id", self.store_id)
        _clean("scope_key", self.scope_key)
        if type(self.store_schema_version) is not int or self.store_schema_version != STORE_SCHEMA_VERSION:
            raise BrokerSafetyStoreError("unsupported store schema version")
        _exact_positive("first_audit_sequence", self.first_audit_sequence)
        _exact_positive("last_audit_sequence", self.last_audit_sequence)
        if self.first_audit_sequence > self.last_audit_sequence:
            raise BrokerSafetyStoreError("audit anchor sequence range is invalid")
        _digest("audit_root_digest", self.audit_root_digest)
        _timestamp("created_at", self.created_at)
        _optional_text("previous_receipt_reference", self.previous_receipt_reference)


@dataclass(frozen=True, slots=True)
class ExternalAuditAnchorReceipt:
    schema_version: str
    receipt_id: str
    bundle_sha256: str
    target: str
    object_reference: str
    anchored_at: str

    def __post_init__(self) -> None:
        if self.schema_version != "external_audit_anchor_receipt_v1":
            raise BrokerSafetyStoreError("unsupported external anchor receipt schema")
        _clean("receipt_id", self.receipt_id)
        _digest("bundle_sha256", self.bundle_sha256)
        _clean("target", self.target)
        _clean("object_reference", self.object_reference)
        _timestamp("anchored_at", self.anchored_at)


class ExternalAuditAnchorPort(Protocol):
    def anchor(self, bundle: AuditAnchorBundle) -> ExternalAuditAnchorReceipt: ...


@dataclass(frozen=True, slots=True)
class TrustedRecoveryCheckpoint:
    store_id: str
    scope_key: str
    minimum_audit_sequence: int
    audit_root_digest: str
    high_water_summary_sha256: str
    maximum_fencing_token: int

    def __post_init__(self) -> None:
        _clean("store_id", self.store_id)
        _clean("scope_key", self.scope_key)
        _exact_positive("minimum_audit_sequence", self.minimum_audit_sequence)
        _digest("audit_root_digest", self.audit_root_digest)
        _digest("high_water_summary_sha256", self.high_water_summary_sha256)
        _exact_positive("maximum_fencing_token", self.maximum_fencing_token)


@dataclass(frozen=True, slots=True)
class ScopeAuditCheckpoint:
    scope_key: str
    last_audit_sequence: int
    last_audit_root: str
    latest_external_receipt_reference: str | None
    high_water_summary_sha256: str
    maximum_fencing_token: int

    def __post_init__(self) -> None:
        _clean("scope_key", self.scope_key)
        _exact_nonnegative("last_audit_sequence", self.last_audit_sequence)
        _digest("last_audit_root", self.last_audit_root)
        if (self.last_audit_sequence == 0) != (self.last_audit_root == ZERO_AUDIT_DIGEST):
            raise BrokerSafetyStoreError("scope audit checkpoint is inconsistent")
        _optional_text(
            "latest_external_receipt_reference",
            self.latest_external_receipt_reference,
        )
        _digest("high_water_summary_sha256", self.high_water_summary_sha256)
        _exact_positive("maximum_fencing_token", self.maximum_fencing_token)


@dataclass(frozen=True, slots=True)
class BackupManifest:
    schema_version: str
    store_id: str
    store_schema_version: int
    backup_timestamp: str
    database_sha256: str
    scope_audit_checkpoints: tuple[ScopeAuditCheckpoint, ...]
    high_water_summary_sha256: str

    def __post_init__(self) -> None:
        if self.schema_version != "broker_store_backup_manifest_v3":
            raise BrokerSafetyStoreError("unsupported backup manifest schema")
        _clean("store_id", self.store_id)
        if type(self.store_schema_version) is not int or self.store_schema_version != STORE_SCHEMA_VERSION:
            raise BrokerSafetyStoreError("unsupported backup store schema")
        _timestamp("backup_timestamp", self.backup_timestamp)
        _digest("database_sha256", self.database_sha256)
        if (
            type(self.scope_audit_checkpoints) is not tuple
            or any(type(item) is not ScopeAuditCheckpoint for item in self.scope_audit_checkpoints)
            or tuple(item.scope_key for item in self.scope_audit_checkpoints) != tuple(sorted(item.scope_key for item in self.scope_audit_checkpoints))
            or len({item.scope_key for item in self.scope_audit_checkpoints}) != len(self.scope_audit_checkpoints)
        ):
            raise BrokerSafetyStoreError("scope audit checkpoints must be exact, unique, and sorted")
        _digest("high_water_summary_sha256", self.high_water_summary_sha256)


@dataclass(frozen=True, slots=True)
class BrokerRecoveryPlan:
    scope: BrokerAccountScope
    fencing_token: int | None
    high_water_count: int
    authorization_use_count: int
    intent_count: int
    nonterminal_submission_count: int
    unresolved_submission_count: int
    latest_kill_switch_version: str | None
    last_audit_sequence: int
    last_audit_root: str
    last_external_receipt_reference: str | None
    last_external_anchor_sequence: int | None
    last_external_anchor_root: str | None
    last_external_anchor_target: str | None
    blocks_new_authorization: bool
    blocking_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.scope) is not BrokerAccountScope:
            raise BrokerSafetyStoreError("scope must be exact")
        if self.fencing_token is not None:
            _exact_positive("fencing_token", self.fencing_token)
        for name in (
            "high_water_count",
            "authorization_use_count",
            "intent_count",
            "nonterminal_submission_count",
            "unresolved_submission_count",
            "last_audit_sequence",
        ):
            _exact_nonnegative(name, getattr(self, name))
        if self.unresolved_submission_count > self.nonterminal_submission_count:
            raise BrokerSafetyStoreError("recovery submission counts are inconsistent")
        _optional_text("latest_kill_switch_version", self.latest_kill_switch_version)
        _digest("last_audit_root", self.last_audit_root)
        _optional_text(
            "last_external_receipt_reference",
            self.last_external_receipt_reference,
        )
        if self.last_external_anchor_sequence is not None:
            _exact_positive(
                "last_external_anchor_sequence",
                self.last_external_anchor_sequence,
            )
        if self.last_external_anchor_root is not None:
            _digest("last_external_anchor_root", self.last_external_anchor_root)
        _optional_text("last_external_anchor_target", self.last_external_anchor_target)
        anchor_values = (
            self.last_external_receipt_reference,
            self.last_external_anchor_sequence,
            self.last_external_anchor_root,
            self.last_external_anchor_target,
        )
        if any(value is None for value in anchor_values) != all(value is None for value in anchor_values):
            raise BrokerSafetyStoreError("external anchor recovery checkpoint is incomplete")
        if type(self.blocks_new_authorization) is not bool:
            raise BrokerSafetyStoreError("blocks_new_authorization must be an exact bool")
        if type(self.blocking_reasons) is not tuple or any(type(reason) is not str or not reason for reason in self.blocking_reasons):
            raise BrokerSafetyStoreError("blocking_reasons must be a tuple of strings")
        if self.blocks_new_authorization != bool(self.blocking_reasons):
            raise BrokerSafetyStoreError("recovery blocking state is inconsistent")


__all__ = [
    "AuditAnchorBundle",
    "AuthorizationClaimResult",
    "BackupManifest",
    "BrokerAccountLease",
    "BrokerAccountScope",
    "BrokerAuditRecord",
    "BrokerRecoveryPlan",
    "BrokerSafetyStoreError",
    "ClaimDisposition",
    "PreSubmitDisposition",
    "ExternalAuditAnchorPort",
    "ExternalAuditAnchorReceipt",
    "LeaseConflictError",
    "PersistenceConflictError",
    "PreSubmitCommit",
    "RestoreRejectedError",
    "ScopeAuditCheckpoint",
    "STORE_SCHEMA_VERSION",
    "StaleFenceError",
    "StoreCorruptionError",
    "TrustedRecoveryCheckpoint",
    "ZERO_AUDIT_DIGEST",
]

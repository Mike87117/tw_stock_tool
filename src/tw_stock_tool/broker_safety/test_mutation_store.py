"""TEST-only lifecycle sidecar bound read-only to Phase C authority."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Iterator
from uuid import UUID, uuid4

from tw_stock_tool.broker_safety.durable_models import (
    BrokerAccountScope,
    BrokerSafetyStoreError,
    PersistenceConflictError,
    StoreCorruptionError,
    ZERO_AUDIT_DIGEST,
)
from tw_stock_tool.broker_safety.durable_store import (
    SQLiteBrokerSafetyStore,
    _scope_key as _phase_c_scope_key,
)
from tw_stock_tool.broker_safety.models import BrokerEnvironment, _clean, _timestamp
from tw_stock_tool.broker_safety.test_mutation_models import (
    TEST_MUTATION_SCHEMA_VERSION,
    TEST_PRE_SUBMIT_PERSISTENCE_VERSION,
    TEST_PROVIDER_BINDING_SCHEMA_VERSION,
    BrokerTestExecutionAuthorization,
    BrokerTestMutationEnvelope,
    BrokerTestOperatorOptIn,
    BrokerTestMutationPolicy,
    BrokerTestPreSubmitCommit,
    BrokerTestSubmissionRecord,
    DurableTestProviderTagBinding,
    TestSubmissionState,
    _TEST_BINDING_AUTHORITY,
    _TEST_OPT_IN_AUTHORITY,
    test_mutation_artifact_sha256,
)
from tw_stock_tool.broker_safety.test_mutation_serialization import (
    export_test_mutation_artifact_json,
    load_test_mutation_artifact_json,
)


TEST_STORE_SCHEMA_VERSION = 2
TEST_STORE_MIGRATION_ID = "002_phase_56_5d0_1_phase_c_authority_bound"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SAFE = re.compile(r"[A-Za-z0-9_.:/-]+\Z")
_FORBIDDEN = re.compile(
    r"(?i)(password|api[_-]?key|secret|token|certificate|private[_-]?key|raw[_-]?(account|request|response))"
)

_SCHEMA = (
    "CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE test_scopes(scope_key TEXT PRIMARY KEY, broker_id TEXT NOT NULL, environment TEXT NOT NULL, account_reference TEXT NOT NULL, phase_c_store_id TEXT NOT NULL, UNIQUE(broker_id, environment, account_reference))",
    "CREATE TABLE policies(scope_key TEXT NOT NULL REFERENCES test_scopes(scope_key), policy_sha256 TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, policy_sha256))",
    "CREATE TABLE envelopes(scope_key TEXT NOT NULL REFERENCES test_scopes(scope_key), envelope_id TEXT NOT NULL, economic_intent_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, client_order_id TEXT NOT NULL, sequence INTEGER NOT NULL CHECK(sequence > 0), artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, envelope_id), UNIQUE(scope_key, economic_intent_id), UNIQUE(scope_key, idempotency_key), UNIQUE(scope_key, client_order_id))",
    "CREATE TABLE phase_c_provider_binding_refs(scope_key TEXT NOT NULL REFERENCES test_scopes(scope_key), provider_name TEXT NOT NULL, provider_tag TEXT NOT NULL, canonical_client_id TEXT NOT NULL, envelope_id TEXT NOT NULL, fencing_token INTEGER NOT NULL CHECK(fencing_token > 0), mapped_at TEXT NOT NULL, phase_c_audit_sequence INTEGER NOT NULL CHECK(phase_c_audit_sequence > 0), phase_c_audit_root TEXT NOT NULL, mapping_audit_sequence INTEGER NOT NULL CHECK(mapping_audit_sequence > 0), PRIMARY KEY(scope_key, provider_name, provider_tag), UNIQUE(scope_key, provider_name, canonical_client_id))",
    "CREATE TABLE operator_opt_ins(scope_key TEXT NOT NULL REFERENCES test_scopes(scope_key), operator_opt_in_id TEXT NOT NULL, envelope_id TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, fencing_token INTEGER NOT NULL CHECK(fencing_token > 0), issue_audit_sequence INTEGER NOT NULL CHECK(issue_audit_sequence > 0), PRIMARY KEY(scope_key, operator_opt_in_id), UNIQUE(scope_key, envelope_id))",
    "CREATE TABLE authorizations(scope_key TEXT NOT NULL REFERENCES test_scopes(scope_key), authorization_id TEXT NOT NULL, envelope_id TEXT NOT NULL, operator_opt_in_id TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, authorization_id), UNIQUE(scope_key, envelope_id), UNIQUE(scope_key, operator_opt_in_id))",
    "CREATE TABLE authorization_uses(scope_key TEXT NOT NULL REFERENCES test_scopes(scope_key), authorization_id TEXT NOT NULL, operator_opt_in_id TEXT NOT NULL, attempt_id TEXT NOT NULL, used_at TEXT NOT NULL, PRIMARY KEY(scope_key, authorization_id), UNIQUE(scope_key, operator_opt_in_id), UNIQUE(scope_key, attempt_id))",
    "CREATE TABLE pre_submit_commits(scope_key TEXT NOT NULL REFERENCES test_scopes(scope_key), authorization_id TEXT NOT NULL, operator_opt_in_id TEXT NOT NULL, envelope_id TEXT NOT NULL, attempt_id TEXT NOT NULL, persistence_version TEXT NOT NULL, request_sha256 TEXT NOT NULL, submission_sha256 TEXT NOT NULL, audit_sequence INTEGER NOT NULL, audit_root_digest TEXT NOT NULL, fencing_token INTEGER NOT NULL, PRIMARY KEY(scope_key, authorization_id), UNIQUE(scope_key, envelope_id), UNIQUE(scope_key, attempt_id))",
    "CREATE TABLE submissions_current(scope_key TEXT NOT NULL REFERENCES test_scopes(scope_key), envelope_id TEXT NOT NULL, attempt_id TEXT NOT NULL, state TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0), artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, envelope_id, attempt_id))",
    "CREATE TABLE submission_history(scope_key TEXT NOT NULL REFERENCES test_scopes(scope_key), envelope_id TEXT NOT NULL, attempt_id TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL, transition_kind TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, envelope_id, attempt_id, version))",
    "CREATE TABLE high_water(scope_key TEXT NOT NULL REFERENCES test_scopes(scope_key), trading_date TEXT NOT NULL, maximum_sequence INTEGER NOT NULL CHECK(maximum_sequence > 0), submitted_notional TEXT NOT NULL, PRIMARY KEY(scope_key, trading_date))",
    "CREATE TABLE audit(scope_key TEXT NOT NULL REFERENCES test_scopes(scope_key), sequence INTEGER NOT NULL CHECK(sequence > 0), event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, actor_reference TEXT NOT NULL, references_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL, previous_digest TEXT NOT NULL, record_digest TEXT NOT NULL, PRIMARY KEY(scope_key, sequence), UNIQUE(scope_key, record_digest))",
)
TEST_STORE_MIGRATION_CHECKSUM = sha256("\n".join(_SCHEMA).encode()).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value: bytes) -> str:
    return sha256(value).hexdigest()


def _scope_key(scope: BrokerAccountScope) -> str:
    if type(scope) is not BrokerAccountScope:
        raise BrokerSafetyStoreError("scope must be an exact BrokerAccountScope")
    return _digest(
        _canonical(
            {
                "account_reference": scope.account_reference,
                "broker_id": scope.broker_id,
                "environment": scope.environment.value,
                "schema_version": "broker_test_account_scope_v1",
            }
        )
    )


def _safe(name: str, value: object) -> str:
    text = _clean(name, value)
    if _FORBIDDEN.search(name) or _FORBIDDEN.search(text) or _SAFE.fullmatch(text) is None:
        raise BrokerSafetyStoreError(f"{name} is unsafe for TEST durable storage")
    return text


def _artifact(value: object) -> tuple[str, str]:
    text = export_test_mutation_artifact_json(value)
    return text, _digest(text.encode("utf-8"))


@dataclass(frozen=True, slots=True)
class BrokerTestMutationRecoveryPlan:
    scope: BrokerAccountScope
    fencing_token: int | None
    envelope_count: int
    authorization_use_count: int
    active_order_count: int
    unresolved_submission_count: int
    last_audit_sequence: int
    last_audit_root: str
    blocks_new_test_submission: bool
    blocking_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.scope) is not BrokerAccountScope or self.scope.environment is not BrokerEnvironment.SANDBOX:
            raise BrokerSafetyStoreError("TEST recovery scope must be exact SANDBOX")
        for name in (
            "envelope_count",
            "authorization_use_count",
            "active_order_count",
            "unresolved_submission_count",
            "last_audit_sequence",
        ):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise BrokerSafetyStoreError(f"{name} must be exact and nonnegative")
        if self.fencing_token is not None and (type(self.fencing_token) is not int or self.fencing_token <= 0):
            raise BrokerSafetyStoreError("fencing_token must be exact and positive")
        if _SHA.fullmatch(self.last_audit_root) is None:
            raise BrokerSafetyStoreError("audit root must be a SHA-256")
        if self.blocks_new_test_submission != bool(self.blocking_reasons):
            raise BrokerSafetyStoreError("TEST recovery blocking state is inconsistent")


class _Connection(sqlite3.Connection):
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


class SQLiteBrokerTestMutationStore:
    """Non-promotable lifecycle store with no lease or provider-ID authority."""

    def __init__(
        self,
        path: str | Path,
        controller_store: SQLiteBrokerSafetyStore,
        *,
        busy_timeout_ms: int = 5000,
        migration_applied_at: str = "1970-01-01T00:00:00Z",
    ) -> None:
        if type(controller_store) is not SQLiteBrokerSafetyStore:
            raise BrokerSafetyStoreError("TEST lifecycle requires the exact Phase C store")
        self.controller_store = controller_store
        self.path = Path(path).resolve()
        if self.path == controller_store.path:
            raise BrokerSafetyStoreError("TEST lifecycle namespace must be a distinct database")
        if type(busy_timeout_ms) is not int or busy_timeout_ms <= 0:
            raise BrokerSafetyStoreError("busy timeout must be exact and positive")
        self.busy_timeout_ms = busy_timeout_ms
        _timestamp("migration_applied_at", migration_applied_at)
        self._initialize(migration_applied_at)

    def _connect(self, *, readonly: bool = False) -> sqlite3.Connection:
        target = f"file:{self.path.as_posix()}?mode=ro" if readonly else str(self.path)
        connection = sqlite3.connect(
            target,
            uri=readonly,
            timeout=self.busy_timeout_ms / 1000,
            isolation_level=None,
            factory=_Connection,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms}")
        if not readonly:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
        return connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def _initialize(self, applied_at: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "metadata" in tables:
                metadata = dict(connection.execute("SELECT key, value FROM metadata"))
                if metadata.get("schema_version") != str(TEST_STORE_SCHEMA_VERSION) or metadata.get("migration_id") != TEST_STORE_MIGRATION_ID or metadata.get("migration_checksum") != TEST_STORE_MIGRATION_CHECKSUM:
                    raise StoreCorruptionError("TEST store schema identity is invalid")
                expected = {statement.split("(", 1)[0].removeprefix("CREATE TABLE ") for statement in _SCHEMA}
                if tables - {"sqlite_sequence"} != expected:
                    raise StoreCorruptionError("TEST store contains an unexpected schema")
                return
            connection.execute("BEGIN IMMEDIATE")
            for statement in _SCHEMA:
                connection.execute(statement)
            connection.executemany(
                "INSERT INTO metadata VALUES(?, ?)",
                (
                    ("schema_version", str(TEST_STORE_SCHEMA_VERSION)),
                    ("migration_id", TEST_STORE_MIGRATION_ID),
                    ("migration_checksum", TEST_STORE_MIGRATION_CHECKSUM),
                    ("migration_applied_at", applied_at),
                    ("store_id", str(uuid4())),
                ),
            )
            connection.execute(f"PRAGMA user_version = {TEST_STORE_SCHEMA_VERSION}")
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def _ensure_scope(self, connection: sqlite3.Connection, scope: BrokerAccountScope) -> str:
        if scope.environment is not BrokerEnvironment.SANDBOX:
            raise BrokerSafetyStoreError("TEST mutation store structurally rejects LIVE")
        key = _scope_key(scope)
        connection.execute(
            "INSERT OR IGNORE INTO test_scopes VALUES(?, ?, ?, ?, ?)",
            (key, scope.broker_id, scope.environment.value, scope.account_reference, self.controller_store.store_id),
        )
        row = connection.execute(
            "SELECT broker_id, environment, account_reference, phase_c_store_id FROM test_scopes WHERE scope_key=?",
            (key,),
        ).fetchone()
        if row is None or tuple(row) != (scope.broker_id, scope.environment.value, scope.account_reference, self.controller_store.store_id):
            raise StoreCorruptionError("TEST scope identity conflict")
        return key

    def _check_fence(
        self,
        scope: BrokerAccountScope,
        owner_id: str,
        fencing_token: int,
        now: str,
    ) -> None:
        key = _phase_c_scope_key(scope)
        plan = self.controller_store.recovery_plan(scope)
        if "STORE_OR_AUDIT_CORRUPTION" in plan.blocking_reasons:
            raise StoreCorruptionError("Phase C authority is not recoverable")
        with self.controller_store._connect(readonly=True) as connection:
            self.controller_store._check_fence(
                connection, key, owner_id, fencing_token, now
            )

    @staticmethod
    def _append_audit(
        connection: sqlite3.Connection,
        key: str,
        *,
        event_type: str,
        occurred_at: str,
        actor_reference: str,
        references: dict[str, str],
        payload_sha256: str,
    ) -> tuple[int, str]:
        event_type = _safe("event_type", event_type)
        actor_reference = _safe("actor_reference", actor_reference)
        _timestamp("occurred_at", occurred_at)
        if _SHA.fullmatch(payload_sha256) is None:
            raise BrokerSafetyStoreError("audit payload must be a SHA-256")
        safe_references = { _safe("reference_name", name): _safe(name, value) for name, value in sorted(references.items()) }
        previous = connection.execute(
            "SELECT sequence, record_digest, occurred_at FROM audit WHERE scope_key=? ORDER BY sequence DESC LIMIT 1",
            (key,),
        ).fetchone()
        if previous is not None and previous[2] > occurred_at:
            raise BrokerSafetyStoreError("TEST audit time must be monotonic")
        sequence = 1 if previous is None else previous[0] + 1
        prior = ZERO_AUDIT_DIGEST if previous is None else previous[1]
        facts = {
            "actor_reference": actor_reference,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "payload_sha256": payload_sha256,
            "previous_digest": prior,
            "references": safe_references,
            "schema_version": "broker_test_audit_v1",
            "scope_key": key,
            "sequence": sequence,
        }
        root = _digest(_canonical(facts))
        connection.execute(
            "INSERT INTO audit VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (key, sequence, event_type, occurred_at, actor_reference, json.dumps(safe_references, sort_keys=True, separators=(",", ":")), payload_sha256, prior, root),
        )
        return sequence, root

    @staticmethod
    def _validate_scope_artifact(scope: BrokerAccountScope, value: object) -> None:
        if type(value) not in (
            BrokerTestMutationPolicy,
            BrokerTestMutationEnvelope,
            BrokerTestOperatorOptIn,
            BrokerTestExecutionAuthorization,
        ):
            raise BrokerSafetyStoreError("TEST store requires an exact TEST artifact")
        if (
            value.broker_id,
            value.environment,
            getattr(value, "account_reference", scope.account_reference),
        ) != (scope.broker_id, BrokerEnvironment.SANDBOX, scope.account_reference):
            raise PersistenceConflictError("TEST artifact account scope mismatch")

    def _verify_phase_c_provider_mapping(
        self,
        scope: BrokerAccountScope,
        envelope: BrokerTestMutationEnvelope,
        *,
        provider_name: str,
        provider_tag: str,
        owner_id: str,
        fencing_token: int,
        now: str,
    ) -> tuple[int, str]:
        self._check_fence(scope, owner_id, fencing_token, now)
        key = _phase_c_scope_key(scope)
        with self.controller_store._connect(readonly=True) as connection:
            row = connection.execute(
                "SELECT canonical_client_id FROM provider_ids WHERE scope_key=? AND provider_name=? AND provider_client_id=?",
                (key, provider_name, provider_tag),
            ).fetchone()
        if row is None or row[0] != envelope.canonical_client_order_id:
            raise PersistenceConflictError(
                "exact Phase C durable provider-ID mapping is required"
            )
        return self.controller_store.verify_audit_chain(scope)

    def _assert_lifecycle_integrity(self, scope: BrokerAccountScope) -> None:
        plan = self.recovery_plan(scope)
        if any("CORRUPTION" in reason for reason in plan.blocking_reasons):
            raise StoreCorruptionError(
                "TEST lifecycle recovery failed; no new TEST write is allowed"
            )

    def map_test_provider_tag(
        self,
        scope: BrokerAccountScope,
        policy: BrokerTestMutationPolicy,
        envelope: BrokerTestMutationEnvelope,
        *,
        provider_name: str,
        provider_tag: str,
        owner_id: str,
        fencing_token: int,
        now: str,
        actor_reference: str,
    ) -> DurableTestProviderTagBinding:
        self._assert_lifecycle_integrity(scope)
        self._validate_scope_artifact(scope, policy)
        self._validate_scope_artifact(scope, envelope)
        provider_name = _safe("provider_name", provider_name)
        provider_tag = _safe("provider_tag", provider_tag)
        if envelope.policy_sha256 != test_mutation_artifact_sha256(policy) or envelope.endpoint != policy.endpoint:
            raise PersistenceConflictError("TEST envelope is not bound to the exact policy")
        policy_text, policy_digest = _artifact(policy)
        envelope_text, envelope_digest = _artifact(envelope)
        phase_c_sequence, phase_c_root = self._verify_phase_c_provider_mapping(
            scope,
            envelope,
            provider_name=provider_name,
            provider_tag=provider_tag,
            owner_id=owner_id,
            fencing_token=fencing_token,
            now=now,
        )
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(scope, owner_id, fencing_token, now)
            existing = connection.execute(
                "SELECT canonical_client_id, envelope_id, fencing_token, mapped_at, phase_c_audit_sequence, phase_c_audit_root, mapping_audit_sequence FROM phase_c_provider_binding_refs WHERE scope_key=? AND provider_name=? AND provider_tag=?",
                (key, provider_name, provider_tag),
            ).fetchone()
            if existing is not None:
                if tuple(existing[:2]) != (envelope.canonical_client_order_id, envelope.envelope_id):
                    raise PersistenceConflictError("TEST provider tag collision")
                if tuple(existing[2:6]) == (
                    fencing_token,
                    existing[3],
                    phase_c_sequence,
                    phase_c_root,
                ):
                    return DurableTestProviderTagBinding(
                        TEST_PROVIDER_BINDING_SCHEMA_VERSION,
                        scope.broker_id,
                        scope.environment,
                        envelope.endpoint,
                        scope.account_reference,
                        envelope.envelope_id,
                        provider_name,
                        provider_tag,
                        envelope.canonical_client_order_id,
                        existing[2],
                        existing[3],
                        existing[6],
                        _TEST_BINDING_AUTHORITY,
                    )
                payload = _digest(
                    _canonical(
                        {
                            "canonical_client_id": envelope.canonical_client_order_id,
                            "envelope_id": envelope.envelope_id,
                            "fencing_token": fencing_token,
                            "provider_name": provider_name,
                            "provider_tag": provider_tag,
                        }
                    )
                )
                sequence, _ = self._append_audit(
                    connection,
                    key,
                    event_type="TEST_PROVIDER_TAG_REBOUND",
                    occurred_at=now,
                    actor_reference=actor_reference,
                    references={
                        "envelope_id": envelope.envelope_id,
                        "provider_name": provider_name,
                    },
                    payload_sha256=payload,
                )
                connection.execute(
                    "UPDATE phase_c_provider_binding_refs SET fencing_token=?, mapped_at=?, phase_c_audit_sequence=?, phase_c_audit_root=?, mapping_audit_sequence=? WHERE scope_key=? AND provider_name=? AND provider_tag=?",
                    (fencing_token, now, phase_c_sequence, phase_c_root, sequence, key, provider_name, provider_tag),
                )
                return DurableTestProviderTagBinding(
                    TEST_PROVIDER_BINDING_SCHEMA_VERSION,
                    scope.broker_id,
                    scope.environment,
                    envelope.endpoint,
                    scope.account_reference,
                    envelope.envelope_id,
                    provider_name,
                    provider_tag,
                    envelope.canonical_client_order_id,
                    fencing_token,
                    now,
                    sequence,
                    _TEST_BINDING_AUTHORITY,
                )
            connection.execute(
                "INSERT OR IGNORE INTO policies VALUES(?, ?, ?, ?)",
                (key, envelope.policy_sha256, policy_text, policy_digest),
            )
            try:
                connection.execute(
                    "INSERT INTO envelopes VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    (key, envelope.envelope_id, envelope.economic_intent_id, envelope.idempotency_key, envelope.canonical_client_order_id, envelope.sequence, envelope_text, envelope_digest),
                )
            except sqlite3.IntegrityError as exc:
                row = connection.execute(
                    "SELECT artifact_json, artifact_sha256 FROM envelopes WHERE scope_key=? AND envelope_id=?",
                    (key, envelope.envelope_id),
                ).fetchone()
                if row is None or tuple(row) != (envelope_text, envelope_digest):
                    raise PersistenceConflictError("TEST envelope identity or idempotency conflict") from exc
            payload = _digest(_canonical({"canonical_client_id": envelope.canonical_client_order_id, "envelope_id": envelope.envelope_id, "provider_name": provider_name, "provider_tag": provider_tag}))
            sequence, _ = self._append_audit(
                connection,
                key,
                event_type="TEST_PROVIDER_TAG_MAPPED",
                occurred_at=now,
                actor_reference=actor_reference,
                references={"envelope_id": envelope.envelope_id, "provider_name": provider_name},
                payload_sha256=payload,
            )
            try:
                connection.execute(
                    "INSERT INTO phase_c_provider_binding_refs VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (key, provider_name, provider_tag, envelope.canonical_client_order_id, envelope.envelope_id, fencing_token, now, phase_c_sequence, phase_c_root, sequence),
                )
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflictError("TEST provider tag or canonical identity collision") from exc
        return DurableTestProviderTagBinding(
            TEST_PROVIDER_BINDING_SCHEMA_VERSION,
            scope.broker_id,
            scope.environment,
            envelope.endpoint,
            scope.account_reference,
            envelope.envelope_id,
            provider_name,
            provider_tag,
            envelope.canonical_client_order_id,
            fencing_token,
            now,
            sequence,
            _TEST_BINDING_AUTHORITY,
        )

    def issue_test_operator_opt_in(
        self,
        scope: BrokerAccountScope,
        policy: BrokerTestMutationPolicy,
        envelope: BrokerTestMutationEnvelope,
        *,
        operator_opt_in_id: str,
        issued_at: str,
        expires_at: str,
        operator_reference: str,
        owner_id: str,
        fencing_token: int,
        actor_reference: str,
    ) -> BrokerTestOperatorOptIn:
        self._assert_lifecycle_integrity(scope)
        self._validate_scope_artifact(scope, policy)
        self._validate_scope_artifact(scope, envelope)
        self._check_fence(scope, owner_id, fencing_token, issued_at)
        if (
            envelope.policy_sha256 != test_mutation_artifact_sha256(policy)
            or issued_at < envelope.created_at
            or expires_at > envelope.expires_at
        ):
            raise PersistenceConflictError("operator opt-in is outside the exact envelope")
        opt_in = BrokerTestOperatorOptIn(
            TEST_MUTATION_SCHEMA_VERSION,
            "broker_test_operator_opt_in",
            operator_opt_in_id,
            envelope.broker_id,
            envelope.environment,
            envelope.endpoint,
            envelope.account_reference,
            envelope.envelope_id,
            test_mutation_artifact_sha256(envelope),
            envelope.policy_sha256,
            envelope.trading_date,
            issued_at,
            expires_at,
            operator_reference,
            True,
            _TEST_OPT_IN_AUTHORITY,
        )
        policy_text, policy_digest = _artifact(policy)
        envelope_text, envelope_digest = _artifact(envelope)
        opt_in_text, opt_in_digest = _artifact(opt_in)
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(scope, owner_id, fencing_token, issued_at)
            connection.execute(
                "INSERT OR IGNORE INTO policies VALUES(?, ?, ?, ?)",
                (key, envelope.policy_sha256, policy_text, policy_digest),
            )
            connection.execute(
                "INSERT OR IGNORE INTO envelopes VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (key, envelope.envelope_id, envelope.economic_intent_id, envelope.idempotency_key, envelope.canonical_client_order_id, envelope.sequence, envelope_text, envelope_digest),
            )
            existing = connection.execute(
                "SELECT artifact_json, artifact_sha256 FROM operator_opt_ins WHERE scope_key=? AND operator_opt_in_id=?",
                (key, operator_opt_in_id),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != (opt_in_text, opt_in_digest):
                    raise PersistenceConflictError("operator opt-in identity conflict")
                return opt_in
            sequence, _ = self._append_audit(
                connection,
                key,
                event_type="TEST_OPERATOR_OPT_IN_ISSUED",
                occurred_at=issued_at,
                actor_reference=actor_reference,
                references={"envelope_id": envelope.envelope_id, "operator_opt_in_id": operator_opt_in_id},
                payload_sha256=opt_in_digest,
            )
            try:
                connection.execute(
                    "INSERT INTO operator_opt_ins VALUES(?, ?, ?, ?, ?, ?, ?)",
                    (key, operator_opt_in_id, envelope.envelope_id, opt_in_text, opt_in_digest, fencing_token, sequence),
                )
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflictError("operator opt-in is not one-envelope exact") from exc
        return opt_in

    def commit_test_pre_submit(
        self,
        scope: BrokerAccountScope,
        policy: BrokerTestMutationPolicy,
        operator_opt_in: BrokerTestOperatorOptIn,
        authorization: BrokerTestExecutionAuthorization,
        envelope: BrokerTestMutationEnvelope,
        *,
        provider_name: str,
        provider_tag: str,
        attempt_id: str,
        occurred_at: str,
        owner_id: str,
        fencing_token: int,
        actor_reference: str,
        fail_before_commit: bool = False,
    ) -> BrokerTestPreSubmitCommit:
        self._assert_lifecycle_integrity(scope)
        self._validate_scope_artifact(scope, policy)
        self._validate_scope_artifact(scope, operator_opt_in)
        self._validate_scope_artifact(scope, authorization)
        self._validate_scope_artifact(scope, envelope)
        provider_name = _safe("provider_name", provider_name)
        provider_tag = _safe("provider_tag", provider_tag)
        try:
            parsed_attempt = UUID(attempt_id)
            if parsed_attempt.version != 4 or str(parsed_attempt) != attempt_id:
                raise ValueError
        except (TypeError, ValueError, AttributeError) as exc:
            raise BrokerSafetyStoreError("attempt_id must be an exact UUIDv4") from exc
        now = _timestamp("occurred_at", occurred_at)
        if (
            now < _timestamp("authorization.issued_at", authorization.issued_at)
            or now >= _timestamp("authorization.expires_at", authorization.expires_at)
            or now < _timestamp("operator_opt_in.issued_at", operator_opt_in.issued_at)
            or now >= _timestamp("operator_opt_in.expires_at", operator_opt_in.expires_at)
        ):
            raise PersistenceConflictError("TEST authorization is not currently valid")
        if (
            authorization.envelope_id,
            authorization.envelope_sha256,
            authorization.policy_sha256,
            authorization.endpoint,
            authorization.operator_opt_in_id,
            authorization.operator_opt_in_sha256,
        ) != (
            envelope.envelope_id,
            test_mutation_artifact_sha256(envelope),
            test_mutation_artifact_sha256(policy),
            envelope.endpoint,
            operator_opt_in.operator_opt_in_id,
            test_mutation_artifact_sha256(operator_opt_in),
        ) or envelope.order_notional > policy.maximum_order_notional:
            raise PersistenceConflictError("TEST authorization, policy, and envelope binding mismatch")
        if (
            operator_opt_in.envelope_id,
            operator_opt_in.envelope_sha256,
            operator_opt_in.policy_sha256,
            operator_opt_in.trading_date,
        ) != (
            envelope.envelope_id,
            test_mutation_artifact_sha256(envelope),
            envelope.policy_sha256,
            envelope.trading_date,
        ):
            raise PersistenceConflictError("TEST operator opt-in binding mismatch")
        auth_text, auth_digest = _artifact(authorization)
        submission = BrokerTestSubmissionRecord(
            TEST_MUTATION_SCHEMA_VERSION,
            "broker_test_submission",
            envelope.envelope_id,
            attempt_id,
            envelope.canonical_client_order_id,
            provider_tag,
            TestSubmissionState.SUBMITTING,
            1,
            occurred_at,
            None,
            "PRE_SIDE_EFFECT_COMMITTED_NO_PROVIDER_CALL",
        )
        submission_text, submission_digest = _artifact(submission)
        request_digest = _digest(_canonical({"authorization_sha256": auth_digest, "envelope_sha256": test_mutation_artifact_sha256(envelope), "persistence_version": TEST_PRE_SUBMIT_PERSISTENCE_VERSION, "provider_name": provider_name, "provider_tag": provider_tag, "submission_sha256": submission_digest}))
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(scope, owner_id, fencing_token, occurred_at)
            existing_commit = connection.execute(
                "SELECT envelope_id, attempt_id, persistence_version, request_sha256, submission_sha256, audit_sequence, audit_root_digest, fencing_token FROM pre_submit_commits WHERE scope_key=? AND authorization_id=?",
                (key, authorization.authorization_id),
            ).fetchone()
            if existing_commit is not None:
                if tuple(existing_commit[:5]) != (envelope.envelope_id, attempt_id, TEST_PRE_SUBMIT_PERSISTENCE_VERSION, request_digest, submission_digest):
                    raise PersistenceConflictError("one-shot TEST authorization was already consumed")
                return BrokerTestPreSubmitCommit(
                    TEST_MUTATION_SCHEMA_VERSION,
                    TEST_PRE_SUBMIT_PERSISTENCE_VERSION,
                    envelope.envelope_id,
                    authorization.authorization_id,
                    attempt_id,
                    request_digest,
                    submission_digest,
                    existing_commit[5],
                    existing_commit[6],
                    existing_commit[7],
                    submission,
                )
            binding = connection.execute(
                "SELECT canonical_client_id, envelope_id, fencing_token FROM phase_c_provider_binding_refs WHERE scope_key=? AND provider_name=? AND provider_tag=?",
                (key, provider_name, provider_tag),
            ).fetchone()
            if binding is None or tuple(binding) != (envelope.canonical_client_order_id, envelope.envelope_id, fencing_token):
                raise PersistenceConflictError("current fenced TEST provider-tag mapping is required before pre-submit")
            self._verify_phase_c_provider_mapping(
                scope,
                envelope,
                provider_name=provider_name,
                provider_tag=provider_tag,
                owner_id=owner_id,
                fencing_token=fencing_token,
                now=occurred_at,
            )
            opt_in_row = connection.execute(
                "SELECT envelope_id, artifact_json, artifact_sha256 FROM operator_opt_ins WHERE scope_key=? AND operator_opt_in_id=?",
                (key, operator_opt_in.operator_opt_in_id),
            ).fetchone()
            opt_in_text, opt_in_digest = _artifact(operator_opt_in)
            if opt_in_row is None or tuple(opt_in_row) != (
                envelope.envelope_id,
                opt_in_text,
                opt_in_digest,
            ):
                raise PersistenceConflictError("durable exact operator opt-in is required")
            unresolved = connection.execute(
                "SELECT COUNT(*) FROM submissions_current WHERE scope_key=? AND state IN (?, ?, ?)",
                (key, TestSubmissionState.SUBMITTING.value, TestSubmissionState.RECONCILIATION_REQUIRED.value, TestSubmissionState.UNKNOWN_SUBMISSION_STATE.value),
            ).fetchone()[0]
            active = connection.execute(
                "SELECT COUNT(*) FROM submissions_current WHERE scope_key=? AND state IN (?, ?)",
                (key, TestSubmissionState.SUBMITTING.value, TestSubmissionState.PROVIDER_ACKNOWLEDGED.value),
            ).fetchone()[0]
            if unresolved >= policy.maximum_unresolved_submissions or active >= policy.maximum_active_test_orders:
                raise PersistenceConflictError("TEST one-active/one-unresolved boundary blocks submission")
            high = connection.execute(
                "SELECT maximum_sequence, submitted_notional FROM high_water WHERE scope_key=? AND trading_date=?",
                (key, envelope.trading_date),
            ).fetchone()
            prior_sequence = 0 if high is None else high[0]
            prior_notional = Decimal("0") if high is None else Decimal(high[1])
            if envelope.sequence <= prior_sequence or prior_notional + envelope.order_notional > policy.maximum_session_submitted_notional:
                raise PersistenceConflictError("TEST high-water or synthetic session command cap blocks submission")
            connection.execute(
                "INSERT OR REPLACE INTO high_water VALUES(?, ?, ?, ?)",
                (key, envelope.trading_date, envelope.sequence, str(prior_notional + envelope.order_notional)),
            )
            connection.execute(
                "INSERT INTO authorizations VALUES(?, ?, ?, ?, ?, ?)",
                (key, authorization.authorization_id, envelope.envelope_id, operator_opt_in.operator_opt_in_id, auth_text, auth_digest),
            )
            connection.execute(
                "INSERT INTO authorization_uses VALUES(?, ?, ?, ?, ?)",
                (key, authorization.authorization_id, operator_opt_in.operator_opt_in_id, attempt_id, occurred_at),
            )
            connection.execute(
                "INSERT INTO submissions_current VALUES(?, ?, ?, ?, ?, ?, ?)",
                (key, envelope.envelope_id, attempt_id, submission.state.value, 1, submission_text, submission_digest),
            )
            connection.execute(
                "INSERT INTO submission_history VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (key, envelope.envelope_id, attempt_id, 1, submission.state.value, "ATOMIC_TEST_PRE_SUBMIT", submission_text, submission_digest),
            )
            audit_sequence, audit_root = self._append_audit(
                connection,
                key,
                event_type="TEST_PRE_SUBMIT_COMMITTED",
                occurred_at=occurred_at,
                actor_reference=actor_reference,
                references={"authorization_id": authorization.authorization_id, "envelope_id": envelope.envelope_id},
                payload_sha256=request_digest,
            )
            connection.execute(
                "INSERT INTO pre_submit_commits VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (key, authorization.authorization_id, operator_opt_in.operator_opt_in_id, envelope.envelope_id, attempt_id, TEST_PRE_SUBMIT_PERSISTENCE_VERSION, request_digest, submission_digest, audit_sequence, audit_root, fencing_token),
            )
            if fail_before_commit:
                raise BrokerSafetyStoreError("injected TEST transaction failure")
        return BrokerTestPreSubmitCommit(
            TEST_MUTATION_SCHEMA_VERSION,
            TEST_PRE_SUBMIT_PERSISTENCE_VERSION,
            envelope.envelope_id,
            authorization.authorization_id,
            attempt_id,
            request_digest,
            submission_digest,
            audit_sequence,
            audit_root,
            fencing_token,
            submission,
        )

    def apply_validated_test_lost_ack(
        self,
        scope: BrokerAccountScope,
        envelope: BrokerTestMutationEnvelope,
        validated_match: object,
        *,
        attempt_id: str,
        owner_id: str,
        fencing_token: int,
        recorded_at: str,
        actor_reference: str,
    ) -> BrokerTestSubmissionRecord:
        """Persist fail-closed lost-ACK handling; only provider validation may MATCH."""

        self._assert_lifecycle_integrity(scope)

        from tw_stock_tool.broker_adapters.fubon_neo.test_mutation import (
            ValidatedProviderOrderMatch,
        )
        from tw_stock_tool.broker_adapters.fubon_neo.d0_readiness import (
            ProviderOrderMatchState,
        )

        self._validate_scope_artifact(scope, envelope)
        if type(validated_match) is not ValidatedProviderOrderMatch or (
            validated_match.envelope_id,
            validated_match.canonical_client_order_id,
        ) != (
            envelope.envelope_id,
            envelope.canonical_client_order_id,
        ):
            raise PersistenceConflictError("lost-ACK result is not bound to the exact TEST envelope")
        state = {
            ProviderOrderMatchState.MATCHED: TestSubmissionState.PROVIDER_ACKNOWLEDGED,
            ProviderOrderMatchState.NO_MATCH: TestSubmissionState.RECONCILIATION_REQUIRED,
            ProviderOrderMatchState.AMBIGUOUS: TestSubmissionState.UNKNOWN_SUBMISSION_STATE,
        }[validated_match.match_state]
        outcomes = {
            ProviderOrderMatchState.MATCHED: "VALIDATED_PROVIDER_MATCH_RECONCILE_EXISTING",
            ProviderOrderMatchState.NO_MATCH: "NO_MATCH_RECONCILIATION_REQUIRED_NO_RETRY",
            ProviderOrderMatchState.AMBIGUOUS: "AMBIGUOUS_UNKNOWN_SUBMISSION_NO_RETRY",
        }
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(scope, owner_id, fencing_token, recorded_at)
            row = connection.execute(
                "SELECT state, version, artifact_json, artifact_sha256 FROM submissions_current WHERE scope_key=? AND envelope_id=? AND attempt_id=?",
                (key, envelope.envelope_id, attempt_id),
            ).fetchone()
            if row is None:
                raise PersistenceConflictError("lost-ACK handling requires the durable existing attempt")
            try:
                current = load_test_mutation_artifact_json(row[2])
            except Exception as exc:
                raise StoreCorruptionError("durable TEST submission is invalid") from exc
            if type(current) is not BrokerTestSubmissionRecord or current.state is not TestSubmissionState.SUBMITTING or current.provider_tag != validated_match.provider_tag or row[0] != current.state.value or row[1] != current.version or _digest(row[2].encode()) != row[3]:
                raise PersistenceConflictError("lost-ACK handling requires exact SUBMITTING state")
            updated = BrokerTestSubmissionRecord(
                TEST_MUTATION_SCHEMA_VERSION,
                current.artifact_type,
                current.envelope_id,
                current.attempt_id,
                current.canonical_client_order_id,
                current.provider_tag,
                state,
                current.version + 1,
                recorded_at,
                validated_match.provider_order_id,
                outcomes[validated_match.match_state],
            )
            text, digest = _artifact(updated)
            connection.execute(
                "UPDATE submissions_current SET state=?, version=?, artifact_json=?, artifact_sha256=? WHERE scope_key=? AND envelope_id=? AND attempt_id=? AND version=?",
                (state.value, updated.version, text, digest, key, envelope.envelope_id, attempt_id, current.version),
            )
            connection.execute(
                "INSERT INTO submission_history VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (key, envelope.envelope_id, attempt_id, updated.version, state.value, f"VALIDATED_LOST_ACK:{validated_match.match_state.value}", text, digest),
            )
            self._append_audit(
                connection,
                key,
                event_type="TEST_LOST_ACK_RESOLVED",
                occurred_at=recorded_at,
                actor_reference=actor_reference,
                references={"attempt_id": attempt_id, "match_state": validated_match.match_state.value},
                payload_sha256=digest,
            )
        return updated

    def recovery_plan(self, scope: BrokerAccountScope) -> BrokerTestMutationRecoveryPlan:
        key = _scope_key(scope)
        reasons: list[str] = []
        controller_plan = self.controller_store.recovery_plan(scope)
        if "STORE_OR_AUDIT_CORRUPTION" in controller_plan.blocking_reasons:
            reasons.append("TEST_PHASE_C_AUTHORITY_CORRUPTION")
        with self._connect(readonly=True) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                reasons.append("TEST_STORE_CORRUPTION")
            scope_row = connection.execute(
                "SELECT broker_id, environment, account_reference, phase_c_store_id FROM test_scopes WHERE scope_key=?",
                (key,),
            ).fetchone()
            if scope_row is not None and tuple(scope_row) != (
                scope.broker_id,
                scope.environment.value,
                scope.account_reference,
                self.controller_store.store_id,
            ):
                reasons.append("TEST_LIFECYCLE_CORRUPTION")
            with self.controller_store._connect(readonly=True) as controller:
                lease = controller.execute(
                    "SELECT fencing_token FROM leases WHERE scope_key=?",
                    (_phase_c_scope_key(scope),),
                ).fetchone()
            envelope_rows = connection.execute("SELECT envelope_id, artifact_json, artifact_sha256 FROM envelopes WHERE scope_key=?", (key,)).fetchall()
            envelopes: dict[str, BrokerTestMutationEnvelope] = {}
            policy_rows = connection.execute(
                "SELECT policy_sha256, artifact_json, artifact_sha256 FROM policies WHERE scope_key=?",
                (key,),
            ).fetchall()
            policies: set[str] = set()
            for row in policy_rows:
                try:
                    value = load_test_mutation_artifact_json(row[1])
                    if (
                        type(value) is not BrokerTestMutationPolicy
                        or test_mutation_artifact_sha256(value) != row[0]
                        or _digest(row[1].encode()) != row[2]
                    ):
                        raise ValueError
                    policies.add(row[0])
                except Exception:
                    reasons.append("TEST_LIFECYCLE_CORRUPTION")
            for row in envelope_rows:
                try:
                    value = load_test_mutation_artifact_json(row[1])
                    if type(value) is not BrokerTestMutationEnvelope or value.envelope_id != row[0] or value.policy_sha256 not in policies or _digest(row[1].encode()) != row[2]:
                        raise ValueError
                    envelopes[value.envelope_id] = value
                except Exception:
                    reasons.append("TEST_LIFECYCLE_CORRUPTION")
            opt_in_rows = connection.execute(
                "SELECT operator_opt_in_id, envelope_id, artifact_json, artifact_sha256, issue_audit_sequence FROM operator_opt_ins WHERE scope_key=?",
                (key,),
            ).fetchall()
            opt_ins: dict[str, BrokerTestOperatorOptIn] = {}
            for row in opt_in_rows:
                try:
                    value = load_test_mutation_artifact_json(row[2])
                    if (
                        type(value) is not BrokerTestOperatorOptIn
                        or (value.operator_opt_in_id, value.envelope_id) != tuple(row[:2])
                        or value.envelope_id not in envelopes
                        or _digest(row[2].encode()) != row[3]
                    ):
                        raise ValueError
                    issue_audit = connection.execute(
                        "SELECT event_type, references_json, payload_sha256 FROM audit WHERE scope_key=? AND sequence=?",
                        (key, row[4]),
                    ).fetchone()
                    if (
                        issue_audit is None
                        or issue_audit[0] != "TEST_OPERATOR_OPT_IN_ISSUED"
                        or json.loads(issue_audit[1])
                        != {
                            "envelope_id": value.envelope_id,
                            "operator_opt_in_id": value.operator_opt_in_id,
                        }
                        or issue_audit[2] != row[3]
                    ):
                        raise ValueError
                    opt_ins[value.operator_opt_in_id] = value
                except Exception:
                    reasons.append("TEST_LIFECYCLE_CORRUPTION")
            authorization_rows = connection.execute(
                "SELECT authorization_id, envelope_id, operator_opt_in_id, artifact_json, artifact_sha256 FROM authorizations WHERE scope_key=?",
                (key,),
            ).fetchall()
            authorizations: dict[str, BrokerTestExecutionAuthorization] = {}
            for row in authorization_rows:
                try:
                    value = load_test_mutation_artifact_json(row[3])
                    if (
                        type(value) is not BrokerTestExecutionAuthorization
                        or (value.authorization_id, value.envelope_id, value.operator_opt_in_id) != tuple(row[:3])
                        or value.envelope_id not in envelopes
                        or value.operator_opt_in_id not in opt_ins
                        or value.operator_opt_in_sha256 != test_mutation_artifact_sha256(opt_ins[value.operator_opt_in_id])
                        or _digest(row[3].encode()) != row[4]
                    ):
                        raise ValueError
                    authorizations[value.authorization_id] = value
                except Exception:
                    reasons.append("TEST_LIFECYCLE_CORRUPTION")
            use_rows = connection.execute(
                "SELECT authorization_id, operator_opt_in_id, attempt_id, used_at FROM authorization_uses WHERE scope_key=?",
                (key,),
            ).fetchall()
            uses_by_authorization = {row[0]: row for row in use_rows}
            for row in use_rows:
                authorization = authorizations.get(row[0])
                if authorization is None or authorization.operator_opt_in_id != row[1]:
                    reasons.append("TEST_LIFECYCLE_CORRUPTION")
            rows = connection.execute("SELECT envelope_id, attempt_id, state, version, artifact_json, artifact_sha256 FROM submissions_current WHERE scope_key=?", (key,)).fetchall()
            current_by_pair: dict[tuple[str, str], sqlite3.Row] = {}
            for row in rows:
                try:
                    value = load_test_mutation_artifact_json(row[4])
                    if type(value) is not BrokerTestSubmissionRecord or (value.envelope_id, value.attempt_id, value.state.value, value.version) != tuple(row[:4]) or _digest(row[4].encode()) != row[5]:
                        raise ValueError
                    current_by_pair[(row[0], row[1])] = row
                except Exception:
                    reasons.append("TEST_LIFECYCLE_CORRUPTION")
            unresolved = sum(row[2] in {TestSubmissionState.SUBMITTING.value, TestSubmissionState.RECONCILIATION_REQUIRED.value, TestSubmissionState.UNKNOWN_SUBMISSION_STATE.value} for row in rows)
            active = sum(row[2] in {TestSubmissionState.SUBMITTING.value, TestSubmissionState.PROVIDER_ACKNOWLEDGED.value} for row in rows)
            if unresolved:
                reasons.append("TEST_UNRESOLVED_SUBMISSION_STATE")
            if active:
                reasons.append("TEST_ACTIVE_ORDER_STATE")
            uses = len(use_rows)
            commits = connection.execute(
                "SELECT authorization_id, operator_opt_in_id, envelope_id, attempt_id, persistence_version, request_sha256, submission_sha256, audit_sequence, audit_root_digest, fencing_token FROM pre_submit_commits WHERE scope_key=?",
                (key,),
            ).fetchall()
            binding_rows = connection.execute(
                "SELECT provider_name, provider_tag, canonical_client_id, envelope_id, phase_c_audit_sequence, phase_c_audit_root, mapping_audit_sequence FROM phase_c_provider_binding_refs WHERE scope_key=?",
                (key,),
            ).fetchall()
            bindings = {row[3]: row for row in binding_rows}
            committed: list[BrokerTestMutationEnvelope | None] = []
            for commit in commits:
                authorization = authorizations.get(commit[0])
                use = uses_by_authorization.get(commit[0])
                envelope = envelopes.get(commit[2])
                pair = (commit[2], commit[3])
                binding = bindings.get(commit[2])
                audit_row = connection.execute(
                    "SELECT record_digest, event_type, references_json, payload_sha256 FROM audit WHERE scope_key=? AND sequence=?",
                    (key, commit[7]),
                ).fetchone()
                first_history = connection.execute(
                    "SELECT version, state, transition_kind, artifact_sha256 FROM submission_history WHERE scope_key=? AND envelope_id=? AND attempt_id=? AND version=1",
                    (key, commit[2], commit[3]),
                ).fetchone()
                if (
                    authorization is None
                    or use is None
                    or envelope is None
                    or binding is None
                    or tuple(use[:3]) != (commit[0], commit[1], commit[3])
                    or authorization.operator_opt_in_id != commit[1]
                    or commit[4] != TEST_PRE_SUBMIT_PERSISTENCE_VERSION
                    or pair not in current_by_pair
                    or first_history is None
                    or tuple(first_history) != (
                        1,
                        TestSubmissionState.SUBMITTING.value,
                        "ATOMIC_TEST_PRE_SUBMIT",
                        commit[6],
                    )
                    or audit_row is None
                    or (audit_row[0], audit_row[1], audit_row[3]) != (commit[8], "TEST_PRE_SUBMIT_COMMITTED", commit[5])
                    or json.loads(audit_row[2]) != {"authorization_id": commit[0], "envelope_id": commit[2]}
                ):
                    reasons.append("TEST_LIFECYCLE_CORRUPTION")
                committed.append(envelope)
            if set(uses_by_authorization) != {row[0] for row in commits} or set(authorizations) != {row[0] for row in commits}:
                reasons.append("TEST_LIFECYCLE_CORRUPTION")
            if set(current_by_pair) != {(row[2], row[3]) for row in commits}:
                reasons.append("TEST_LIFECYCLE_CORRUPTION")
            history_rows = connection.execute(
                "SELECT envelope_id, attempt_id, version, state, transition_kind, artifact_json, artifact_sha256 FROM submission_history WHERE scope_key=? ORDER BY envelope_id, attempt_id, version",
                (key,),
            ).fetchall()
            histories: dict[tuple[str, str], list[sqlite3.Row]] = {}
            for history in history_rows:
                histories.setdefault((history[0], history[1]), []).append(history)
            if set(histories) != set(current_by_pair):
                reasons.append("TEST_LIFECYCLE_CORRUPTION")
            allowed_version_two = {
                "VALIDATED_LOST_ACK:MATCHED": TestSubmissionState.PROVIDER_ACKNOWLEDGED.value,
                "VALIDATED_LOST_ACK:NO_MATCH": TestSubmissionState.RECONCILIATION_REQUIRED.value,
                "VALIDATED_LOST_ACK:AMBIGUOUS": TestSubmissionState.UNKNOWN_SUBMISSION_STATE.value,
            }
            for pair, history in histories.items():
                if pair not in current_by_pair:
                    reasons.append("TEST_LIFECYCLE_CORRUPTION")
                    continue
                current = current_by_pair[pair]
                try:
                    if [item[2] for item in history] != list(range(1, current[3] + 1)) or len(history) not in (1, 2):
                        raise ValueError
                    first = history[0]
                    if (first[2], first[3], first[4]) != (1, TestSubmissionState.SUBMITTING.value, "ATOMIC_TEST_PRE_SUBMIT"):
                        raise ValueError
                    if len(history) == 2 and allowed_version_two.get(history[1][4]) != history[1][3]:
                        raise ValueError
                    for item in history:
                        value = load_test_mutation_artifact_json(item[5])
                        if type(value) is not BrokerTestSubmissionRecord or (value.envelope_id, value.attempt_id, value.version, value.state.value) != tuple(item[:4]) or _digest(item[5].encode()) != item[6]:
                            raise ValueError
                    if (history[-1][2], history[-1][3], history[-1][5], history[-1][6]) != (current[3], current[2], current[4], current[5]):
                        raise ValueError
                    if len(history) == 2:
                        match_state = history[1][4].split(":", 1)[1]
                        audits = connection.execute(
                            "SELECT references_json, payload_sha256 FROM audit WHERE scope_key=? AND event_type='TEST_LOST_ACK_RESOLVED'",
                            (key,),
                        ).fetchall()
                        exact = [
                            item
                            for item in audits
                            if json.loads(item[0])
                            == {"attempt_id": pair[1], "match_state": match_state}
                            and item[1] == history[1][6]
                        ]
                        if len(exact) != 1:
                            raise ValueError
                except Exception:
                    reasons.append("TEST_LIFECYCLE_CORRUPTION")
            high_rows = connection.execute(
                "SELECT trading_date, maximum_sequence, submitted_notional FROM high_water WHERE scope_key=?",
                (key,),
            ).fetchall()
            expected_high: dict[str, tuple[int, Decimal]] = {}
            for envelope in committed:
                if envelope is None:
                    reasons.append("TEST_LIFECYCLE_CORRUPTION")
                    continue
                prior = expected_high.get(envelope.trading_date, (0, Decimal("0")))
                expected_high[envelope.trading_date] = (
                    max(prior[0], envelope.sequence),
                    prior[1] + envelope.order_notional,
                )
            observed_high = {
                row[0]: (row[1], Decimal(row[2])) for row in high_rows
            }
            if observed_high != expected_high:
                reasons.append("TEST_HIGH_WATER_CORRUPTION")
            audit_rows = connection.execute(
                "SELECT sequence, event_type, occurred_at, actor_reference, references_json, payload_sha256, previous_digest, record_digest FROM audit WHERE scope_key=? ORDER BY sequence",
                (key,),
            ).fetchall()
            prior = ZERO_AUDIT_DIGEST
            for expected_sequence, row in enumerate(audit_rows, start=1):
                try:
                    references = json.loads(row[4])
                    facts = {
                        "actor_reference": row[3],
                        "event_type": row[1],
                        "occurred_at": row[2],
                        "payload_sha256": row[5],
                        "previous_digest": row[6],
                        "references": references,
                        "schema_version": "broker_test_audit_v1",
                        "scope_key": key,
                        "sequence": row[0],
                    }
                    if row[0] != expected_sequence or row[6] != prior or row[7] != _digest(_canonical(facts)):
                        raise ValueError
                    prior = row[7]
                except Exception:
                    reasons.append("TEST_AUDIT_CORRUPTION")
                    break
            audit = None if not audit_rows else audit_rows[-1]
            for binding in binding_rows:
                envelope = envelopes.get(binding[3])
                try:
                    if envelope is None:
                        raise ValueError
                    with self.controller_store._connect(readonly=True) as controller:
                        mapping = controller.execute(
                            "SELECT canonical_client_id FROM provider_ids WHERE scope_key=? AND provider_name=? AND provider_client_id=?",
                            (_phase_c_scope_key(scope), binding[0], binding[1]),
                        ).fetchone()
                        phase_c_audit = controller.execute(
                            "SELECT record_digest FROM audit WHERE scope_key=? AND sequence=?",
                            (_phase_c_scope_key(scope), binding[4]),
                        ).fetchone()
                    mapping_audit = connection.execute(
                        "SELECT event_type, references_json FROM audit WHERE scope_key=? AND sequence=?",
                        (key, binding[6]),
                    ).fetchone()
                    if mapping is None or mapping[0] != binding[2] or binding[2] != envelope.canonical_client_order_id or phase_c_audit is None or phase_c_audit[0] != binding[5]:
                        raise ValueError
                    if (
                        mapping_audit is None
                        or mapping_audit[0] not in {"TEST_PROVIDER_TAG_MAPPED", "TEST_PROVIDER_TAG_REBOUND"}
                        or json.loads(mapping_audit[1])
                        != {"envelope_id": envelope.envelope_id, "provider_name": binding[0]}
                    ):
                        raise ValueError
                except Exception:
                    reasons.append("TEST_LIFECYCLE_CORRUPTION")
        return BrokerTestMutationRecoveryPlan(
            scope,
            None if lease is None else lease[0],
            len(envelope_rows),
            uses,
            active,
            unresolved,
            0 if audit is None else audit[0],
            ZERO_AUDIT_DIGEST if audit is None else audit[7],
            bool(reasons),
            tuple(sorted(set(reasons))),
        )


__all__ = [
    "BrokerTestMutationRecoveryPlan",
    "SQLiteBrokerTestMutationStore",
    "TEST_STORE_MIGRATION_CHECKSUM",
    "TEST_STORE_MIGRATION_ID",
    "TEST_STORE_SCHEMA_VERSION",
]

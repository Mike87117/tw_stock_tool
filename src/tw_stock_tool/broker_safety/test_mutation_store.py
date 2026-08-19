"""Isolated SQLite durability boundary for non-promotable TEST mutation artifacts."""

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
    BrokerAccountLease,
    BrokerAccountScope,
    BrokerSafetyStoreError,
    LeaseConflictError,
    PersistenceConflictError,
    StaleFenceError,
    StoreCorruptionError,
    ZERO_AUDIT_DIGEST,
)
from tw_stock_tool.broker_safety.models import BrokerEnvironment, _clean, _timestamp
from tw_stock_tool.broker_safety.test_mutation_models import (
    TEST_MUTATION_SCHEMA_VERSION,
    TEST_PRE_SUBMIT_PERSISTENCE_VERSION,
    TEST_PROVIDER_BINDING_SCHEMA_VERSION,
    BrokerTestExecutionAuthorization,
    BrokerTestMutationEnvelope,
    BrokerTestMutationPolicy,
    BrokerTestPreSubmitCommit,
    BrokerTestSubmissionRecord,
    DurableTestProviderTagBinding,
    TestSubmissionState,
    _TEST_BINDING_AUTHORITY,
    test_mutation_artifact_sha256,
)
from tw_stock_tool.broker_safety.test_mutation_serialization import (
    export_test_mutation_artifact_json,
    load_test_mutation_artifact_json,
)


TEST_STORE_SCHEMA_VERSION = 1
TEST_STORE_MIGRATION_ID = "001_phase_56_5d0_1_test_only"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SAFE = re.compile(r"[A-Za-z0-9_.:/-]+\Z")
_FORBIDDEN = re.compile(
    r"(?i)(password|api[_-]?key|secret|token|certificate|private[_-]?key|raw[_-]?(account|request|response))"
)

_SCHEMA = (
    "CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE account_scopes(scope_key TEXT PRIMARY KEY, broker_id TEXT NOT NULL, environment TEXT NOT NULL, account_reference TEXT NOT NULL, UNIQUE(broker_id, environment, account_reference))",
    "CREATE TABLE leases(scope_key TEXT PRIMARY KEY REFERENCES account_scopes(scope_key), owner_id TEXT NOT NULL, fencing_token INTEGER NOT NULL CHECK(fencing_token > 0), acquired_at TEXT NOT NULL, expires_at TEXT NOT NULL, last_renewed_at TEXT NOT NULL)",
    "CREATE TABLE policies(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), policy_sha256 TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, policy_sha256))",
    "CREATE TABLE envelopes(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), envelope_id TEXT NOT NULL, economic_intent_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, client_order_id TEXT NOT NULL, sequence INTEGER NOT NULL CHECK(sequence > 0), artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, envelope_id), UNIQUE(scope_key, economic_intent_id), UNIQUE(scope_key, idempotency_key), UNIQUE(scope_key, client_order_id))",
    "CREATE TABLE provider_ids(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), provider_name TEXT NOT NULL, provider_tag TEXT NOT NULL, canonical_client_id TEXT NOT NULL, envelope_id TEXT NOT NULL, fencing_token INTEGER NOT NULL CHECK(fencing_token > 0), mapped_at TEXT NOT NULL, mapping_audit_sequence INTEGER NOT NULL CHECK(mapping_audit_sequence > 0), PRIMARY KEY(scope_key, provider_name, provider_tag), UNIQUE(scope_key, provider_name, canonical_client_id))",
    "CREATE TABLE authorizations(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), authorization_id TEXT NOT NULL, envelope_id TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, authorization_id), UNIQUE(scope_key, envelope_id))",
    "CREATE TABLE authorization_uses(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), authorization_id TEXT NOT NULL, attempt_id TEXT NOT NULL, used_at TEXT NOT NULL, PRIMARY KEY(scope_key, authorization_id), UNIQUE(scope_key, attempt_id))",
    "CREATE TABLE pre_submit_commits(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), authorization_id TEXT NOT NULL, envelope_id TEXT NOT NULL, attempt_id TEXT NOT NULL, persistence_version TEXT NOT NULL, request_sha256 TEXT NOT NULL, submission_sha256 TEXT NOT NULL, audit_sequence INTEGER NOT NULL, audit_root_digest TEXT NOT NULL, fencing_token INTEGER NOT NULL, PRIMARY KEY(scope_key, authorization_id), UNIQUE(scope_key, envelope_id), UNIQUE(scope_key, attempt_id))",
    "CREATE TABLE submissions_current(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), envelope_id TEXT NOT NULL, attempt_id TEXT NOT NULL, state TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0), artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, envelope_id, attempt_id))",
    "CREATE TABLE submission_history(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), envelope_id TEXT NOT NULL, attempt_id TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL, transition_kind TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, envelope_id, attempt_id, version))",
    "CREATE TABLE high_water(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), trading_date TEXT NOT NULL, maximum_sequence INTEGER NOT NULL CHECK(maximum_sequence > 0), submitted_notional TEXT NOT NULL, PRIMARY KEY(scope_key, trading_date))",
    "CREATE TABLE audit(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), sequence INTEGER NOT NULL CHECK(sequence > 0), event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, actor_reference TEXT NOT NULL, references_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL, previous_digest TEXT NOT NULL, record_digest TEXT NOT NULL, PRIMARY KEY(scope_key, sequence), UNIQUE(scope_key, record_digest))",
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
    """TEST-only sidecar store; it has no live artifact or broker transport path."""

    def __init__(
        self,
        path: str | Path,
        *,
        busy_timeout_ms: int = 5000,
        migration_applied_at: str = "1970-01-01T00:00:00Z",
    ) -> None:
        self.path = Path(path).resolve()
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
            "INSERT OR IGNORE INTO account_scopes VALUES(?, ?, ?, ?)",
            (key, scope.broker_id, scope.environment.value, scope.account_reference),
        )
        row = connection.execute(
            "SELECT broker_id, environment, account_reference FROM account_scopes WHERE scope_key=?",
            (key,),
        ).fetchone()
        if row is None or tuple(row) != (scope.broker_id, scope.environment.value, scope.account_reference):
            raise StoreCorruptionError("TEST scope identity conflict")
        return key

    def acquire_lease(
        self,
        scope: BrokerAccountScope,
        *,
        owner_id: str,
        acquired_at: str,
        expires_at: str,
    ) -> BrokerAccountLease:
        owner_id = _safe("owner_id", owner_id)
        acquired = _timestamp("acquired_at", acquired_at)
        expires = _timestamp("expires_at", expires_at)
        if acquired >= expires:
            raise BrokerSafetyStoreError("lease expiry must follow acquisition")
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            row = connection.execute(
                "SELECT owner_id, fencing_token, acquired_at, expires_at, last_renewed_at FROM leases WHERE scope_key=?",
                (key,),
            ).fetchone()
            if row is None:
                token = 1
                original = acquired_at
                connection.execute(
                    "INSERT INTO leases VALUES(?, ?, ?, ?, ?, ?)",
                    (key, owner_id, token, acquired_at, expires_at, acquired_at),
                )
            elif row[0] == owner_id and row[3] > acquired_at:
                raise LeaseConflictError("TEST lease already belongs to this live owner")
            elif row[3] <= acquired_at:
                token = row[1] + 1
                original = acquired_at
                connection.execute(
                    "UPDATE leases SET owner_id=?, fencing_token=?, acquired_at=?, expires_at=?, last_renewed_at=? WHERE scope_key=?",
                    (owner_id, token, acquired_at, expires_at, acquired_at, key),
                )
            else:
                raise LeaseConflictError("TEST lease is held by another live owner")
        return BrokerAccountLease(scope, owner_id, token, original, expires_at, acquired_at)

    @staticmethod
    def _check_fence(
        connection: sqlite3.Connection,
        key: str,
        owner_id: str,
        fencing_token: int,
        now: str,
    ) -> None:
        _safe("owner_id", owner_id)
        _timestamp("now", now)
        row = connection.execute(
            "SELECT owner_id, fencing_token, expires_at FROM leases WHERE scope_key=?", (key,)
        ).fetchone()
        if row is None or tuple(row[:2]) != (owner_id, fencing_token) or row[2] <= now:
            raise StaleFenceError("TEST write requires the current unexpired fence")

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
        if type(value) not in (BrokerTestMutationPolicy, BrokerTestMutationEnvelope, BrokerTestExecutionAuthorization):
            raise BrokerSafetyStoreError("TEST store requires an exact TEST artifact")
        if (
            value.broker_id,
            value.environment,
            getattr(value, "account_reference", scope.account_reference),
        ) != (scope.broker_id, BrokerEnvironment.SANDBOX, scope.account_reference):
            raise PersistenceConflictError("TEST artifact account scope mismatch")

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
        self._validate_scope_artifact(scope, policy)
        self._validate_scope_artifact(scope, envelope)
        provider_name = _safe("provider_name", provider_name)
        provider_tag = _safe("provider_tag", provider_tag)
        if envelope.policy_sha256 != test_mutation_artifact_sha256(policy) or envelope.endpoint != policy.endpoint:
            raise PersistenceConflictError("TEST envelope is not bound to the exact policy")
        policy_text, policy_digest = _artifact(policy)
        envelope_text, envelope_digest = _artifact(envelope)
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(connection, key, owner_id, fencing_token, now)
            existing = connection.execute(
                "SELECT canonical_client_id, envelope_id, fencing_token, mapped_at, mapping_audit_sequence FROM provider_ids WHERE scope_key=? AND provider_name=? AND provider_tag=?",
                (key, provider_name, provider_tag),
            ).fetchone()
            if existing is not None:
                if tuple(existing[:2]) != (envelope.canonical_client_order_id, envelope.envelope_id):
                    raise PersistenceConflictError("TEST provider tag collision")
                if existing[2] == fencing_token:
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
                        existing[4],
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
                    "UPDATE provider_ids SET fencing_token=?, mapped_at=?, mapping_audit_sequence=? WHERE scope_key=? AND provider_name=? AND provider_tag=?",
                    (fencing_token, now, sequence, key, provider_name, provider_tag),
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
                    "INSERT INTO provider_ids VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    (key, provider_name, provider_tag, envelope.canonical_client_order_id, envelope.envelope_id, fencing_token, now, sequence),
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

    def commit_test_pre_submit(
        self,
        scope: BrokerAccountScope,
        policy: BrokerTestMutationPolicy,
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
        self._validate_scope_artifact(scope, policy)
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
        if now < _timestamp("authorization.issued_at", authorization.issued_at) or now >= _timestamp("authorization.expires_at", authorization.expires_at):
            raise PersistenceConflictError("TEST authorization is not currently valid")
        if (
            authorization.envelope_id,
            authorization.envelope_sha256,
            authorization.policy_sha256,
            authorization.endpoint,
        ) != (
            envelope.envelope_id,
            test_mutation_artifact_sha256(envelope),
            test_mutation_artifact_sha256(policy),
            envelope.endpoint,
        ) or envelope.order_notional > policy.maximum_order_notional:
            raise PersistenceConflictError("TEST authorization, policy, and envelope binding mismatch")
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
            self._check_fence(connection, key, owner_id, fencing_token, occurred_at)
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
                "SELECT canonical_client_id, envelope_id, fencing_token FROM provider_ids WHERE scope_key=? AND provider_name=? AND provider_tag=?",
                (key, provider_name, provider_tag),
            ).fetchone()
            if binding is None or tuple(binding) != (envelope.canonical_client_order_id, envelope.envelope_id, fencing_token):
                raise PersistenceConflictError("current fenced TEST provider-tag mapping is required before pre-submit")
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
                "INSERT INTO authorizations VALUES(?, ?, ?, ?, ?)",
                (key, authorization.authorization_id, envelope.envelope_id, auth_text, auth_digest),
            )
            connection.execute(
                "INSERT INTO authorization_uses VALUES(?, ?, ?, ?)",
                (key, authorization.authorization_id, attempt_id, occurred_at),
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
                "INSERT INTO pre_submit_commits VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (key, authorization.authorization_id, envelope.envelope_id, attempt_id, TEST_PRE_SUBMIT_PERSISTENCE_VERSION, request_digest, submission_digest, audit_sequence, audit_root, fencing_token),
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
            self._check_fence(connection, key, owner_id, fencing_token, recorded_at)
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
        with self._connect(readonly=True) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                reasons.append("TEST_STORE_CORRUPTION")
            lease = connection.execute("SELECT fencing_token FROM leases WHERE scope_key=?", (key,)).fetchone()
            envelope_rows = connection.execute("SELECT artifact_json, artifact_sha256 FROM envelopes WHERE scope_key=?", (key,)).fetchall()
            envelopes: dict[str, BrokerTestMutationEnvelope] = {}
            for row in envelope_rows:
                try:
                    value = load_test_mutation_artifact_json(row[0])
                    if type(value) is not BrokerTestMutationEnvelope or _digest(row[0].encode()) != row[1]:
                        raise ValueError
                    envelopes[value.envelope_id] = value
                except Exception:
                    reasons.append("TEST_STORE_CORRUPTION")
            rows = connection.execute("SELECT state, artifact_json, artifact_sha256 FROM submissions_current WHERE scope_key=?", (key,)).fetchall()
            for row in rows:
                try:
                    value = load_test_mutation_artifact_json(row[1])
                    if type(value) is not BrokerTestSubmissionRecord or value.state.value != row[0] or _digest(row[1].encode()) != row[2]:
                        raise ValueError
                except Exception:
                    reasons.append("TEST_STORE_CORRUPTION")
            unresolved = sum(row[0] in {TestSubmissionState.SUBMITTING.value, TestSubmissionState.RECONCILIATION_REQUIRED.value, TestSubmissionState.UNKNOWN_SUBMISSION_STATE.value} for row in rows)
            active = sum(row[0] in {TestSubmissionState.SUBMITTING.value, TestSubmissionState.PROVIDER_ACKNOWLEDGED.value} for row in rows)
            if unresolved:
                reasons.append("TEST_UNRESOLVED_SUBMISSION_STATE")
            if active:
                reasons.append("TEST_ACTIVE_ORDER_STATE")
            uses = connection.execute("SELECT COUNT(*) FROM authorization_uses WHERE scope_key=?", (key,)).fetchone()[0]
            commits = connection.execute(
                "SELECT envelope_id FROM pre_submit_commits WHERE scope_key=?",
                (key,),
            ).fetchall()
            committed = [envelopes.get(row[0]) for row in commits]
            high_rows = connection.execute(
                "SELECT trading_date, maximum_sequence, submitted_notional FROM high_water WHERE scope_key=?",
                (key,),
            ).fetchall()
            expected_high: dict[str, tuple[int, Decimal]] = {}
            for envelope in committed:
                if envelope is None:
                    reasons.append("TEST_STORE_CORRUPTION")
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

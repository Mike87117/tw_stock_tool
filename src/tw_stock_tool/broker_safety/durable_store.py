"""Single-host SQLite durability boundary for Phase 56.5C broker safety."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator, Mapping
from uuid import uuid4

from tw_stock_tool.broker_safety.durable_models import (
    AuditAnchorBundle,
    AuthorizationClaimResult,
    BackupManifest,
    BrokerAccountLease,
    BrokerAccountScope,
    BrokerAuditRecord,
    BrokerRecoveryPlan,
    BrokerSafetyStoreError,
    ClaimDisposition,
    ExternalAuditAnchorReceipt,
    LeaseConflictError,
    PersistenceConflictError,
    PreSubmitCommit,
    PreSubmitDisposition,
    RestoreRejectedError,
    ScopeAuditCheckpoint,
    STORE_SCHEMA_VERSION,
    StaleFenceError,
    StoreCorruptionError,
    TrustedRecoveryCheckpoint,
    ZERO_AUDIT_DIGEST,
)
from tw_stock_tool.broker_safety.execution import (
    apply_broker_execution,
    prepare_broker_submission,
    transition_broker_authorization_use,
    transition_broker_submission,
)
from tw_stock_tool.broker_safety.execution_models import (
    AuthorizationUseState,
    BrokerAuthorizationUseRecord,
    BrokerExecutionAuthorization,
    BrokerExecutionRecord,
    BrokerKillSwitchSnapshot,
    BrokerOrderIntent,
    BrokerSubmissionEvidence,
    BrokerSubmissionRecord,
    BrokerSubmissionState,
)
from tw_stock_tool.broker_safety.lineage import (
    validate_forward_eligibility_high_water_mark,
)
from tw_stock_tool.broker_safety.models import BrokerEnvironment, _clean, _timestamp
from tw_stock_tool.broker_safety.serialization import (
    export_broker_safety_artifact_json,
    load_broker_safety_artifact_json,
)
from tw_stock_tool.broker_safety.source_models import (
    ForwardEligibilityHighWaterMark,
    ForwardEligibilityLineageKey,
    ForwardEligibilityProgression,
)
from tw_stock_tool.broker_safety.source_serialization import (
    export_forward_eligibility_high_water_mark_json,
    export_forward_eligibility_progression_json,
    load_forward_eligibility_high_water_mark_json,
)


class _ClosingConnection(sqlite3.Connection):
    """Commit or roll back, then release the Windows file handle."""

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


MIGRATION_ID = "001_phase_56_5c_initial"
EXTERNAL_WORM_TARGET = "AMAZON_S3_OBJECT_LOCK_COMPLIANCE"
TEST_ANCHOR_TARGET = "DETERMINISTIC_FAKE_WORM"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SAFE = re.compile(r"[A-Za-z0-9_.:/-]+\Z")
_FORBIDDEN = re.compile(r"(?i)(password|api[_-]?key|secret|token|certificate|private[_-]?key|raw[_-]?(account|request|response))")
_TERMINAL_SUBMISSIONS = {
    BrokerSubmissionState.FILLED.value,
    BrokerSubmissionState.CANCELLED.value,
    BrokerSubmissionState.REJECTED.value,
    BrokerSubmissionState.EXPIRED.value,
}
_UNRESOLVED_SUBMISSIONS = {
    BrokerSubmissionState.SUBMITTING.value,
    BrokerSubmissionState.UNKNOWN_SUBMISSION_STATE.value,
    BrokerSubmissionState.RECONCILIATION_REQUIRED.value,
}


_SCHEMA = (
    "CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)",
    "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, migration_id TEXT UNIQUE NOT NULL, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)",
    "CREATE TABLE account_scopes(scope_key TEXT PRIMARY KEY, broker_id TEXT NOT NULL, environment TEXT NOT NULL, account_reference TEXT NOT NULL, UNIQUE(broker_id, environment, account_reference))",
    "CREATE TABLE leases(scope_key TEXT PRIMARY KEY REFERENCES account_scopes(scope_key), owner_id TEXT NOT NULL, fencing_token INTEGER NOT NULL CHECK(fencing_token > 0), acquired_at TEXT NOT NULL, expires_at TEXT NOT NULL, last_renewed_at TEXT NOT NULL)",
    "CREATE TABLE high_water(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), lineage_key TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, lineage_key))",
    "CREATE TABLE authorizations(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), authorization_id TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, authorization_id))",
    "CREATE TABLE intents(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), economic_intent_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, client_order_id TEXT NOT NULL, authorization_id TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, economic_intent_id), UNIQUE(scope_key, idempotency_key), UNIQUE(scope_key, client_order_id))",
    "CREATE TABLE provider_ids(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), provider_name TEXT NOT NULL, provider_client_id TEXT NOT NULL, canonical_client_id TEXT NOT NULL, PRIMARY KEY(scope_key, provider_name, provider_client_id), UNIQUE(scope_key, provider_name, canonical_client_id))",
    "CREATE TABLE authorization_uses(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), authorization_id TEXT NOT NULL, authorization_use_id TEXT NOT NULL, economic_intent_id TEXT NOT NULL, idempotency_key TEXT NOT NULL, state TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, authorization_id), UNIQUE(scope_key, authorization_use_id))",
    "CREATE TABLE pre_submit_commits(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), authorization_use_id TEXT NOT NULL, authorization_id TEXT NOT NULL, economic_intent_id TEXT NOT NULL, attempt_id TEXT NOT NULL, persistence_version TEXT NOT NULL, request_sha256 TEXT NOT NULL, submission_sha256 TEXT NOT NULL, audit_sequence INTEGER NOT NULL, audit_root_digest TEXT NOT NULL, fencing_token INTEGER NOT NULL, PRIMARY KEY(scope_key, authorization_use_id), UNIQUE(scope_key, economic_intent_id), UNIQUE(scope_key, economic_intent_id, attempt_id))",
    "CREATE TABLE submissions_current(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), intent_id TEXT NOT NULL, attempt_id TEXT NOT NULL, state TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0), artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, intent_id, attempt_id))",
    "CREATE TABLE submission_history(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), intent_id TEXT NOT NULL, attempt_id TEXT NOT NULL, version INTEGER NOT NULL, state TEXT NOT NULL, transition_kind TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, intent_id, attempt_id, version))",
    "CREATE TABLE executions(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), execution_id TEXT NOT NULL, intent_id TEXT NOT NULL, attempt_id TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, execution_id))",
    "CREATE TABLE kill_switch(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), kill_switch_version TEXT NOT NULL, artifact_json TEXT NOT NULL, artifact_sha256 TEXT NOT NULL, PRIMARY KEY(scope_key, kill_switch_version))",
    "CREATE TABLE audit(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), sequence INTEGER NOT NULL CHECK(sequence > 0), record_id TEXT NOT NULL, event_type TEXT NOT NULL, occurred_at TEXT NOT NULL, recorded_at TEXT NOT NULL, actor_reference TEXT NOT NULL, references_json TEXT NOT NULL, payload_sha256 TEXT NOT NULL, previous_digest TEXT NOT NULL, record_digest TEXT NOT NULL, external_anchor_reference TEXT, PRIMARY KEY(scope_key, sequence), UNIQUE(scope_key, record_id), UNIQUE(scope_key, record_digest))",
    "CREATE TABLE anchor_receipts(scope_key TEXT NOT NULL REFERENCES account_scopes(scope_key), receipt_id TEXT NOT NULL, bundle_json TEXT NOT NULL, bundle_sha256 TEXT NOT NULL, anchored_sequence INTEGER NOT NULL, anchored_root TEXT NOT NULL, previous_receipt_reference TEXT, target TEXT NOT NULL, object_reference TEXT NOT NULL, anchored_at TEXT NOT NULL, PRIMARY KEY(scope_key, receipt_id))",
    "CREATE TABLE backup_history(backup_sha256 TEXT PRIMARY KEY, manifest_json TEXT NOT NULL, created_at TEXT NOT NULL)",
)
MIGRATION_CHECKSUM = sha256("\n".join(_SCHEMA).encode()).hexdigest()


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BrokerSafetyStoreError("value is not canonical JSON") from exc


def _digest_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _require_sha(name: str, value: object) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise BrokerSafetyStoreError(f"{name} must be a lowercase SHA-256")
    return value


def _safe_text(name: str, value: object) -> str:
    text = _clean(name, value)
    if _FORBIDDEN.search(name) or _FORBIDDEN.search(text) or _SAFE.fullmatch(text) is None:
        raise BrokerSafetyStoreError(f"{name} is not safe for durable audit storage")
    return text


def _scope_key(scope: BrokerAccountScope) -> str:
    if type(scope) is not BrokerAccountScope:
        raise BrokerSafetyStoreError("scope must be an exact BrokerAccountScope")
    return _digest_bytes(
        _canonical(
            {
                "account_reference": scope.account_reference,
                "broker_id": scope.broker_id,
                "environment": scope.environment.value,
                "schema_version": "broker_account_scope_v1",
            }
        )
    )


def _lineage_key(value: ForwardEligibilityLineageKey) -> str:
    if type(value) is not ForwardEligibilityLineageKey:
        raise BrokerSafetyStoreError("lineage key must be exact")
    return _digest_bytes(_canonical(asdict(value)))


def canonical_audit_anchor_bundle_bytes(bundle: AuditAnchorBundle) -> bytes:
    if type(bundle) is not AuditAnchorBundle:
        raise BrokerSafetyStoreError("bundle must be an exact AuditAnchorBundle")
    return _canonical(asdict(bundle))


def audit_anchor_bundle_sha256(bundle: AuditAnchorBundle) -> str:
    return _digest_bytes(canonical_audit_anchor_bundle_bytes(bundle))


def _artifact(value: object) -> tuple[str, str]:
    text = export_broker_safety_artifact_json(value)
    return text, _digest_bytes(text.encode("utf-8"))


def _source_artifact(value: ForwardEligibilityHighWaterMark) -> tuple[str, str]:
    text = export_forward_eligibility_high_water_mark_json(value)
    return text, _digest_bytes(text.encode("utf-8"))


class SQLiteBrokerSafetyStore:
    """One SQLite database per operator-controlled host; no broker I/O."""

    def __init__(
        self,
        path: str | Path,
        *,
        busy_timeout_ms: int = 5000,
        migration_applied_at: str = "1970-01-01T00:00:00Z",
        fail_migration: bool = False,
    ) -> None:
        self.path = Path(path).resolve()
        if type(busy_timeout_ms) is not int or busy_timeout_ms <= 0:
            raise BrokerSafetyStoreError("busy timeout must be an exact positive integer")
        self.busy_timeout_ms = busy_timeout_ms
        _timestamp("migration_applied_at", migration_applied_at)
        self._initialize(migration_applied_at, fail_migration)

    def _connect(self, *, readonly: bool = False) -> sqlite3.Connection:
        target = f"file:{self.path.as_posix()}?mode=ro" if readonly else str(self.path)
        connection = sqlite3.connect(
            target,
            uri=readonly,
            timeout=self.busy_timeout_ms / 1000,
            isolation_level=None,
            factory=_ClosingConnection,
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

    def _initialize(self, applied_at: str, fail_migration: bool) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "metadata" in tables:
                user_version = connection.execute("PRAGMA user_version").fetchone()[0]
                if user_version != STORE_SCHEMA_VERSION:
                    raise BrokerSafetyStoreError("unknown SQLite user_version")
                version_row = connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
                if version_row is None or int(version_row[0]) != STORE_SCHEMA_VERSION:
                    raise BrokerSafetyStoreError("unknown or unsupported store schema version")
                migration = connection.execute(
                    "SELECT migration_id, checksum FROM schema_migrations WHERE version=?",
                    (STORE_SCHEMA_VERSION,),
                ).fetchone()
                if migration is None or tuple(migration) != (MIGRATION_ID, MIGRATION_CHECKSUM):
                    raise StoreCorruptionError("schema migration identity is invalid")
                return
            connection.execute("BEGIN IMMEDIATE")
            for statement in _SCHEMA:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {STORE_SCHEMA_VERSION}")
            if fail_migration:
                raise BrokerSafetyStoreError("injected migration failure")
            connection.executemany(
                "INSERT INTO metadata(key, value) VALUES(?, ?)",
                (
                    ("schema_version", str(STORE_SCHEMA_VERSION)),
                    ("store_id", str(uuid4())),
                ),
            )
            connection.execute(
                "INSERT INTO schema_migrations VALUES(?, ?, ?, ?)",
                (STORE_SCHEMA_VERSION, MIGRATION_ID, MIGRATION_CHECKSUM, applied_at),
            )
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    @property
    def store_id(self) -> str:
        with self._connect(readonly=True) as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key='store_id'").fetchone()
        if row is None:
            raise StoreCorruptionError("store identity is missing")
        return row[0]

    def sqlite_posture(self) -> dict[str, object]:
        with self._connect() as connection:
            return {
                "foreign_keys": connection.execute("PRAGMA foreign_keys").fetchone()[0],
                "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
                "synchronous": connection.execute("PRAGMA synchronous").fetchone()[0],
                "busy_timeout": connection.execute("PRAGMA busy_timeout").fetchone()[0],
            }

    def _ensure_scope(self, connection: sqlite3.Connection, scope: BrokerAccountScope) -> str:
        key = _scope_key(scope)
        connection.execute(
            "INSERT OR IGNORE INTO account_scopes VALUES(?, ?, ?, ?)",
            (key, scope.broker_id, scope.environment.value, scope.account_reference),
        )
        row = connection.execute(
            "SELECT broker_id, environment, account_reference FROM account_scopes WHERE scope_key=?",
            (key,),
        ).fetchone()
        if row is None or tuple(row) != (
            scope.broker_id,
            scope.environment.value,
            scope.account_reference,
        ):
            raise StoreCorruptionError("account scope identity conflict")
        return key

    def acquire_lease(
        self,
        scope: BrokerAccountScope,
        *,
        owner_id: str,
        acquired_at: str,
        expires_at: str,
    ) -> BrokerAccountLease:
        _safe_text("owner_id", owner_id)
        acquired = _timestamp("acquired_at", acquired_at)
        expires = _timestamp("expires_at", expires_at)
        if acquired >= expires:
            raise BrokerSafetyStoreError("lease expiry must follow acquisition")
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            row = connection.execute("SELECT * FROM leases WHERE scope_key=?", (key,)).fetchone()
            if row is None:
                token = 1
                original = acquired_at
                connection.execute(
                    "INSERT INTO leases VALUES(?, ?, ?, ?, ?, ?)",
                    (key, owner_id, token, acquired_at, expires_at, acquired_at),
                )
            elif row[4] <= acquired_at:
                token = row[2] + 1
                original = acquired_at
                connection.execute(
                    "UPDATE leases SET owner_id=?, fencing_token=?, acquired_at=?, expires_at=?, last_renewed_at=? WHERE scope_key=?",
                    (owner_id, token, acquired_at, expires_at, acquired_at, key),
                )
            elif row[1] == owner_id and row[5] <= acquired_at:
                token = row[2]
                original = row[3]
                connection.execute(
                    "UPDATE leases SET expires_at=?, last_renewed_at=? WHERE scope_key=?",
                    (expires_at, acquired_at, key),
                )
            else:
                raise LeaseConflictError("account lease is held by another live owner")
        return BrokerAccountLease(scope, owner_id, token, original, expires_at, acquired_at)

    def renew_lease(
        self,
        lease: BrokerAccountLease,
        *,
        renewed_at: str,
        expires_at: str,
    ) -> BrokerAccountLease:
        renewed = _timestamp("renewed_at", renewed_at)
        expires = _timestamp("expires_at", expires_at)
        if renewed >= expires:
            raise BrokerSafetyStoreError("lease expiry must follow renewal")
        with self._transaction() as connection:
            key = self._ensure_scope(connection, lease.scope)
            cursor = connection.execute(
                "UPDATE leases SET expires_at=?, last_renewed_at=? WHERE scope_key=? AND owner_id=? AND fencing_token=? AND expires_at>? AND last_renewed_at<=?",
                (expires_at, renewed_at, key, lease.owner_id, lease.fencing_token, renewed_at, renewed_at),
            )
            if cursor.rowcount != 1:
                raise StaleFenceError("lease renewal presented stale authority")
        return BrokerAccountLease(
            lease.scope,
            lease.owner_id,
            lease.fencing_token,
            lease.acquired_at,
            expires_at,
            renewed_at,
        )

    def _check_fence(
        self,
        connection: sqlite3.Connection,
        scope_key: str,
        owner_id: str,
        fencing_token: int,
        now: str,
    ) -> None:
        _safe_text("owner_id", owner_id)
        if type(fencing_token) is not int or fencing_token <= 0:
            raise StaleFenceError("fencing token must be an exact positive integer")
        _timestamp("now", now)
        row = connection.execute(
            "SELECT owner_id, fencing_token, expires_at FROM leases WHERE scope_key=?",
            (scope_key,),
        ).fetchone()
        if row is None or tuple(row[:2]) != (owner_id, fencing_token) or row[2] <= now:
            raise StaleFenceError("controller write requires the current unexpired fence")

    def _append_audit(
        self,
        connection: sqlite3.Connection,
        scope_key: str,
        *,
        event_type: str,
        occurred_at: str,
        recorded_at: str,
        actor_reference: str,
        references: Mapping[str, str] | None = None,
        payload_sha256: str,
    ) -> BrokerAuditRecord:
        event_type = _safe_text("event_type", event_type)
        actor_reference = _safe_text("actor_reference", actor_reference)
        occurred = _timestamp("occurred_at", occurred_at)
        recorded = _timestamp("recorded_at", recorded_at)
        if occurred > recorded:
            raise BrokerSafetyStoreError("audit occurrence cannot follow recording")
        _require_sha("payload_sha256", payload_sha256)
        safe_references: dict[str, str] = {}
        for name, value in sorted((references or {}).items()):
            safe_references[_safe_text("reference_name", name)] = _safe_text(name, value)
        references_json = _canonical(safe_references).decode()
        previous = connection.execute(
            "SELECT sequence, record_digest, recorded_at FROM audit WHERE scope_key=? ORDER BY sequence DESC LIMIT 1",
            (scope_key,),
        ).fetchone()
        if previous is not None and _timestamp("previous_recorded_at", previous[2]) > recorded:
            raise BrokerSafetyStoreError("audit recorded_at must be monotonic")
        sequence = 1 if previous is None else previous[0] + 1
        previous_digest = ZERO_AUDIT_DIGEST if previous is None else previous[1]
        record_id = str(uuid4())
        facts = {
            "actor_reference": actor_reference,
            "event_type": event_type,
            "occurred_at": occurred_at,
            "payload_sha256": payload_sha256,
            "previous_record_digest": previous_digest,
            "record_id": record_id,
            "recorded_at": recorded_at,
            "references": safe_references,
            "schema_version": "broker_audit_v1",
            "scope_key": scope_key,
            "sequence": sequence,
            "store_id": self.store_id,
        }
        record_digest = _digest_bytes(_canonical(facts))
        connection.execute(
            "INSERT INTO audit VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                scope_key,
                sequence,
                record_id,
                event_type,
                occurred_at,
                recorded_at,
                actor_reference,
                references_json,
                payload_sha256,
                previous_digest,
                record_digest,
            ),
        )
        return BrokerAuditRecord(
            self.store_id,
            scope_key,
            sequence,
            record_id,
            event_type,
            occurred_at,
            recorded_at,
            actor_reference,
            references_json,
            payload_sha256,
            previous_digest,
            record_digest,
            None,
        )

    def verify_audit_chain(self, scope: BrokerAccountScope) -> tuple[int, str]:
        key = _scope_key(scope)
        with self._connect(readonly=True) as connection:
            rows = connection.execute("SELECT * FROM audit WHERE scope_key=? ORDER BY sequence", (key,)).fetchall()
        previous = ZERO_AUDIT_DIGEST
        for expected, row in enumerate(rows, 1):
            if row[0] != key or row[1] != expected or row[9] != previous:
                raise StoreCorruptionError("broker audit sequence or linkage is broken")
            try:
                references = json.loads(row[7])
                BrokerAuditRecord(
                    self.store_id,
                    key,
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                    row[9],
                    row[10],
                    row[11],
                )
            except Exception as exc:
                raise StoreCorruptionError("broker audit record is malformed") from exc
            facts = {
                "actor_reference": row[6],
                "event_type": row[3],
                "occurred_at": row[4],
                "payload_sha256": row[8],
                "previous_record_digest": row[9],
                "record_id": row[2],
                "recorded_at": row[5],
                "references": references,
                "schema_version": "broker_audit_v1",
                "scope_key": key,
                "sequence": row[1],
                "store_id": self.store_id,
            }
            if _digest_bytes(_canonical(facts)) != row[10]:
                raise StoreCorruptionError("broker audit record digest is invalid")
            previous = row[10]
        return len(rows), previous

    def _put_immutable(
        self,
        connection: sqlite3.Connection,
        table: str,
        key_columns: tuple[str, ...],
        key_values: tuple[str, ...],
        text: str,
        digest: str,
        extra_columns: tuple[str, ...] = (),
        extra_values: tuple[str, ...] = (),
    ) -> bool:
        where = " AND ".join(f"{name}=?" for name in key_columns)
        row = connection.execute(
            f"SELECT artifact_json, artifact_sha256 FROM {table} WHERE {where}",
            key_values,
        ).fetchone()
        if row is not None:
            if tuple(row) != (text, digest):
                raise PersistenceConflictError("immutable persisted identity conflict")
            return False
        columns = (*key_columns, *extra_columns, "artifact_json", "artifact_sha256")
        connection.execute(
            f"INSERT INTO {table}({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",
            (*key_values, *extra_values, text, digest),
        )
        return True

    def _read_artifact(
        self,
        connection: sqlite3.Connection,
        table: str,
        where: str,
        values: tuple[str, ...],
        expected: type,
    ) -> Any:
        row = connection.execute(f"SELECT artifact_json, artifact_sha256 FROM {table} WHERE {where}", values).fetchone()
        if row is None:
            return None
        if _digest_bytes(row[0].encode()) != row[1]:
            raise StoreCorruptionError("persisted artifact digest mismatch")
        try:
            value = load_broker_safety_artifact_json(row[0])
        except Exception as exc:
            raise StoreCorruptionError("persisted broker artifact is invalid") from exc
        if type(value) is not expected:
            raise StoreCorruptionError("persisted broker artifact has the wrong type")
        return value

    def persist_authorization(
        self,
        scope: BrokerAccountScope,
        authorization: BrokerExecutionAuthorization,
        *,
        owner_id: str,
        fencing_token: int,
        now: str,
        actor_reference: str,
    ) -> BrokerExecutionAuthorization:
        if type(authorization) is not BrokerExecutionAuthorization:
            raise BrokerSafetyStoreError("authorization must be exact")
        if (scope.broker_id, scope.environment, scope.account_reference) != (
            authorization.broker_id,
            authorization.environment,
            authorization.account_reference,
        ):
            raise PersistenceConflictError("authorization account scope mismatch")
        text, digest = _artifact(authorization)
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(connection, key, owner_id, fencing_token, now)
            inserted = self._put_immutable(
                connection,
                "authorizations",
                ("scope_key", "authorization_id"),
                (key, authorization.authorization_id),
                text,
                digest,
            )
            if inserted:
                self._append_audit(
                    connection,
                    key,
                    event_type="AUTHORIZATION_PERSISTED",
                    occurred_at=now,
                    recorded_at=now,
                    actor_reference=actor_reference,
                    references={"authorization_id": authorization.authorization_id},
                    payload_sha256=digest,
                )
        return authorization

    def load_authorization(self, scope: BrokerAccountScope, authorization_id: str) -> BrokerExecutionAuthorization | None:
        with self._connect(readonly=True) as connection:
            return self._read_artifact(
                connection,
                "authorizations",
                "scope_key=? AND authorization_id=?",
                (_scope_key(scope), authorization_id),
                BrokerExecutionAuthorization,
            )

    def _put_intent(self, connection: sqlite3.Connection, key: str, intent: BrokerOrderIntent) -> bool:
        authorization = self._read_artifact(
            connection,
            "authorizations",
            "scope_key=? AND authorization_id=?",
            (key, intent.authorization_id),
            BrokerExecutionAuthorization,
        )
        if authorization is None:
            raise PersistenceConflictError("order intent requires its immutable authorization")
        text, digest = _artifact(intent)
        try:
            return self._put_immutable(
                connection,
                "intents",
                ("scope_key", "economic_intent_id"),
                (key, intent.economic_intent_id),
                text,
                digest,
                ("idempotency_key", "client_order_id", "authorization_id"),
                (intent.idempotency_key, intent.canonical_client_order_id, intent.authorization_id),
            )
        except sqlite3.IntegrityError as exc:
            raise PersistenceConflictError("intent idempotency or client identity conflict") from exc

    def persist_intent(
        self,
        scope: BrokerAccountScope,
        intent: BrokerOrderIntent,
        *,
        owner_id: str,
        fencing_token: int,
        now: str,
        actor_reference: str,
    ) -> BrokerOrderIntent:
        self._validate_intent_scope(scope, intent)
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(connection, key, owner_id, fencing_token, now)
            inserted = self._put_intent(connection, key, intent)
            if inserted:
                _, digest = _artifact(intent)
                self._append_audit(
                    connection,
                    key,
                    event_type="ORDER_INTENT_PERSISTED",
                    occurred_at=now,
                    recorded_at=now,
                    actor_reference=actor_reference,
                    references={"economic_intent_id": intent.economic_intent_id},
                    payload_sha256=digest,
                )
        return intent

    def _validate_intent_scope(self, scope: BrokerAccountScope, intent: BrokerOrderIntent) -> None:
        if type(intent) is not BrokerOrderIntent:
            raise BrokerSafetyStoreError("intent must be exact")
        if (scope.broker_id, scope.environment, scope.account_reference) != (
            intent.broker_id,
            intent.environment,
            intent.account_reference,
        ):
            raise PersistenceConflictError("intent account scope mismatch")

    def load_intent_by_idempotency_key(self, scope: BrokerAccountScope, idempotency_key: str) -> BrokerOrderIntent | None:
        with self._connect(readonly=True) as connection:
            return self._read_artifact(
                connection,
                "intents",
                "scope_key=? AND idempotency_key=?",
                (_scope_key(scope), idempotency_key),
                BrokerOrderIntent,
            )

    def map_provider_client_id(
        self,
        scope: BrokerAccountScope,
        *,
        provider_name: str,
        provider_client_id: str,
        canonical_client_id: str,
        owner_id: str,
        fencing_token: int,
        now: str,
        actor_reference: str,
    ) -> str:
        provider_name = _safe_text("provider_name", provider_name)
        provider_client_id = _safe_text("provider_client_id", provider_client_id)
        canonical_client_id = _safe_text("canonical_client_id", canonical_client_id)
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(connection, key, owner_id, fencing_token, now)
            intent = self._read_artifact(
                connection,
                "intents",
                "scope_key=? AND client_order_id=?",
                (key, canonical_client_id),
                BrokerOrderIntent,
            )
            if intent is None:
                raise PersistenceConflictError("provider mapping requires an existing canonical intent")
            existing = connection.execute(
                "SELECT canonical_client_id FROM provider_ids WHERE scope_key=? AND provider_name=? AND provider_client_id=?",
                (key, provider_name, provider_client_id),
            ).fetchone()
            if existing is not None:
                if existing[0] != canonical_client_id:
                    raise PersistenceConflictError("provider client ID collision")
                return existing[0]
            try:
                connection.execute(
                    "INSERT INTO provider_ids VALUES(?, ?, ?, ?)",
                    (key, provider_name, provider_client_id, canonical_client_id),
                )
            except sqlite3.IntegrityError as exc:
                raise PersistenceConflictError("canonical client ID already has another provider mapping") from exc
            payload = _digest_bytes(
                _canonical(
                    {
                        "canonical_client_id": canonical_client_id,
                        "provider_client_id": provider_client_id,
                        "provider_name": provider_name,
                    }
                )
            )
            self._append_audit(
                connection,
                key,
                event_type="PROVIDER_CLIENT_ID_MAPPED",
                occurred_at=now,
                recorded_at=now,
                actor_reference=actor_reference,
                references={
                    "economic_intent_id": intent.economic_intent_id,
                    "provider_name": provider_name,
                },
                payload_sha256=payload,
            )
        return canonical_client_id

    def claim_authorization_use(
        self,
        scope: BrokerAccountScope,
        record: BrokerAuthorizationUseRecord,
        *,
        owner_id: str,
        fencing_token: int,
        now: str,
        actor_reference: str,
        fail_before_commit: bool = False,
    ) -> AuthorizationClaimResult:
        if type(record) is not BrokerAuthorizationUseRecord or record.state is not AuthorizationUseState.RESERVED:
            raise BrokerSafetyStoreError("claim requires an exact RESERVED authorization-use record")
        if (scope.account_reference, scope.environment) != (
            record.account_reference,
            record.environment,
        ):
            raise PersistenceConflictError("authorization-use account scope mismatch")
        text, digest = _artifact(record)
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(connection, key, owner_id, fencing_token, now)
            authorization = self._read_artifact(
                connection,
                "authorizations",
                "scope_key=? AND authorization_id=?",
                (key, record.authorization_id),
                BrokerExecutionAuthorization,
            )
            intent = self._read_artifact(
                connection,
                "intents",
                "scope_key=? AND economic_intent_id=?",
                (key, record.economic_intent_id),
                BrokerOrderIntent,
            )
            if authorization is None or intent is None or intent.authorization_id != record.authorization_id or intent.idempotency_key != record.idempotency_key:
                raise PersistenceConflictError("authorization-use claim requires correlated durable artifacts")
            existing = connection.execute(
                "SELECT authorization_use_id, artifact_json, artifact_sha256 FROM authorization_uses WHERE scope_key=? AND authorization_id=?",
                (key, record.authorization_id),
            ).fetchone()
            if existing is not None:
                if tuple(existing[1:]) != (text, digest):
                    raise PersistenceConflictError("authorization already has a conflicting use claim")
                return AuthorizationClaimResult(ClaimDisposition.ALREADY_CLAIMED, existing[0])
            connection.execute(
                "INSERT INTO authorization_uses VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    record.authorization_id,
                    record.authorization_use_id,
                    record.economic_intent_id,
                    record.idempotency_key,
                    record.state.value,
                    text,
                    digest,
                ),
            )
            self._append_audit(
                connection,
                key,
                event_type="AUTHORIZATION_USE_RESERVED",
                occurred_at=now,
                recorded_at=now,
                actor_reference=actor_reference,
                references={
                    "authorization_id": record.authorization_id,
                    "authorization_use_id": record.authorization_use_id,
                },
                payload_sha256=digest,
            )
            if fail_before_commit:
                raise BrokerSafetyStoreError("injected claim failure before commit")
        return AuthorizationClaimResult(ClaimDisposition.ACQUIRED, record.authorization_use_id)

    def transition_authorization_use(
        self,
        scope: BrokerAccountScope,
        *,
        authorization_id: str,
        target_state: AuthorizationUseState,
        occurred_at: str,
        reason: str | None,
        owner_id: str,
        fencing_token: int,
        actor_reference: str,
    ) -> BrokerAuthorizationUseRecord:
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(connection, key, owner_id, fencing_token, occurred_at)
            current = self._read_artifact(
                connection,
                "authorization_uses",
                "scope_key=? AND authorization_id=?",
                (key, authorization_id),
                BrokerAuthorizationUseRecord,
            )
            if current is None:
                raise PersistenceConflictError("authorization-use claim is missing")
            updated = transition_broker_authorization_use(
                current,
                target_state,
                authorization_id=current.authorization_id,
                economic_intent_id=current.economic_intent_id,
                idempotency_key=current.idempotency_key,
                occurred_at=occurred_at,
                reason=reason,
            )
            text, digest = _artifact(updated)
            connection.execute(
                "UPDATE authorization_uses SET state=?, artifact_json=?, artifact_sha256=? WHERE scope_key=? AND authorization_id=?",
                (updated.state.value, text, digest, key, authorization_id),
            )
            self._append_audit(
                connection,
                key,
                event_type=f"AUTHORIZATION_USE_{updated.state.value}",
                occurred_at=occurred_at,
                recorded_at=occurred_at,
                actor_reference=actor_reference,
                references={"authorization_id": authorization_id},
                payload_sha256=digest,
            )
        return updated

    def persist_high_water(
        self,
        scope: BrokerAccountScope,
        progression: ForwardEligibilityProgression,
        *,
        owner_id: str,
        fencing_token: int,
        now: str,
        actor_reference: str,
    ) -> ForwardEligibilityHighWaterMark:
        if type(progression) is not ForwardEligibilityProgression:
            raise BrokerSafetyStoreError("progression must be exact")
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(connection, key, owner_id, fencing_token, now)
            mark, changed = self._advance_high_water(connection, key, progression)
            if changed:
                _, digest = _source_artifact(mark)
                self._append_audit(
                    connection,
                    key,
                    event_type="ELIGIBILITY_HIGH_WATER_ADVANCED",
                    occurred_at=now,
                    recorded_at=now,
                    actor_reference=actor_reference,
                    references={"lineage_key": _lineage_key(progression.lineage_key)},
                    payload_sha256=digest,
                )
        return mark

    def _advance_high_water(
        self,
        connection: sqlite3.Connection,
        scope_key: str,
        progression: ForwardEligibilityProgression,
    ) -> tuple[ForwardEligibilityHighWaterMark, bool]:
        lineage = _lineage_key(progression.lineage_key)
        row = connection.execute(
            "SELECT artifact_json, artifact_sha256 FROM high_water WHERE scope_key=? AND lineage_key=?",
            (scope_key, lineage),
        ).fetchone()
        if row is None:
            mark = ForwardEligibilityHighWaterMark.from_progression(progression)
        else:
            if _digest_bytes(row[0].encode()) != row[1]:
                raise StoreCorruptionError("high-water digest mismatch")
            try:
                current = load_forward_eligibility_high_water_mark_json(row[0])
            except Exception as exc:
                raise StoreCorruptionError("persisted high-water mark is invalid") from exc
            mark = validate_forward_eligibility_high_water_mark(progression, current)
            if mark == current:
                return current, False
        text, digest = _source_artifact(mark)
        connection.execute(
            "INSERT INTO high_water VALUES(?, ?, ?, ?) ON CONFLICT(scope_key, lineage_key) DO UPDATE SET artifact_json=excluded.artifact_json, artifact_sha256=excluded.artifact_sha256",
            (scope_key, lineage, text, digest),
        )
        return mark, True

    def load_high_water(self, scope: BrokerAccountScope, lineage_key: ForwardEligibilityLineageKey) -> ForwardEligibilityHighWaterMark | None:
        with self._connect(readonly=True) as connection:
            row = connection.execute(
                "SELECT artifact_json, artifact_sha256 FROM high_water WHERE scope_key=? AND lineage_key=?",
                (_scope_key(scope), _lineage_key(lineage_key)),
            ).fetchone()
        if row is None:
            return None
        if _digest_bytes(row[0].encode()) != row[1]:
            raise StoreCorruptionError("high-water digest mismatch")
        try:
            return load_forward_eligibility_high_water_mark_json(row[0])
        except Exception as exc:
            raise StoreCorruptionError("persisted high-water mark is invalid") from exc

    def persist_submission(
        self,
        scope: BrokerAccountScope,
        record: BrokerSubmissionRecord,
        *,
        owner_id: str,
        fencing_token: int,
        now: str,
        actor_reference: str,
    ) -> int:
        if type(record) is not BrokerSubmissionRecord or record.state is not BrokerSubmissionState.PREPARED:
            raise BrokerSafetyStoreError("direct submission persistence requires exact PREPARED state")
        self._validate_intent_scope(
            scope,
            self._require_durable_intent(scope, record.intent_id),
        )
        expected = prepare_broker_submission(
            self._require_durable_intent(scope, record.intent_id),
            attempt_id=record.attempt_id,
            recorded_at=record.recorded_at,
        )
        if record != expected:
            raise PersistenceConflictError("PREPARED submission does not match the frozen A4 constructor")
        text, digest = _artifact(record)
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(connection, key, owner_id, fencing_token, now)
            intent = self._read_artifact(
                connection,
                "intents",
                "scope_key=? AND economic_intent_id=?",
                (key, record.intent_id),
                BrokerOrderIntent,
            )
            if intent is None or record.stable_client_order_id != intent.canonical_client_order_id:
                raise PersistenceConflictError("submission requires its correlated durable intent")
            row = connection.execute(
                "SELECT version, artifact_json, artifact_sha256 FROM submissions_current WHERE scope_key=? AND intent_id=? AND attempt_id=?",
                (key, record.intent_id, record.attempt_id),
            ).fetchone()
            if row is not None:
                if tuple(row[1:]) != (text, digest):
                    raise PersistenceConflictError("submission identity already has different facts")
                return row[0]
            connection.execute(
                "INSERT INTO submissions_current VALUES(?, ?, ?, ?, 1, ?, ?)",
                (
                    key,
                    record.intent_id,
                    record.attempt_id,
                    record.state.value,
                    text,
                    digest,
                ),
            )
            connection.execute(
                "INSERT INTO submission_history VALUES(?, ?, ?, 1, ?, ?, ?, ?)",
                (
                    key,
                    record.intent_id,
                    record.attempt_id,
                    record.state.value,
                    "INITIAL_PREPARED",
                    text,
                    digest,
                ),
            )
            self._append_audit(
                connection,
                key,
                event_type="SUBMISSION_PREPARED",
                occurred_at=now,
                recorded_at=now,
                actor_reference=actor_reference,
                references={
                    "intent_id": record.intent_id,
                    "attempt_id": record.attempt_id,
                },
                payload_sha256=digest,
            )
        return 1

    def _require_durable_intent(self, scope: BrokerAccountScope, intent_id: str) -> BrokerOrderIntent:
        with self._connect(readonly=True) as connection:
            intent = self._read_artifact(
                connection,
                "intents",
                "scope_key=? AND economic_intent_id=?",
                (_scope_key(scope), intent_id),
                BrokerOrderIntent,
            )
        if intent is None:
            raise PersistenceConflictError("submission requires its correlated durable intent")
        return intent

    def transition_submission(
        self,
        scope: BrokerAccountScope,
        *,
        intent_id: str,
        attempt_id: str,
        expected_version: int,
        evidence: BrokerSubmissionEvidence,
        recorded_at: str,
        owner_id: str,
        fencing_token: int,
        actor_reference: str,
        transition_facts: Mapping[str, object] | None = None,
    ) -> tuple[BrokerSubmissionRecord, int]:
        if evidence in (
            BrokerSubmissionEvidence.AUTHORIZATION_GATE,
            BrokerSubmissionEvidence.SUBMIT_REQUEST,
        ):
            raise BrokerSafetyStoreError("authorization and SUBMITTING are owned by atomic pre-submit")
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(connection, key, owner_id, fencing_token, recorded_at)
            row = connection.execute(
                "SELECT version FROM submissions_current WHERE scope_key=? AND intent_id=? AND attempt_id=?",
                (key, intent_id, attempt_id),
            ).fetchone()
            if row is None or row[0] != expected_version:
                raise PersistenceConflictError("submission version compare-and-swap failed")
            current = self._read_artifact(
                connection,
                "submissions_current",
                "scope_key=? AND intent_id=? AND attempt_id=?",
                (key, intent_id, attempt_id),
                BrokerSubmissionRecord,
            )
            intent = self._read_artifact(
                connection,
                "intents",
                "scope_key=? AND economic_intent_id=?",
                (key, intent_id),
                BrokerOrderIntent,
            )
            if current is None or intent is None:
                raise StoreCorruptionError("submission or intent reference is missing")
            updated = transition_broker_submission(
                current,
                intent,
                evidence,
                recorded_at=recorded_at,
                **dict(transition_facts or {}),
            )
            version = expected_version + 1
            text, digest = _artifact(updated)
            cursor = connection.execute(
                "UPDATE submissions_current SET state=?, version=?, artifact_json=?, artifact_sha256=? WHERE scope_key=? AND intent_id=? AND attempt_id=? AND version=?",
                (
                    updated.state.value,
                    version,
                    text,
                    digest,
                    key,
                    intent_id,
                    attempt_id,
                    expected_version,
                ),
            )
            if cursor.rowcount != 1:
                raise PersistenceConflictError("submission version compare-and-swap failed")
            connection.execute(
                "INSERT INTO submission_history VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    intent_id,
                    attempt_id,
                    version,
                    updated.state.value,
                    evidence.value,
                    text,
                    digest,
                ),
            )
            self._append_audit(
                connection,
                key,
                event_type="SUBMISSION_TRANSITIONED",
                occurred_at=recorded_at,
                recorded_at=recorded_at,
                actor_reference=actor_reference,
                references={
                    "intent_id": intent_id,
                    "attempt_id": attempt_id,
                    "evidence": evidence.value,
                },
                payload_sha256=digest,
            )
        return updated, version

    def commit_pre_submit(
        self,
        scope: BrokerAccountScope,
        progression: ForwardEligibilityProgression,
        authorization: BrokerExecutionAuthorization,
        intent: BrokerOrderIntent,
        reserved_use: BrokerAuthorizationUseRecord,
        authorized_submission: BrokerSubmissionRecord,
        *,
        persistence_version: str,
        occurred_at: str,
        owner_id: str,
        fencing_token: int,
        actor_reference: str,
        gate_facts: Mapping[str, object],
        fail_at: str | None = None,
    ) -> PreSubmitCommit:
        self._validate_intent_scope(scope, intent)
        _safe_text("persistence_version", persistence_version)
        if type(authorization) is not BrokerExecutionAuthorization:
            raise BrokerSafetyStoreError("authorization must be exact")
        if (
            (
                authorization.broker_id,
                authorization.environment,
                authorization.account_reference,
            )
            != (
                scope.broker_id,
                scope.environment,
                scope.account_reference,
            )
            or authorization.progression_fingerprint != progression.progression_fingerprint
            or intent.progression_fingerprint != progression.progression_fingerprint
        ):
            raise PersistenceConflictError("pre-submit progression or authorization scope mismatch")
        if type(reserved_use) is not BrokerAuthorizationUseRecord or reserved_use.state is not AuthorizationUseState.RESERVED:
            raise BrokerSafetyStoreError("pre-submit requires exact RESERVED authorization use")
        if type(authorized_submission) is not BrokerSubmissionRecord or authorized_submission.state is not BrokerSubmissionState.AUTHORIZED:
            raise BrokerSafetyStoreError("pre-submit requires exact AUTHORIZED submission")
        consumed = transition_broker_authorization_use(
            reserved_use,
            AuthorizationUseState.CONSUMED,
            authorization_id=authorization.authorization_id,
            economic_intent_id=intent.economic_intent_id,
            idempotency_key=intent.idempotency_key,
            occurred_at=occurred_at,
        )
        submitting = transition_broker_submission(
            authorized_submission,
            intent,
            BrokerSubmissionEvidence.SUBMIT_REQUEST,
            recorded_at=occurred_at,
            pre_submit_persistence_version=persistence_version,
            authorization=authorization,
            authorization_use=consumed,
            **dict(gate_facts),
        )
        reserved_text, reserved_digest = _artifact(reserved_use)
        consumed_text, consumed_digest = _artifact(consumed)
        auth_text, auth_digest = _artifact(authorization)
        intent_text, intent_digest = _artifact(intent)
        submission_text, submission_digest = _artifact(submitting)
        request_digest = _digest_bytes(
            _canonical(
                {
                    "authorized_submission_sha256": _artifact(authorized_submission)[1],
                    "authorization_sha256": auth_digest,
                    "intent_sha256": intent_digest,
                    "persistence_version": persistence_version,
                    "progression_sha256": _digest_bytes(export_forward_eligibility_progression_json(progression).encode()),
                    "reserved_use_sha256": reserved_digest,
                    "submitting_sha256": submission_digest,
                }
            )
        )
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(connection, key, owner_id, fencing_token, occurred_at)
            existing_use_row = connection.execute(
                "SELECT authorization_use_id, economic_intent_id, idempotency_key, state, artifact_json, artifact_sha256 FROM authorization_uses WHERE scope_key=? AND authorization_id=?",
                (key, authorization.authorization_id),
            ).fetchone()
            if existing_use_row is not None:
                durable_use = self._validate_artifact_row(existing_use_row[4:], BrokerAuthorizationUseRecord)
                if (
                    durable_use.authorization_use_id,
                    durable_use.economic_intent_id,
                    durable_use.idempotency_key,
                    durable_use.state.value,
                ) != tuple(existing_use_row[:4]) or durable_use.authorization_id != authorization.authorization_id:
                    raise StoreCorruptionError("durable authorization-use identity is inconsistent")
                if durable_use.state is AuthorizationUseState.CONSUMED:
                    return self._resolve_pre_submit_replay(
                        connection,
                        key,
                        durable_use,
                        submitting,
                        persistence_version,
                        request_digest,
                    )
                if durable_use.state is not AuthorizationUseState.RESERVED or (existing_use_row[4], existing_use_row[5]) != (reserved_text, reserved_digest):
                    raise PersistenceConflictError("authorization use is not available for pre-submit")
            mark, _ = self._advance_high_water(connection, key, progression)
            self._fail(fail_at, "high_water")
            self._put_immutable(
                connection,
                "authorizations",
                ("scope_key", "authorization_id"),
                (key, authorization.authorization_id),
                auth_text,
                auth_digest,
            )
            self._fail(fail_at, "authorization")
            self._put_intent(connection, key, intent)
            self._fail(fail_at, "intent")
            if existing_use_row is None:
                connection.execute(
                    "INSERT INTO authorization_uses VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        key,
                        reserved_use.authorization_id,
                        reserved_use.authorization_use_id,
                        reserved_use.economic_intent_id,
                        reserved_use.idempotency_key,
                        reserved_use.state.value,
                        reserved_text,
                        reserved_digest,
                    ),
                )
            cursor = connection.execute(
                "UPDATE authorization_uses SET state=?, artifact_json=?, artifact_sha256=? WHERE scope_key=? AND authorization_id=? AND authorization_use_id=? AND state=? AND artifact_sha256=?",
                (
                    consumed.state.value,
                    consumed_text,
                    consumed_digest,
                    key,
                    consumed.authorization_id,
                    consumed.authorization_use_id,
                    AuthorizationUseState.RESERVED.value,
                    reserved_digest,
                ),
            )
            if cursor.rowcount != 1:
                raise PersistenceConflictError("authorization use was not durably RESERVED")
            self._fail(fail_at, "authorization_use")
            if connection.execute(
                "SELECT 1 FROM submissions_current WHERE scope_key=? AND intent_id=?",
                (key, submitting.intent_id),
            ).fetchone():
                raise PersistenceConflictError("economic intent already has a submission attempt")
            connection.execute(
                "INSERT INTO submissions_current VALUES(?, ?, ?, ?, 1, ?, ?)",
                (
                    key,
                    submitting.intent_id,
                    submitting.attempt_id,
                    submitting.state.value,
                    submission_text,
                    submission_digest,
                ),
            )
            connection.execute(
                "INSERT INTO submission_history VALUES(?, ?, ?, 1, ?, ?, ?, ?)",
                (
                    key,
                    submitting.intent_id,
                    submitting.attempt_id,
                    submitting.state.value,
                    "ATOMIC_PRE_SUBMIT",
                    submission_text,
                    submission_digest,
                ),
            )
            self._fail(fail_at, "submission")
            combined_digest = _digest_bytes(
                _canonical(
                    {
                        "authorization": auth_digest,
                        "authorization_use": consumed_digest,
                        "high_water": _source_artifact(mark)[1],
                        "intent": intent_digest,
                        "request": request_digest,
                        "submission": submission_digest,
                    }
                )
            )
            audit = self._append_audit(
                connection,
                key,
                event_type="PRE_SUBMIT_COMMITTED",
                occurred_at=occurred_at,
                recorded_at=occurred_at,
                actor_reference=actor_reference,
                references={
                    "authorization_id": authorization.authorization_id,
                    "authorization_use_id": consumed.authorization_use_id,
                    "intent_id": intent.economic_intent_id,
                    "attempt_id": submitting.attempt_id,
                },
                payload_sha256=combined_digest,
            )
            self._fail(fail_at, "audit")
            connection.execute(
                "INSERT INTO pre_submit_commits VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    consumed.authorization_use_id,
                    consumed.authorization_id,
                    consumed.economic_intent_id,
                    submitting.attempt_id,
                    persistence_version,
                    request_digest,
                    submission_digest,
                    audit.sequence,
                    audit.record_digest,
                    fencing_token,
                ),
            )
            self._fail(fail_at, "commit_record")
        return PreSubmitCommit(
            PreSubmitDisposition.COMMITTED,
            persistence_version,
            consumed.authorization_use_id,
            intent.economic_intent_id,
            submitting.attempt_id,
            fencing_token,
            audit.sequence,
            audit.record_digest,
        )

    def _resolve_pre_submit_replay(
        self,
        connection: sqlite3.Connection,
        scope_key: str,
        durable_use: BrokerAuthorizationUseRecord,
        submitting: BrokerSubmissionRecord,
        persistence_version: str,
        request_digest: str,
    ) -> PreSubmitCommit:
        commit = connection.execute(
            "SELECT authorization_id, economic_intent_id, attempt_id, "
            "persistence_version, request_sha256, submission_sha256, "
            "audit_sequence, audit_root_digest, fencing_token "
            "FROM pre_submit_commits WHERE scope_key=? "
            "AND authorization_use_id=?",
            (scope_key, durable_use.authorization_use_id),
        ).fetchone()
        if commit is None:
            raise StoreCorruptionError("CONSUMED authorization use has no pre-submit commit")
        expected = (
            durable_use.authorization_id,
            durable_use.economic_intent_id,
            submitting.attempt_id,
            persistence_version,
            request_digest,
            _artifact(submitting)[1],
        )
        if tuple(commit[:6]) != expected:
            raise PersistenceConflictError("consumed authorization use is bound to another attempt")
        history = connection.execute(
            "SELECT state, transition_kind, artifact_sha256 FROM submission_history WHERE scope_key=? AND intent_id=? AND attempt_id=? AND version=1",
            (
                scope_key,
                durable_use.economic_intent_id,
                submitting.attempt_id,
            ),
        ).fetchone()
        audit = connection.execute(
            "SELECT record_digest FROM audit WHERE scope_key=? AND sequence=?",
            (scope_key, commit[6]),
        ).fetchone()
        if (
            history is None
            or tuple(history)
            != (
                BrokerSubmissionState.SUBMITTING.value,
                "ATOMIC_PRE_SUBMIT",
                commit[5],
            )
            or audit is None
            or audit[0] != commit[7]
        ):
            raise StoreCorruptionError("pre-submit commit lost its submission or audit binding")
        return PreSubmitCommit(
            PreSubmitDisposition.ALREADY_COMMITTED,
            commit[3],
            durable_use.authorization_use_id,
            commit[1],
            commit[2],
            commit[8],
            commit[6],
            commit[7],
        )

    @staticmethod
    def _fail(selected: str | None, boundary: str) -> None:
        if selected == boundary:
            raise BrokerSafetyStoreError(f"injected pre-submit failure at {boundary}")

    def record_execution(
        self,
        scope: BrokerAccountScope,
        intent: BrokerOrderIntent,
        execution: BrokerExecutionRecord,
        *,
        expected_submission_version: int,
        owner_id: str,
        fencing_token: int,
        actor_reference: str,
    ) -> tuple[BrokerSubmissionRecord, int]:
        if type(execution) is not BrokerExecutionRecord:
            raise BrokerSafetyStoreError("execution must be exact")
        self._validate_intent_scope(scope, intent)
        text, digest = _artifact(execution)
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(connection, key, owner_id, fencing_token, execution.received_at)
            durable_intent = self._read_artifact(
                connection,
                "intents",
                "scope_key=? AND economic_intent_id=?",
                (key, intent.economic_intent_id),
                BrokerOrderIntent,
            )
            if durable_intent != intent:
                raise PersistenceConflictError("execution intent does not match durable economic facts")
            existing = connection.execute(
                "SELECT artifact_json, artifact_sha256 FROM executions WHERE scope_key=? AND execution_id=?",
                (key, execution.execution_id),
            ).fetchone()
            if existing is not None:
                if tuple(existing) != (text, digest):
                    raise PersistenceConflictError("execution ID maps to conflicting facts")
                row = connection.execute(
                    "SELECT version FROM submissions_current WHERE scope_key=? AND intent_id=? AND attempt_id=?",
                    (key, execution.intent_id, execution.attempt_id),
                ).fetchone()
                current = self._read_artifact(
                    connection, "submissions_current", "scope_key=? AND intent_id=? AND attempt_id=?", (key, execution.intent_id, execution.attempt_id), BrokerSubmissionRecord
                )
                if row is None or current is None:
                    raise StoreCorruptionError("execution replay lost its submission reference")
                return current, row[0]
            row = connection.execute(
                "SELECT version FROM submissions_current WHERE scope_key=? AND intent_id=? AND attempt_id=?",
                (key, execution.intent_id, execution.attempt_id),
            ).fetchone()
            if row is None or row[0] != expected_submission_version:
                raise PersistenceConflictError("submission version compare-and-swap failed")
            current = self._read_artifact(connection, "submissions_current", "scope_key=? AND intent_id=? AND attempt_id=?", (key, execution.intent_id, execution.attempt_id), BrokerSubmissionRecord)
            updated = apply_broker_execution(current, intent, execution)
            connection.execute(
                "INSERT INTO executions VALUES(?, ?, ?, ?, ?, ?)",
                (key, execution.execution_id, execution.intent_id, execution.attempt_id, text, digest),
            )
            version = expected_submission_version + 1
            state_text, state_digest = _artifact(updated)
            connection.execute(
                "UPDATE submissions_current SET state=?, version=?, artifact_json=?, artifact_sha256=? WHERE scope_key=? AND intent_id=? AND attempt_id=? AND version=?",
                (updated.state.value, version, state_text, state_digest, key, updated.intent_id, updated.attempt_id, expected_submission_version),
            )
            connection.execute(
                "INSERT INTO submission_history VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    updated.intent_id,
                    updated.attempt_id,
                    version,
                    updated.state.value,
                    f"EXECUTION:{execution.execution_id}",
                    state_text,
                    state_digest,
                ),
            )
            self._append_audit(
                connection,
                key,
                event_type="EXECUTION_PERSISTED",
                occurred_at=execution.fill_time,
                recorded_at=execution.received_at,
                actor_reference=actor_reference,
                references={"execution_id": execution.execution_id, "intent_id": execution.intent_id},
                payload_sha256=digest,
            )
        return updated, version

    def persist_kill_switch(
        self,
        scope: BrokerAccountScope,
        snapshot: BrokerKillSwitchSnapshot,
        *,
        owner_id: str,
        fencing_token: int,
        now: str,
        actor_reference: str,
    ) -> BrokerKillSwitchSnapshot:
        if type(snapshot) is not BrokerKillSwitchSnapshot:
            raise BrokerSafetyStoreError("kill switch must be exact")
        text, digest = _artifact(snapshot)
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(connection, key, owner_id, fencing_token, now)
            inserted = self._put_immutable(connection, "kill_switch", ("scope_key", "kill_switch_version"), (key, snapshot.kill_switch_version), text, digest)
            if inserted:
                self._append_audit(
                    connection,
                    key,
                    event_type="KILL_SWITCH_PERSISTED",
                    occurred_at=now,
                    recorded_at=now,
                    actor_reference=actor_reference,
                    references={"kill_switch_version": snapshot.kill_switch_version},
                    payload_sha256=digest,
                )
        return snapshot

    def recovery_plan(self, scope: BrokerAccountScope) -> BrokerRecoveryPlan:
        key = _scope_key(scope)
        reasons: list[str] = []
        try:
            audit_sequence, audit_root = self.verify_audit_chain(scope)
            with self._connect(readonly=True) as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    raise StoreCorruptionError("SQLite integrity check failed")
                lease = connection.execute("SELECT fencing_token FROM leases WHERE scope_key=?", (key,)).fetchone()

                high_water = connection.execute(
                    "SELECT lineage_key, artifact_json, artifact_sha256 FROM high_water WHERE scope_key=?",
                    (key,),
                ).fetchall()
                for row in high_water:
                    if _digest_bytes(row[1].encode()) != row[2]:
                        raise StoreCorruptionError("high-water digest mismatch")
                    try:
                        mark = load_forward_eligibility_high_water_mark_json(row[1])
                    except Exception as exc:
                        raise StoreCorruptionError("persisted high-water artifact is invalid") from exc
                    if _lineage_key(mark.lineage_key) != row[0]:
                        raise StoreCorruptionError("high-water lineage key is not canonical")

                authorization_rows = connection.execute(
                    "SELECT authorization_id, artifact_json, artifact_sha256 FROM authorizations WHERE scope_key=?",
                    (key,),
                ).fetchall()
                authorizations: dict[str, BrokerExecutionAuthorization] = {}
                for row in authorization_rows:
                    authorization = self._validate_artifact_row(row[1:], BrokerExecutionAuthorization)
                    if authorization.authorization_id != row[0] or (
                        authorization.broker_id,
                        authorization.environment,
                        authorization.account_reference,
                    ) != (
                        scope.broker_id,
                        scope.environment,
                        scope.account_reference,
                    ):
                        raise StoreCorruptionError("authorization identity or account scope mismatch")
                    authorizations[row[0]] = authorization

                intent_rows = connection.execute(
                    "SELECT economic_intent_id, idempotency_key, client_order_id, authorization_id, artifact_json, artifact_sha256 FROM intents WHERE scope_key=?",
                    (key,),
                ).fetchall()
                intents: dict[str, BrokerOrderIntent] = {}
                for row in intent_rows:
                    intent = self._validate_artifact_row(row[4:], BrokerOrderIntent)
                    if (
                        (
                            intent.economic_intent_id,
                            intent.idempotency_key,
                            intent.canonical_client_order_id,
                            intent.authorization_id,
                        )
                        != tuple(row[:4])
                        or intent.authorization_id not in authorizations
                        or (
                            intent.broker_id,
                            intent.environment,
                            intent.account_reference,
                        )
                        != (
                            scope.broker_id,
                            scope.environment,
                            scope.account_reference,
                        )
                    ):
                        raise StoreCorruptionError("order intent identity, authorization, or scope mismatch")
                    intents[row[0]] = intent

                provider_rows = connection.execute(
                    "SELECT provider_name, provider_client_id, canonical_client_id FROM provider_ids WHERE scope_key=?",
                    (key,),
                ).fetchall()
                canonical_client_ids = {intent.canonical_client_order_id for intent in intents.values()}
                for row in provider_rows:
                    _safe_text("provider_name", row[0])
                    _safe_text("provider_client_id", row[1])
                    _safe_text("canonical_client_id", row[2])
                    if row[2] not in canonical_client_ids:
                        raise StoreCorruptionError("provider mapping has no canonical durable intent")
                use_rows = connection.execute(
                    "SELECT authorization_id, authorization_use_id, economic_intent_id, idempotency_key, state, artifact_json, artifact_sha256 FROM authorization_uses WHERE scope_key=?",
                    (key,),
                ).fetchall()
                uses_by_id: dict[str, BrokerAuthorizationUseRecord] = {}
                for row in use_rows:
                    use = self._validate_artifact_row(row[5:], BrokerAuthorizationUseRecord)
                    if (
                        (
                            use.authorization_id,
                            use.authorization_use_id,
                            use.economic_intent_id,
                            use.idempotency_key,
                            use.state.value,
                        )
                        != tuple(row[:5])
                        or use.authorization_id not in authorizations
                        or use.economic_intent_id not in intents
                        or intents[use.economic_intent_id].idempotency_key != use.idempotency_key
                        or (use.environment, use.account_reference) != (scope.environment, scope.account_reference)
                    ):
                        raise StoreCorruptionError("authorization-use identity or reference mismatch")
                    uses_by_id[use.authorization_use_id] = use
                submission_rows = connection.execute(
                    "SELECT intent_id, attempt_id, state, version, artifact_json, artifact_sha256 FROM submissions_current WHERE scope_key=?",
                    (key,),
                ).fetchall()
                submissions: dict[tuple[str, str], tuple[int, BrokerSubmissionRecord, str, str]] = {}
                for row in submission_rows:
                    submission = self._validate_artifact_row(row[4:], BrokerSubmissionRecord)
                    if (
                        (submission.intent_id, submission.attempt_id, submission.state.value) != tuple(row[:3])
                        or submission.intent_id not in intents
                        or submission.stable_client_order_id != intents[submission.intent_id].canonical_client_order_id
                    ):
                        raise StoreCorruptionError("submission identity or intent reference mismatch")
                    submissions[(row[0], row[1])] = (
                        row[3],
                        submission,
                        row[4],
                        row[5],
                    )

                commit_rows = connection.execute(
                    "SELECT authorization_use_id, authorization_id, "
                    "economic_intent_id, attempt_id, persistence_version, "
                    "request_sha256, submission_sha256, audit_sequence, "
                    "audit_root_digest, fencing_token "
                    "FROM pre_submit_commits WHERE scope_key=?",
                    (key,),
                ).fetchall()
                commits_by_submission: dict[tuple[str, str], sqlite3.Row] = {}
                for row in commit_rows:
                    use = uses_by_id.get(row[0])
                    pair = (row[2], row[3])
                    audit = connection.execute(
                        "SELECT record_digest FROM audit WHERE scope_key=? AND sequence=?",
                        (key, row[7]),
                    ).fetchone()
                    for name, value in (
                        ("persistence_version", row[4]),
                        ("request_sha256", row[5]),
                        ("submission_sha256", row[6]),
                        ("audit_root_digest", row[8]),
                    ):
                        (_require_sha(name, value) if name.endswith("sha256") or name == "audit_root_digest" else _safe_text(name, value))
                    if (
                        use is None
                        or use.state is not AuthorizationUseState.CONSUMED
                        or (
                            use.authorization_id,
                            use.economic_intent_id,
                        )
                        != (row[1], row[2])
                        or pair not in submissions
                        or submissions[pair][1].pre_submit_persistence_version != row[4]
                        or type(row[7]) is not int
                        or row[7] <= 0
                        or type(row[9]) is not int
                        or row[9] <= 0
                        or audit is None
                        or audit[0] != row[8]
                    ):
                        raise StoreCorruptionError("pre-submit commit identity or audit binding is invalid")
                    if pair in commits_by_submission:
                        raise StoreCorruptionError("multiple pre-submit commits exist for one submission")
                    commits_by_submission[pair] = row
                committed_use_ids = {row[0] for row in commit_rows}
                for use_id, use in uses_by_id.items():
                    if (use.state is AuthorizationUseState.CONSUMED) != (use_id in committed_use_ids):
                        raise StoreCorruptionError("consumed authorization use and pre-submit commit differ")
                history_rows = connection.execute(
                    "SELECT intent_id, attempt_id, version, state, transition_kind, artifact_json, artifact_sha256 FROM submission_history WHERE scope_key=? ORDER BY intent_id, attempt_id, version",
                    (key,),
                ).fetchall()
                observed_versions: dict[tuple[str, str], list[int]] = {}
                histories: dict[
                    tuple[str, str],
                    list[tuple[str, BrokerSubmissionRecord, str]],
                ] = {}
                last_history: dict[tuple[str, str], tuple[int, str, str]] = {}
                for row in history_rows:
                    historical = self._validate_artifact_row(row[5:], BrokerSubmissionRecord)
                    pair = (row[0], row[1])
                    if (
                        historical.intent_id,
                        historical.attempt_id,
                        historical.state.value,
                    ) != (row[0], row[1], row[3]) or pair not in submissions:
                        raise StoreCorruptionError("submission history identity or reference mismatch")
                    _safe_text("transition_kind", row[4])
                    observed_versions.setdefault(pair, []).append(row[2])
                    histories.setdefault(pair, []).append((row[4], historical, row[6]))
                    last_history[pair] = (row[2], row[5], row[6])
                for pair, (
                    version,
                    _current,
                    text,
                    digest,
                ) in submissions.items():
                    if observed_versions.get(pair) != list(range(1, version + 1)):
                        raise StoreCorruptionError("submission history versions are not contiguous")
                    if last_history.get(pair) != (version, text, digest):
                        raise StoreCorruptionError("submission current state does not match history")
                execution_rows = connection.execute(
                    "SELECT execution_id, intent_id, attempt_id, artifact_json, artifact_sha256 FROM executions WHERE scope_key=?",
                    (key,),
                ).fetchall()
                executions_by_submission: dict[tuple[str, str], dict[str, BrokerExecutionRecord]] = {}
                for row in execution_rows:
                    execution = self._validate_artifact_row(row[3:], BrokerExecutionRecord)
                    pair = (execution.intent_id, execution.attempt_id)
                    if (
                        execution.execution_id,
                        execution.intent_id,
                        execution.attempt_id,
                    ) != tuple(row[:3]) or pair not in submissions:
                        raise StoreCorruptionError("execution identity or submission reference mismatch")
                    executions_by_submission.setdefault(pair, {})[execution.execution_id] = execution
                for pair, history in histories.items():
                    self._validate_submission_lifecycle(
                        intents[pair[0]],
                        history,
                        executions_by_submission.get(pair, {}),
                        commits_by_submission.get(pair),
                    )
                    current_execution_ids = set(submissions[pair][1].execution_ids)
                    if current_execution_ids != set(executions_by_submission.get(pair, {})):
                        raise StoreCorruptionError("submission and durable execution IDs differ")
                kill_rows = connection.execute(
                    "SELECT kill_switch_version, artifact_json, artifact_sha256 FROM kill_switch WHERE scope_key=? ORDER BY rowid",
                    (key,),
                ).fetchall()
                for row in kill_rows:
                    snapshot = self._validate_artifact_row(row[1:], BrokerKillSwitchSnapshot)
                    if snapshot.kill_switch_version != row[0] or (
                        snapshot.broker_id,
                        snapshot.environment,
                        snapshot.account_reference,
                    ) != (
                        scope.broker_id,
                        scope.environment,
                        scope.account_reference,
                    ):
                        raise StoreCorruptionError("kill-switch identity or account scope mismatch")

                receipt_rows = connection.execute(
                    "SELECT receipt_id, bundle_json, bundle_sha256, "
                    "anchored_sequence, anchored_root, "
                    "previous_receipt_reference, target, object_reference, "
                    "anchored_at FROM anchor_receipts WHERE scope_key=? "
                    "ORDER BY anchored_at, receipt_id",
                    (key,),
                ).fetchall()
                previous_receipt_reference: str | None = None
                anchor_checkpoint: tuple[int, str, str] | None = None
                for row in receipt_rows:
                    try:
                        bundle_data = json.loads(row[1])
                        bundle = AuditAnchorBundle(**bundle_data)
                    except Exception as exc:
                        raise StoreCorruptionError("persisted anchor bundle is invalid") from exc
                    bundle_bytes = canonical_audit_anchor_bundle_bytes(bundle)
                    anchored_audit = connection.execute(
                        "SELECT record_digest FROM audit WHERE scope_key=? AND sequence=?",
                        (key, row[3]),
                    ).fetchone()
                    for name, value in (
                        ("receipt_id", row[0]),
                        ("object_reference", row[7]),
                    ):
                        _safe_text(name, value)
                    _require_sha("bundle_sha256", row[2])
                    _require_sha("anchored_root", row[4])
                    _timestamp("anchored_at", row[8])
                    if (
                        bundle_bytes.decode("utf-8") != row[1]
                        or _digest_bytes(bundle_bytes) != row[2]
                        or bundle.store_id != self.store_id
                        or bundle.scope_key != key
                        or bundle.store_schema_version != STORE_SCHEMA_VERSION
                        or bundle.first_audit_sequence != 1
                        or (
                            bundle.last_audit_sequence,
                            bundle.audit_root_digest,
                            bundle.previous_receipt_reference,
                        )
                        != (row[3], row[4], row[5])
                        or row[5] != previous_receipt_reference
                        or row[6] not in {TEST_ANCHOR_TARGET, EXTERNAL_WORM_TARGET}
                        or anchored_audit is None
                        or anchored_audit[0] != row[4]
                    ):
                        raise StoreCorruptionError("external anchor checkpoint chain is invalid")
                    previous_receipt_reference = row[0]
                    anchor_checkpoint = (row[3], row[4], row[6])

                nonterminal = sum(row[2] not in _TERMINAL_SUBMISSIONS for row in submission_rows)
                unresolved = sum(row[2] in _UNRESOLVED_SUBMISSIONS for row in submission_rows)
                if nonterminal:
                    reasons.append("NONTERMINAL_SUBMISSION_STATE")
                if unresolved:
                    reasons.append("UNRESOLVED_SUBMISSION_STATE")
                kill = None if not kill_rows else (kill_rows[-1][0],)
                receipt = None if not receipt_rows else (receipt_rows[-1][0],)
                uses = use_rows
                intents_for_count = intent_rows
        except Exception as exc:
            if isinstance(exc, (StoreCorruptionError, BrokerSafetyStoreError)):
                reasons.append("STORE_OR_AUDIT_CORRUPTION")
                lease = None
                high_water = uses = intents_for_count = submission_rows = ()
                nonterminal = unresolved = 0
                kill = receipt = anchor_checkpoint = None
                audit_sequence, audit_root = 0, ZERO_AUDIT_DIGEST
            else:
                raise
        return BrokerRecoveryPlan(
            scope,
            None if lease is None else lease[0],
            len(high_water),
            len(uses),
            len(intents_for_count),
            nonterminal,
            unresolved,
            None if kill is None else kill[0],
            audit_sequence,
            audit_root,
            None if receipt is None else receipt[0],
            None if anchor_checkpoint is None else anchor_checkpoint[0],
            None if anchor_checkpoint is None else anchor_checkpoint[1],
            None if anchor_checkpoint is None else anchor_checkpoint[2],
            bool(reasons),
            tuple(sorted(set(reasons))),
        )

    @staticmethod
    def _validate_artifact_row(row: sqlite3.Row | tuple[Any, ...], expected: type) -> Any:
        if _digest_bytes(row[0].encode()) != row[1]:
            raise StoreCorruptionError("persisted artifact digest mismatch")
        try:
            value = load_broker_safety_artifact_json(row[0])
        except Exception as exc:
            raise StoreCorruptionError("persisted artifact is invalid") from exc
        if type(value) is not expected:
            raise StoreCorruptionError("persisted artifact type mismatch")
        return value

    @staticmethod
    def _validate_submission_lifecycle(
        intent: BrokerOrderIntent,
        history: list[tuple[str, BrokerSubmissionRecord, str]],
        executions: dict[str, BrokerExecutionRecord],
        commit: sqlite3.Row | None,
    ) -> None:
        if not history:
            raise StoreCorruptionError("submission history is missing")
        first_kind, prior, first_digest = history[0]
        if first_kind == "INITIAL_PREPARED":
            expected = prepare_broker_submission(
                intent,
                attempt_id=prior.attempt_id,
                recorded_at=prior.recorded_at,
            )
            if commit is not None:
                raise StoreCorruptionError("prepared submission cannot have a pre-submit commit")
        elif first_kind == "ATOMIC_PRE_SUBMIT":
            if commit is None or first_digest != commit[6]:
                raise StoreCorruptionError("submitting history is not bound to its pre-submit commit")
            expected = prior
            if prior.state is not BrokerSubmissionState.SUBMITTING:
                raise StoreCorruptionError("atomic pre-submit history must begin in SUBMITTING")
        else:
            raise StoreCorruptionError("submission history has an unsafe initial state")
        if prior != expected:
            raise StoreCorruptionError("initial submission snapshot is not canonical")

        observed_execution_ids: set[str] = set()
        for transition_kind, current, _digest in history[1:]:
            if transition_kind.startswith("EXECUTION:"):
                execution_id = transition_kind.removeprefix("EXECUTION:")
                execution = executions.get(execution_id)
                if execution is None or execution_id in observed_execution_ids:
                    raise StoreCorruptionError("submission history execution reference is invalid")
                expected = apply_broker_execution(prior, intent, execution)
                observed_execution_ids.add(execution_id)
            else:
                try:
                    evidence = BrokerSubmissionEvidence(transition_kind)
                except ValueError as exc:
                    raise StoreCorruptionError("submission history transition is unknown") from exc
                if evidence in {
                    BrokerSubmissionEvidence.AUTHORIZATION_GATE,
                    BrokerSubmissionEvidence.SUBMIT_REQUEST,
                }:
                    raise StoreCorruptionError("submission history bypasses atomic pre-submit")
                expected = transition_broker_submission(
                    prior,
                    intent,
                    evidence=evidence,
                    recorded_at=current.recorded_at,
                    broker_order_id=current.broker_order_id,
                    sanitized_outcome=current.sanitized_outcome,
                    last_reconciliation_id=current.last_reconciliation_id,
                )
            if current != expected:
                raise StoreCorruptionError("submission history violates the A4 transition contract")
            prior = current
        if observed_execution_ids != set(executions):
            raise StoreCorruptionError("durable execution records do not match submission history")

    def build_anchor_bundle(self, scope: BrokerAccountScope, *, created_at: str) -> AuditAnchorBundle:
        created = _timestamp("created_at", created_at)
        sequence, root = self.verify_audit_chain(scope)
        if sequence == 0:
            raise BrokerSafetyStoreError("cannot anchor an empty audit chain")
        key = _scope_key(scope)
        with self._connect(readonly=True) as connection:
            latest_audit = connection.execute(
                "SELECT recorded_at FROM audit WHERE scope_key=? ORDER BY sequence DESC LIMIT 1",
                (key,),
            ).fetchone()
            receipt = connection.execute(
                "SELECT receipt_id FROM anchor_receipts WHERE scope_key=? ORDER BY anchored_at DESC, receipt_id DESC LIMIT 1",
                (key,),
            ).fetchone()
        if latest_audit is None or created < _timestamp("latest_audit_recorded_at", latest_audit[0]):
            raise BrokerSafetyStoreError("anchor bundle cannot predate its audit root")
        return AuditAnchorBundle(
            "audit_anchor_bundle_v1",
            self.store_id,
            key,
            STORE_SCHEMA_VERSION,
            1,
            sequence,
            root,
            created_at,
            None if receipt is None else receipt[0],
        )

    def record_anchor_receipt(
        self,
        scope: BrokerAccountScope,
        bundle: AuditAnchorBundle,
        receipt: ExternalAuditAnchorReceipt,
        *,
        owner_id: str,
        fencing_token: int,
        actor_reference: str,
    ) -> ExternalAuditAnchorReceipt:
        if type(bundle) is not AuditAnchorBundle:
            raise BrokerSafetyStoreError("bundle must be exact")
        if type(receipt) is not ExternalAuditAnchorReceipt:
            raise BrokerSafetyStoreError("receipt must be exact")
        if _timestamp("anchored_at", receipt.anchored_at) < _timestamp("bundle_created_at", bundle.created_at):
            raise PersistenceConflictError("external receipt predates its bundle")
        bundle_text = canonical_audit_anchor_bundle_bytes(bundle).decode("utf-8")
        bundle_digest = _digest_bytes(bundle_text.encode("utf-8"))
        if receipt.bundle_sha256 != bundle_digest:
            raise PersistenceConflictError("external receipt does not correlate to bundle")
        if receipt.target not in {
            TEST_ANCHOR_TARGET,
            EXTERNAL_WORM_TARGET,
        }:
            raise PersistenceConflictError("external receipt target is not an approved anchor class")
        if (bundle.store_id, bundle.scope_key) != (
            self.store_id,
            _scope_key(scope),
        ):
            raise PersistenceConflictError("anchor bundle store scope mismatch")
        with self._transaction() as connection:
            key = self._ensure_scope(connection, scope)
            self._check_fence(
                connection,
                key,
                owner_id,
                fencing_token,
                receipt.anchored_at,
            )
            existing = connection.execute(
                "SELECT bundle_json, bundle_sha256, anchored_sequence, "
                "anchored_root, previous_receipt_reference, target, "
                "object_reference, anchored_at FROM anchor_receipts "
                "WHERE scope_key=? AND receipt_id=?",
                (key, receipt.receipt_id),
            ).fetchone()
            expected_receipt = (
                bundle_text,
                bundle_digest,
                bundle.last_audit_sequence,
                bundle.audit_root_digest,
                bundle.previous_receipt_reference,
                receipt.target,
                receipt.object_reference,
                receipt.anchored_at,
            )
            if existing is not None:
                if tuple(existing) != expected_receipt:
                    raise PersistenceConflictError("external receipt identity conflict")
                return receipt
            latest_receipt = connection.execute(
                "SELECT receipt_id FROM anchor_receipts WHERE scope_key=? ORDER BY anchored_at DESC, receipt_id DESC LIMIT 1",
                (key,),
            ).fetchone()
            latest_reference = None if latest_receipt is None else latest_receipt[0]
            if bundle.previous_receipt_reference != latest_reference:
                raise PersistenceConflictError("anchor bundle does not extend the current receipt chain")
            sequence, root = self.verify_audit_chain(scope)
            if (bundle.last_audit_sequence, bundle.audit_root_digest) != (
                sequence,
                root,
            ):
                raise PersistenceConflictError("anchor bundle no longer matches current audit root")
            connection.execute(
                "INSERT INTO anchor_receipts VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    key,
                    receipt.receipt_id,
                    bundle_text,
                    bundle_digest,
                    bundle.last_audit_sequence,
                    bundle.audit_root_digest,
                    bundle.previous_receipt_reference,
                    receipt.target,
                    receipt.object_reference,
                    receipt.anchored_at,
                ),
            )
            payload = bundle_digest
            self._append_audit(
                connection,
                key,
                event_type="EXTERNAL_ANCHOR_RECEIPT_VERIFIED",
                occurred_at=receipt.anchored_at,
                recorded_at=receipt.anchored_at,
                actor_reference=actor_reference,
                references={"receipt_id": receipt.receipt_id},
                payload_sha256=payload,
            )
        return receipt

    def _high_water_summary(self, connection: sqlite3.Connection) -> str:
        rows = connection.execute("SELECT scope_key, lineage_key, artifact_sha256 FROM high_water ORDER BY scope_key, lineage_key").fetchall()
        return _digest_bytes(_canonical([list(row) for row in rows]))

    @staticmethod
    def _scope_from_row(row: sqlite3.Row | tuple[Any, ...]) -> BrokerAccountScope:
        try:
            scope = BrokerAccountScope(row[1], BrokerEnvironment(row[2]), row[3])
        except Exception as exc:
            raise StoreCorruptionError("persisted account scope is invalid") from exc
        if _scope_key(scope) != row[0]:
            raise StoreCorruptionError("persisted account scope key is not canonical")
        return scope

    @staticmethod
    def _scope_checkpoints(
        connection: sqlite3.Connection,
    ) -> tuple[ScopeAuditCheckpoint, ...]:
        scopes = connection.execute("SELECT scope_key FROM account_scopes ORDER BY scope_key").fetchall()
        result: list[ScopeAuditCheckpoint] = []
        for scope in scopes:
            audit = connection.execute(
                "SELECT sequence, record_digest FROM audit WHERE scope_key=? ORDER BY sequence DESC LIMIT 1",
                (scope[0],),
            ).fetchone()
            receipt = connection.execute(
                "SELECT receipt_id FROM anchor_receipts WHERE scope_key=? ORDER BY anchored_at DESC, receipt_id DESC LIMIT 1",
                (scope[0],),
            ).fetchone()
            result.append(
                ScopeAuditCheckpoint(
                    scope[0],
                    0 if audit is None else audit[0],
                    ZERO_AUDIT_DIGEST if audit is None else audit[1],
                    None if receipt is None else receipt[0],
                )
            )
        return tuple(result)

    @classmethod
    def _validate_snapshot(cls, backup_path: Path, manifest: BackupManifest) -> None:
        try:
            connection = sqlite3.connect(
                f"file:{backup_path.as_posix()}?mode=ro",
                uri=True,
                factory=_ClosingConnection,
            )
            connection.row_factory = sqlite3.Row
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
            user_version = connection.execute("PRAGMA user_version").fetchone()[0]
            metadata = dict(connection.execute("SELECT key, value FROM metadata ORDER BY key"))
            migrations = connection.execute("SELECT version, migration_id, checksum, applied_at FROM schema_migrations ORDER BY version").fetchall()
            schema = {row[0]: row[1] for row in connection.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            expected_schema = {statement.split("(", 1)[0].removeprefix("CREATE TABLE "): statement for statement in _SCHEMA}
            scope_rows = connection.execute("SELECT scope_key, broker_id, environment, account_reference FROM account_scopes ORDER BY scope_key").fetchall()
            scopes = tuple(cls._scope_from_row(row) for row in scope_rows)
            observed_checkpoints = cls._scope_checkpoints(connection)
            high_water_rows = connection.execute("SELECT scope_key, lineage_key, artifact_sha256 FROM high_water ORDER BY scope_key, lineage_key").fetchall()
            summary = _digest_bytes(_canonical([list(row) for row in high_water_rows]))
        except Exception as exc:
            raise RestoreRejectedError("backup database cannot be structurally validated") from exc
        finally:
            if "connection" in locals():
                connection.close()
        if (
            integrity != "ok"
            or foreign_key_errors
            or user_version != STORE_SCHEMA_VERSION
            or metadata
            != {
                "schema_version": str(STORE_SCHEMA_VERSION),
                "store_id": manifest.store_id,
            }
            or len(migrations) != 1
            or tuple(migrations[0][:3]) != (STORE_SCHEMA_VERSION, MIGRATION_ID, MIGRATION_CHECKSUM)
            or schema != expected_schema
            or observed_checkpoints != manifest.scope_audit_checkpoints
            or summary != manifest.high_water_summary_sha256
        ):
            raise RestoreRejectedError("backup contents do not match schema or manifest")
        try:
            _timestamp("migration_applied_at", migrations[0][3])
        except Exception as exc:
            raise RestoreRejectedError("backup migration timestamp is invalid") from exc

        validator = object.__new__(cls)
        validator.path = backup_path
        validator.busy_timeout_ms = 5000
        expected = {item.scope_key: item for item in manifest.scope_audit_checkpoints}
        for scope in scopes:
            try:
                sequence, root = validator.verify_audit_chain(scope)
                plan = validator.recovery_plan(scope)
            except Exception as exc:
                raise RestoreRejectedError("backup scope cannot be recovered") from exc
            checkpoint = expected[_scope_key(scope)]
            if (
                "STORE_OR_AUDIT_CORRUPTION" in plan.blocking_reasons
                or (sequence, root)
                != (
                    checkpoint.last_audit_sequence,
                    checkpoint.last_audit_root,
                )
                or plan.last_external_receipt_reference != checkpoint.latest_external_receipt_reference
            ):
                raise RestoreRejectedError("backup scope logical recovery validation failed")

    def backup(
        self,
        destination: str | Path,
        manifest_path: str | Path,
        *,
        backup_timestamp: str,
    ) -> BackupManifest:
        backup_time = _timestamp("backup_timestamp", backup_timestamp)
        destination = Path(destination).resolve()
        manifest_path = Path(manifest_path).resolve()
        if destination == manifest_path:
            raise BrokerSafetyStoreError("backup database and manifest paths must differ")
        if destination.exists() or manifest_path.exists():
            raise BrokerSafetyStoreError("backup targets must not already exist")
        with self._connect(readonly=True) as source:
            latest_audit = source.execute("SELECT recorded_at FROM audit ORDER BY recorded_at DESC LIMIT 1").fetchone()
            if latest_audit is not None and backup_time < _timestamp("latest_audit_recorded_at", latest_audit[0]):
                raise BrokerSafetyStoreError("backup cannot predate durable audit state")
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
            finally:
                target.close()

        database_sha = _digest_bytes(destination.read_bytes())
        with sqlite3.connect(destination, factory=_ClosingConnection) as snapshot:
            snapshot.row_factory = sqlite3.Row
            checkpoints = self._scope_checkpoints(snapshot)
            summary = self._high_water_summary(snapshot)
        manifest = BackupManifest(
            "broker_store_backup_manifest_v2",
            self.store_id,
            STORE_SCHEMA_VERSION,
            backup_timestamp,
            database_sha,
            checkpoints,
            summary,
        )
        manifest_path.write_bytes(_canonical(asdict(manifest)) + b"\n")
        if self.verify_backup(destination, manifest_path) != manifest:
            raise BrokerSafetyStoreError("new backup did not verify exactly")
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO backup_history VALUES(?, ?, ?)",
                (
                    database_sha,
                    _canonical(asdict(manifest)).decode(),
                    backup_timestamp,
                ),
            )
        return manifest

    @staticmethod
    def verify_backup(
        backup_path: str | Path,
        manifest_path: str | Path,
    ) -> BackupManifest:
        backup_path = Path(backup_path).resolve()
        manifest_path = Path(manifest_path).resolve()
        try:
            manifest_bytes = manifest_path.read_bytes()
            data = json.loads(manifest_bytes.decode("utf-8"))
            checkpoint_data = data["scope_audit_checkpoints"]
            if type(checkpoint_data) is not list:
                raise ValueError("scope checkpoints must be a JSON list")
            data["scope_audit_checkpoints"] = tuple(ScopeAuditCheckpoint(**item) for item in checkpoint_data)
            manifest = BackupManifest(**data)
            if manifest_bytes != _canonical(asdict(manifest)) + b"\n":
                raise ValueError("backup manifest is not canonical")
        except Exception as exc:
            raise RestoreRejectedError("backup manifest is invalid") from exc
        try:
            observed_sha = _digest_bytes(backup_path.read_bytes())
        except OSError as exc:
            raise RestoreRejectedError("backup database cannot be read") from exc
        if observed_sha != manifest.database_sha256:
            raise RestoreRejectedError("backup database digest mismatch")
        SQLiteBrokerSafetyStore._validate_snapshot(backup_path, manifest)
        return manifest

    @classmethod
    def restore_backup(
        cls,
        backup_path: str | Path,
        manifest_path: str | Path,
        destination: str | Path,
        *,
        active: bool,
        checkpoint: (TrustedRecoveryCheckpoint | tuple[TrustedRecoveryCheckpoint, ...] | None) = None,
        restored_at: str,
    ) -> SQLiteBrokerSafetyStore | ForensicBrokerSafetyStore:
        restore_time = _timestamp("restored_at", restored_at)
        manifest = cls.verify_backup(backup_path, manifest_path)
        destination = Path(destination).resolve()
        if destination.exists():
            raise RestoreRejectedError("restore destination must not already exist")
        if active:
            if type(checkpoint) is TrustedRecoveryCheckpoint:
                checkpoints = (checkpoint,)
            elif (
                type(checkpoint) is tuple
                and all(type(item) is TrustedRecoveryCheckpoint for item in checkpoint)
                and tuple(item.scope_key for item in checkpoint) == tuple(sorted(item.scope_key for item in checkpoint))
                and len({item.scope_key for item in checkpoint}) == len(checkpoint)
            ):
                checkpoints = checkpoint
            else:
                raise RestoreRejectedError("active restore requires exact per-scope trusted checkpoints")
            manifest_by_scope = {item.scope_key: item for item in manifest.scope_audit_checkpoints}
            if {item.scope_key for item in checkpoints} != set(manifest_by_scope):
                raise RestoreRejectedError("trusted checkpoints must cover every persisted scope")
            with sqlite3.connect(
                f"file:{Path(backup_path).resolve().as_posix()}?mode=ro",
                uri=True,
                factory=_ClosingConnection,
            ) as source:
                latest_audit = source.execute("SELECT recorded_at FROM audit ORDER BY recorded_at DESC LIMIT 1").fetchone()
                if latest_audit is not None and restore_time < _timestamp("latest_audit_recorded_at", latest_audit[0]):
                    raise RestoreRejectedError("restore time predates backup audit state")
                for trusted in checkpoints:
                    snapshot = manifest_by_scope[trusted.scope_key]
                    if trusted.store_id != manifest.store_id or snapshot.last_audit_sequence < trusted.minimum_audit_sequence:
                        raise RestoreRejectedError("backup is behind trusted recovery state")
                    row = source.execute(
                        "SELECT record_digest FROM audit WHERE scope_key=? AND sequence=?",
                        (
                            trusted.scope_key,
                            trusted.minimum_audit_sequence,
                        ),
                    ).fetchone()
                    if row is None or row[0] != trusted.audit_root_digest:
                        raise RestoreRejectedError("backup does not preserve a trusted per-scope audit checkpoint")

        source = sqlite3.connect(
            f"file:{Path(backup_path).resolve().as_posix()}?mode=ro",
            uri=True,
        )
        target = sqlite3.connect(destination)
        try:
            source.backup(target)
        finally:
            source.close()
            target.close()
        if not active:
            return ForensicBrokerSafetyStore(destination)

        store = cls(destination, migration_applied_at=restored_at)
        with store._connect(readonly=True) as connection:
            scope_rows = connection.execute("SELECT scope_key, broker_id, environment, account_reference FROM account_scopes ORDER BY scope_key").fetchall()
        scopes = tuple(store._scope_from_row(row) for row in scope_rows)
        for scope in scopes:
            plan = store.recovery_plan(scope)
            if "STORE_OR_AUDIT_CORRUPTION" in plan.blocking_reasons:
                raise RestoreRejectedError("restored scope failed logical recovery validation")
        with store._transaction() as connection:
            for scope in scopes:
                store._append_audit(
                    connection,
                    _scope_key(scope),
                    event_type="BACKUP_RESTORE_ACTIVATED",
                    occurred_at=restored_at,
                    recorded_at=restored_at,
                    actor_reference="operator-recovery",
                    references={"backup_sha256": manifest.database_sha256},
                    payload_sha256=manifest.database_sha256,
                )
        return store


class ForensicBrokerSafetyStore:
    """Read-only handle returned when anti-rollback activation proof is absent."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"file:{self.path.as_posix()}?mode=ro",
            uri=True,
            factory=_ClosingConnection,
        )
        connection.execute("PRAGMA query_only = ON")
        return connection


__all__ = [
    "EXTERNAL_WORM_TARGET",
    "TEST_ANCHOR_TARGET",
    "ForensicBrokerSafetyStore",
    "MIGRATION_CHECKSUM",
    "MIGRATION_ID",
    "SQLiteBrokerSafetyStore",
    "audit_anchor_bundle_sha256",
    "canonical_audit_anchor_bundle_bytes",
]

"""Independent-process probes for the Phase 56.5C SQLite boundary."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from tests import test_phase_56_5a4_broker_execution_contracts as a4_tests
from tw_stock_tool.broker_safety import (
    BrokerAccountScope,
    BrokerEnvironment,
    BrokerSubmissionEvidence,
    LeaseConflictError,
    PersistenceConflictError,
    SQLiteBrokerSafetyStore,
    load_broker_safety_artifact_json,
    prepare_broker_submission,
    reserve_broker_authorization_use,
    transition_broker_submission,
)


def _commit_pre_submit(
    store: SQLiteBrokerSafetyStore,
    attempt_variant: str,
) -> str:
    fx = a4_tests.Phase565A4Tests("test_key_is_exact_stable_and_excludes_runtime_metadata")
    fx.setUp()
    scope = BrokerAccountScope(
        fx.authorization.broker_id,
        fx.authorization.environment,
        fx.authorization.account_reference,
    )
    attempt_id = a4_tests.IDS[12] if attempt_variant == "same" else a4_tests.IDS[13]
    reserved = reserve_broker_authorization_use(
        fx.authorization,
        fx.intent,
        authorization_use_id=a4_tests.IDS[10],
        reserved_at="2025-01-02T00:00:32Z",
    )
    prepared = prepare_broker_submission(
        fx.intent,
        attempt_id=attempt_id,
        recorded_at="2025-01-02T00:00:32Z",
    )
    authorized = transition_broker_submission(
        prepared,
        fx.intent,
        BrokerSubmissionEvidence.AUTHORIZATION_GATE,
        recorded_at="2025-01-02T00:00:33Z",
        **fx.gate_facts(),
    )
    gate_facts = fx.gate_facts()
    del gate_facts["authorization"]
    try:
        result = store.commit_pre_submit(
            scope,
            fx.head,
            fx.authorization,
            fx.intent,
            reserved,
            authorized,
            persistence_version="persist-v1",
            occurred_at="2025-01-02T00:00:34Z",
            owner_id="race-owner",
            fencing_token=1,
            actor_reference="race-worker",
            gate_facts=gate_facts,
        )
    except PersistenceConflictError:
        return "CONFLICT"
    return result.disposition.value


def main() -> int:
    mode, database, payload = sys.argv[1:4]
    store = SQLiteBrokerSafetyStore(database)
    scope = BrokerAccountScope(
        "demo-broker",
        BrokerEnvironment.SANDBOX,
        "acct-safe",
    )
    if mode == "lease":
        try:
            lease = store.acquire_lease(
                scope,
                owner_id=payload,
                acquired_at="2025-01-02T00:00:00Z",
                expires_at="2025-01-02T00:10:00Z",
            )
        except LeaseConflictError:
            print("CONFLICT")
        else:
            print(f"ACQUIRED:{lease.fencing_token}")
        return 0
    if mode == "claim":
        record = load_broker_safety_artifact_json(Path(payload).read_text(encoding="utf-8"))
        result = store.claim_authorization_use(
            scope,
            record,
            owner_id="race-owner",
            fencing_token=1,
            now="2025-01-02T00:00:34Z",
            actor_reference="race-worker",
        )
        print(result.disposition.value)
        return 0
    if mode == "pre-submit":
        print(_commit_pre_submit(store, payload))
        return 0
    if mode == "abrupt":
        connection = sqlite3.connect(database, isolation_level=None)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "INSERT INTO backup_history VALUES(?, ?, ?)",
            ("f" * 64, "uncommitted", "2025-01-02T00:00:10Z"),
        )
        os._exit(7)
    raise AssertionError(mode)


if __name__ == "__main__":
    raise SystemExit(main())

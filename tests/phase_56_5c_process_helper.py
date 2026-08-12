"""Independent-process probes for the Phase 56.5C SQLite boundary."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tw_stock_tool.broker_safety import (
    BrokerAccountScope,
    BrokerEnvironment,
    LeaseConflictError,
    SQLiteBrokerSafetyStore,
    load_broker_safety_artifact_json,
)


def main() -> int:
    mode, database, payload = sys.argv[1:4]
    store = SQLiteBrokerSafetyStore(database)
    scope = BrokerAccountScope("demo-broker", BrokerEnvironment.SANDBOX, "acct-safe")
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

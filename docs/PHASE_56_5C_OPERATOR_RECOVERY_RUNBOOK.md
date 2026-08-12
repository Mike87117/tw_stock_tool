# Phase 56.5C durable broker-safety recovery runbook

This runbook covers the single-host SQLite safety store only. Phase 56.5C has no broker submit, cancel, modify, replace, SDK conversion, live endpoint, or network anchor writer. Recovery must remain broker-neutral and read-only with respect to every broker.

## Safety invariants

- Treat `SUBMITTING`, `UNKNOWN_SUBMISSION_STATE`, `RECONCILIATION_REQUIRED`, and every other non-terminal submission as open exposure. Do not authorize another attempt while `BrokerRecoveryPlan.blocks_new_authorization` is true.
- Never edit or reset an immutable authorization, intent, authorization-use record, submission history row, execution, audit row, anchor receipt, backup, or manifest.
- Never reuse an authorization by changing a `CONSUMED` or `ABANDONED` use record back to `RESERVED`.
- Only the current unexpired account lease and its monotonic fencing token may write. Expiry and takeover, including takeover by the same owner name, create a new token.
- Keep database files, WAL/SHM files, backups, manifests, and trusted checkpoints free of credentials and raw broker payloads. Filesystem permissions and encryption at rest are operator responsibilities.

## Normal restart

1. Stop every controller process for the affected broker/environment/account scope.
2. Preserve a filesystem-level forensic copy of the database and any WAL/SHM files before repair work. Do not open that copy as an active store.
3. Open the original with `SQLiteBrokerSafetyStore`; schema identity, migration checksum, SQLite integrity, artifact digests, logical references, submission history, and audit linkage must all validate.
4. Acquire the account lease. Record the returned fencing token; discard every cached older token.
5. Generate `recovery_plan(scope)`. A corruption reason or any non-terminal submission blocks new authorization.
6. Correlate unresolved submissions with authoritative, read-only broker evidence outside this store. Do not infer a safe retry from timeout, absence, client metadata, or process exit.
7. Persist only transitions supported by the existing pure A4 transition contract. If evidence remains ambiguous, retain or transition to an unresolved state and stop.
8. Re-run `recovery_plan(scope)`, verify the audit chain, and create an `AuditAnchorBundle` for the reviewed root. Phase 56.5C records only a receipt returned by an external port; it performs no network write.

## Crash windows

The pre-submit transaction is all-or-nothing. A crash before commit leaves none of its high-water, authorization, intent, use, `SUBMITTING`, or audit changes. A successful commit durably ends in `SUBMITTING`; after that point, broker submission outcome is unknown until authoritative evidence proves otherwise. Never create a second attempt merely because the caller did not receive a broker response.

After any abrupt exit, restart normally, acquire a new or still-valid lease as appropriate, verify recovery state, and resolve all non-terminal attempts before new authorization. WAL recovery is delegated to SQLite; operators must not delete WAL/SHM files to force startup.

## Backup and verification

1. Call `backup()` with new destination and manifest paths. Keep both immutable after creation.
2. Run `verify_backup()` and retain its database digest, store ID, schema version, high-water summary, audit checkpoint, and latest external receipt reference.
3. Store a `TrustedRecoveryCheckpoint` separately from the database and backup. It is the anti-rollback trust input; copying a checkpoint from the candidate backup is not independent evidence.
4. Periodically perform a forensic restore and verify that recovery remains blocked where unresolved state exists.

## Restore

- Default to `active=False`. A forensic restore exposes a read-only SQLite connection and cannot become a controller store.
- An active restore requires an independently retained trusted checkpoint for the same store and scope. Reject a backup behind the checkpoint, with the wrong audit digest, wrong store identity, invalid manifest/database digest, invalid schema, broken audit, or broken durable references.
- Restore to a new path only. Never overwrite the active database.
- After an accepted active restore, preserve the appended restore audit event, acquire a fresh lease/fence before controller writes, run recovery, and resolve all non-terminal submissions before authorizing anything.

## Suspected corruption or compromise

Stop all controllers, preserve evidence, and use a forensic restore. Do not repair rows in place, recompute hashes to conceal a mismatch, truncate audit history, or lower a trusted checkpoint. Escalate to the safety owner with the store ID, account scope hash, last independently anchored receipt, manifest digest, and sanitized error category. Credentials or raw broker payloads must not be attached to the incident record.

Phase 56.5C does not grant permission to trade. Any future broker mutation boundary requires a separately reviewed phase and explicit authorization.

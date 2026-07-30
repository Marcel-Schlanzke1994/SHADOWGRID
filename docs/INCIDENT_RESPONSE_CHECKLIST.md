# Incident response checklist

Status: engineering procedure complete; named responders and external contacts are
`EXTERNAL-OPERATOR_REQUIRED`.

## Detect and contain

- [ ] Open an incident record with UTC start time, request IDs and pseudonymous subject IDs.
- [ ] Assign incident commander `[INCIDENT_COMMANDER_REQUIRED]`.
- [ ] Assign security, database, privacy and communications owners.
- [ ] Preserve immutable audit records, relevant logs and a verified database backup.
- [ ] Stop affected state-changing traffic at the edge when integrity is uncertain.
- [ ] Keep financial, ownership and trade tables read-only; never hand-edit them.
- [ ] Revoke affected refresh families and disable compromised accounts.
- [ ] Rotate exposed provider credentials in secret stores; never paste them into tickets.
- [ ] Pause the worker only when continued idempotent processing could worsen the incident.

## Investigate and recover

- [ ] Define affected worlds, accounts, data classes, processors and UTC interval.
- [ ] Correlate request IDs across API and worker logs.
- [ ] Run ledger/share reconciliation and preserve the output.
- [ ] Restore only from a verified backup using `docs/BACKUP_RESTORE.md`.
- [ ] Apply financial correction only through a reviewed compensating domain transaction.
- [ ] Run migrations, `pnpm data:verify`, auth/world/logout smoke and worker readiness.
- [ ] Reopen traffic in stages and monitor readiness, 5xx, latency and worker health.

## Privacy and notification decision

- [ ] Escalate to `[PRIVACY_CONTACT_REQUIRED]` and `[LEGAL_CONTACT_REQUIRED]`.
- [ ] Determine notification duties and deadlines for every applicable jurisdiction.
- [ ] Notify affected processors through their contractual security channels.
- [ ] Use only facts verified by logs/evidence; do not speculate or imply legal approval.
- [ ] Preserve notification decisions and timestamps outside the public repository.

## Close and learn

- [ ] Record root cause, containment, recovery, affected data and verified impact.
- [ ] Create tracked remediation with owner, severity and due date.
- [ ] Add a regression test or monitor for the failure mode.
- [ ] Review key rotation, retention and least-privilege controls.
- [ ] Conduct a blameless post-incident review and close only after evidence is attached.

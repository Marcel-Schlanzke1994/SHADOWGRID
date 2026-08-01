# Privacy launch checklist

This is an engineering readiness checklist, not legal approval. Items marked
`EXTERNAL-LEGAL` or `EXTERNAL-OPERATOR` must be completed with real deployment facts before
public launch.

## Repository-complete controls

- [x] Authenticated export endpoint is ownership-scoped and covered by tests.
- [x] Exact ledger values are exported as decimal strings, never binary floats.
- [x] Account deletion disables login and invalidates access/refresh sessions.
- [x] Direct account fields, email recipients and pending invitations are pseudonymized.
- [x] One-time tokens are invalidated and queued email content is redacted.
- [x] Immutable ledger, trade, ownership, season and audit history is retained.
- [x] Auth logs exclude email, passwords, raw tokens, verification links and bodies.
- [x] Analytics are disabled by default and no advertising SDK is installed.
- [x] Mobile data-safety copy identifies itself as an engineering draft.
- [x] Privacy UI exposes export and account-deletion actions.

## Required before public launch

- [ ] `EXTERNAL-LEGAL`: approve the privacy notice for every served jurisdiction.
- [ ] `EXTERNAL-LEGAL`: approve every duration in `DATA_RETENTION_MATRIX.md`.
- [ ] `EXTERNAL-LEGAL`: determine lawful basis and data-subject request deadlines.
- [ ] `EXTERNAL-LEGAL`: approve the immutable finance/audit retention rationale.
- [ ] `EXTERNAL-OPERATOR`: replace `[SUPPORT_CONTACT_REQUIRED]` with a monitored address.
- [ ] `EXTERNAL-OPERATOR`: complete every deployed processor in
  `PROCESSOR_REGISTER_TEMPLATE.md` and attach the applicable agreement.
- [ ] `EXTERNAL-OPERATOR`: record hosting, database, Redis, SMTP, monitoring, backup region
  and subprocessor facts.
- [ ] `EXTERNAL-OPERATOR`: configure request intake, identity verification and escalation.
- [ ] `EXTERNAL-OPERATOR`: bind the incident roles and contacts in
  `INCIDENT_RESPONSE_CHECKLIST.md`.
- [ ] `EXTERNAL-LEGAL`: reconcile Google Play Data Safety and App Store privacy answers
  with the final deployed processors and SDK inventory.
- [ ] `EXTERNAL-OPERATOR`: verify production log and backup deletion policies in provider
  consoles.

Launch is blocked until all unchecked items have an accountable owner, dated evidence and
approval. Repository completion does not imply regulatory compliance.

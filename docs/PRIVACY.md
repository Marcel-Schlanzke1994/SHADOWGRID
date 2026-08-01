# Privacy and data lifecycle

The service stores email, display name, locale, password hash, session metadata, game state, organization membership, notifications and security/audit events. It does not require real names, location, contacts, advertising identifiers or payment data in the launch slice.

Users can export account/game data and request deletion. Deletion revokes sessions and pseudonymizes identity while retaining ledger/audit records required for world integrity and abuse investigation. Production policy must define jurisdiction-specific retention periods, processor contracts, SMTP/log retention and a support contact before public launch.

Logs must not contain passwords, raw refresh tokens, TOTP secrets, email-link tokens or full request bodies. Analytics are disabled by default. Any future crash/analytics SDK requires a privacy review and updated mobile store disclosures before integration.

The engagement implementation does not add an analytics SDK, advertising identifier,
device fingerprint or behavioral profile. Its optional product-measurement path is an
admin-only server aggregation into `engagement_metrics_daily`. Rows contain daily counts
and basis-point rates only; they contain no user/profile/device identifier or chat content
and are immutable after generation. Satisfaction and fairness aggregates are suppressed
unless at least five responses are represented. Generation remains off unless an
authorized operator explicitly runs it after the privacy gate has been approved.

Launch engineering and the deliberately unresolved legal/operator fields are tracked in:

- [Privacy launch checklist](PRIVACY_LAUNCH_CHECKLIST.md)
- [Data retention matrix](DATA_RETENTION_MATRIX.md)
- [Processor register template](PROCESSOR_REGISTER_TEMPLATE.md)
- [Incident response checklist](INCIDENT_RESPONSE_CHECKLIST.md)

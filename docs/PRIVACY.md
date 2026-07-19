# Privacy and data lifecycle

The service stores email, display name, locale, password hash, session metadata, game state, organization membership, notifications and security/audit events. It does not require real names, location, contacts, advertising identifiers or payment data in the launch slice.

Users can export account/game data and request deletion. Deletion revokes sessions and pseudonymizes identity while retaining ledger/audit records required for world integrity and abuse investigation. Production policy must define jurisdiction-specific retention periods, processor contracts, SMTP/log retention and a support contact before public launch.

Logs must not contain passwords, raw refresh tokens, TOTP secrets, email-link tokens or full request bodies. Analytics are disabled by default. Any future crash/analytics SDK requires a privacy review and updated mobile store disclosures before integration.

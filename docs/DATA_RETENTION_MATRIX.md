# Data retention matrix

Durations below are deliberately not invented. `[LEGAL_DURATION_REQUIRED]` is a launch
gate to be replaced by an approved duration and jurisdiction. Technical deletion behavior
is documented separately from the legal decision.

| Data class | Storage | Technical behavior | Retention decision | Owner |
| --- | --- | --- | --- | --- |
| Email, display name, locale | `users` | Pseudonymized immediately on confirmed account deletion | `[LEGAL_DURATION_REQUIRED]` while active | Privacy |
| Password hash and TOTP secret | `users` | Hash randomized and TOTP removed on deletion | Active account lifetime | Security |
| Refresh-session metadata | `refresh_sessions` | All sessions revoked; user agent redacted on deletion | `[LEGAL_DURATION_REQUIRED]` after revocation | Security/Privacy |
| Verification/reset token hashes | `one_time_tokens` | Consumed on use or deletion; raw token is never stored | `[LEGAL_DURATION_REQUIRED]` after expiry | Security |
| Transactional email | `email_outbox` | Recipient, subject and body redacted and delivery cancelled on deletion | `[LEGAL_DURATION_REQUIRED]` for delivery evidence | Privacy/Operations |
| Player profile and world state | game tables | Retained under pseudonymous UUID for shared-world integrity | `[LEGAL_DURATION_REQUIRED]` | Game Operations/Privacy |
| Ledger, transactions, trades, shares, ownership | immutable finance tables | Never cascade-deleted; corrected only by compensating domain transaction | `[LEGAL_DURATION_REQUIRED_AND_BASIS]` | Finance Integrity/Legal |
| Audit and moderation evidence | audit/moderation tables | Retained with pseudonymous actor/target IDs | `[LEGAL_DURATION_REQUIRED_AND_BASIS]` | Trust & Safety/Legal |
| Notifications and communications | notification/social tables | Ownership-scoped; content policy requires final legal decision | `[LEGAL_DURATION_REQUIRED]` | Trust & Safety |
| Structured application logs | deployment provider | No bodies, credentials, email-link tokens or direct email field | `[PROVIDER_POLICY_REQUIRED]` | Operations/Security |
| Database backups | encrypted external backup storage | Verified, access-controlled copies; deletion follows approved backup expiry | Proposed operations rotation 7 daily/5 weekly/12 monthly, pending legal approval | Database Operations/Legal |
| Store crash/analytics data | none in launch repository | Analytics disabled; no crash/advertising SDK configured | Not collected | Product/Privacy |
| Engagement events, goals, sessions, dossiers and identity state | engagement gameplay tables | Operational, ownership-scoped game state; no device fingerprint, advertising ID or inferred vulnerability profile | `[LEGAL_DURATION_REQUIRED]`; immutable history remains pseudonymous where world integrity requires it | Product/Privacy/Game Operations |
| Aggregate engagement product metrics | `engagement_metrics_daily` | Admin-generated daily counts/rates only; no player/user/device ID or chat; survey aggregates below five responses are suppressed; rows are immutable | `[LEGAL_DURATION_REQUIRED]`; generation remains disabled until privacy approval | Product Analytics/Privacy |

Any change to collection, SDKs, processors, game telemetry or identifiers requires a new
privacy review, updated store disclosures and an updated matrix before deployment.

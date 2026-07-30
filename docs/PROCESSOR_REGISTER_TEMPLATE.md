# Processor register template

Status: `EXTERNAL-LEGAL_AND_OPERATOR_REQUIRED`. This template contains no claim that a
contract, data-processing agreement or transfer assessment exists.

Create one reviewed row for every real production service:

| Field | Required value |
| --- | --- |
| Processor legal name | `[REQUIRED]` |
| Service and purpose | `[REQUIRED]` |
| Data categories | `[REQUIRED]` |
| Data-subject categories | `[REQUIRED]` |
| Processing/hosting regions | `[REQUIRED]` |
| Subprocessors | `[REQUIRED_OR_NONE_VERIFIED]` |
| Retention/deletion controls | `[REQUIRED]` |
| Security measures | `[REQUIRED]` |
| Agreement/DPA reference | `[REQUIRED]` |
| International transfer mechanism | `[REQUIRED_OR_NOT_APPLICABLE_WITH_REASON]` |
| Incident notification terms | `[REQUIRED]` |
| Account owner | `[REQUIRED]` |
| Legal reviewer and review date | `[REQUIRED]` |
| Evidence location | `[REQUIRED_NON_SECRET_REFERENCE]` |

Minimum production inventory to resolve:

- application hosting and container runtime;
- managed PostgreSQL;
- managed Redis;
- outbound SMTP/email delivery;
- DNS/CDN/reverse proxy;
- monitoring, uptime and log storage;
- encrypted off-host backup storage;
- Google Play and Apple App Store accounts when submitted;
- support/ticketing system when selected.

Do not put credentials, contract contents or personal contacts in this repository. Record
only non-secret evidence references approved for source control.

# Security threat model

## Assets and trust boundaries

Protected assets are accounts, refresh sessions, world state, organization roles, treasury and resource ledgers, hidden intelligence accuracy, internal evidence, audit logs and administrator functions. Browser/mobile clients, reverse proxies, email links and worker queues are untrusted inputs. PostgreSQL and the API transaction boundary are trusted only after authentication and authorization.

## Primary threats and controls

| Threat | Controls |
| --- | --- |
| Credential stuffing | Argon2id hashes, generic login failure, per-identity in-process throttling, optional TOTP, HTTPS in production |
| Refresh-token theft/replay | HTTP-only cookie on web, SecureStore on mobile, hashed tokens, rotation, family revocation, session UI |
| IDOR or cross-world reads | Current profile derives from authenticated user and selected world; arbitrary profile query values are ignored; organization permissions are server-side |
| Duplicate economic action | Required idempotency keys, unique records, row locks and append-only ledger |
| Client tampering | Server calculates costs, outcome rolls, slots, timers and rewards; exact operation probability and actual intel accuracy never leave the server |
| Injection/XSS | SQLAlchemy bound statements, Pydantic validation, no HTML injection, restrictive CSP/security headers |
| CSRF | SameSite refresh cookie is scoped to auth path; mutations require bearer access token; production origins are allowlisted |
| Privilege escalation | Explicit admin/moderator dependencies, role-permission matrix, protected director role, audit entries for role/removal actions |
| Secret leakage | ignored local secret files, provider secret stores, masked scanner output, Bandit, pip-audit and pnpm audit gates |
| Resource exhaustion | 1 MiB request limit, bounded schemas, operation slots, worker timeouts, connection/service health checks |

## Residual risks

The local login throttle is per API process; multi-replica production should move counters to Redis or the edge WAF. Object storage is provisioned but the current launch slice does not accept user uploads. WebSocket fan-out is process-local; Redis pub/sub is required before horizontal realtime scaling. These do not weaken the server-authoritative HTTP game loop.

## Security response

Follow [SECURITY.md](../SECURITY.md) for private reporting. Rotate `SECRET_KEY`, `REFRESH_PEPPER`, SMTP and database credentials after suspected compromise; rotating the refresh pepper intentionally invalidates all refresh sessions. Preserve audit logs and request IDs for investigation.

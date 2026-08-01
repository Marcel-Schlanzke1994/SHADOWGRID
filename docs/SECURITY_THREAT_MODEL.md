# Security threat model

## Dependency audit exception

`GHSA-qwww-vcr4-c8h2` applies to React Router RSC server actions. SHADOWGRID uses React
Router only as a browser-side library with a FastAPI REST backend; it installs no React
Router framework/RSC server and exposes no React server actions. The audit gate therefore
ignores this advisory while pinning React Router 7.18.1 for the independent route-matching
denial-of-service fix. This exception must be removed before adopting React Router
framework or RSC mode.

## Assets and trust boundaries

Protected assets are accounts, refresh sessions, world state, organization roles, treasury and resource ledgers, hidden intelligence accuracy, internal evidence, audit logs and administrator functions. Browser/mobile clients, reverse proxies, email links and worker queues are untrusted inputs. PostgreSQL and the API transaction boundary are trusted only after authentication and authorization.

## Primary threats and controls

| Threat | Controls |
| --- | --- |
| Credential stuffing | Argon2id hashes, generic login failure, shared transactional per-identity throttling, optional TOTP, HTTPS in production |
| Refresh-token theft/replay | HTTP-only cookie on web, SecureStore on mobile, hashed tokens, rotation, family revocation, session UI |
| IDOR or cross-world reads | Current profile derives from authenticated user and selected world; arbitrary profile query values are ignored; organization permissions are server-side |
| Duplicate economic action | Required idempotency keys, unique records, row locks and append-only ledger |
| Client tampering | Server calculates costs, outcome rolls, slots, timers and rewards; exact operation probability and actual intel accuracy never leave the server |
| Injection/XSS | SQLAlchemy bound statements, Pydantic validation, no HTML injection, restrictive CSP/security headers |
| CSRF | SameSite refresh cookie is scoped to auth path; mutations require bearer access token; production origins are allowlisted |
| Privilege escalation | Explicit admin/moderator dependencies, role-permission matrix, protected director role, audit entries for role/removal actions |
| Secret leakage | ignored local secret files, provider secret stores, masked scanner output, Bandit, pip-audit and pnpm audit gates |
| Resource exhaustion | Counted 1 MiB HTTP receive limit, 16 KiB WebSocket handshake/payload limits, bounded schemas, shared exchange rate windows, operation slots, worker timeouts and service health checks |

## Residual risks

`/metrics` is intentionally compatible with Prometheus and must be network-restricted at
the reverse proxy/firewall. Object storage is provisioned but the current launch slice does
not accept user uploads. Durable database polling lets multiple realtime API processes
converge without socket-only state; Redis pub/sub would reduce delivery latency at larger
horizontal scale but is not an authority or integrity dependency.

## Security response

Follow [SECURITY.md](../SECURITY.md) for private reporting. Rotate `SECRET_KEY`, `REFRESH_PEPPER`, SMTP and database credentials after suspected compromise; rotating the refresh pepper intentionally invalidates all refresh sessions. Preserve audit logs and request IDs for investigation.

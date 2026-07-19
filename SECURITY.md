# Security policy

Report vulnerabilities privately to the repository owner. Do not include passwords, tokens, private intelligence reports or personal exports in a public issue.

Supported security controls include Argon2id password hashing, short-lived access tokens, rotating hashed refresh tokens, server-side object authorization, permission checks, rate limits, idempotency keys, an append-only ledger, structured redacted logs, secure headers and production secret injection.

Development credentials are generated locally and never committed. Treat any credential shared in chat, a PDF, a screenshot or an insecure file as compromised and rotate it before production use.

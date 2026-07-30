# SMTP provider operator gate

Status: `blocked_external`
Reason: `FINALIZE_ALLOW_EMAIL_PROVIDER_ACTIVATION` is false and no provider account or
credential is available. No provider was contacted and no secret was generated.

## Repository-complete evidence

- Registration, verification, forgot-password and reset endpoints are versioned.
- Verification/reset tokens are random, stored only as keyed hashes, expire after one hour
  and are single-use.
- Password reset revokes all refresh sessions.
- Registration, forgot, verification and reset have shared persisted abuse limits.
- Known and unknown forgot-password requests return the same public response.
- Transactional copy and public links are tested in German and English.
- Public deployment URLs must be explicit HTTPS origins.
- SMTP TLS modes and credential pairs are configuration-validated.
- SMTP delivery has retry/backoff behavior; logs do not contain message bodies or tokens.
- Local Compose publishes Mailpit SMTP on 1025 and UI on 8025.

## Exact local Mailpit proof

Requires Docker, which is unavailable on the current host:

```powershell
docker compose up -d postgres redis mailpit api worker web
pnpm test:email-release
Start-Process http://127.0.0.1:8025
```

Register one `de` and one `en` test account, verify both links target the configured public
web origin, exercise password reset, then confirm replay and expired tokens fail. Do not
copy raw tokens into tickets or committed reports.

## Provider variables

Configure only in the provider secret store:

```text
PUBLIC_WEB_URL=https://<controlled-web-origin>
SMTP_HOST=<provider-host>
SMTP_PORT=<provider-port>
SMTP_FROM=<verified-sender>
SMTP_USERNAME=<provider-username-if-required>
SMTP_PASSWORD=<provider-secret-if-required>
SMTP_STARTTLS=true|false
SMTP_USE_SSL=true|false
```

Exactly one of STARTTLS and implicit SSL may be true. Username/password must be configured
together. Never log or commit their values.

## Activation sequence

Only after sender/domain verification, processor/privacy review and explicit permission:

```powershell
$env:FINALIZE_ALLOW_EMAIL_PROVIDER_ACTIVATION = "true"
pnpm test:email-release
pnpm smoke:staging
```

Then run controlled German/English registration and reset deliveries to operator-owned test
addresses, inspect headers and links, verify replay/expiry, monitor retry/bounce behavior and
record only non-secret evidence. Production activation remains external.

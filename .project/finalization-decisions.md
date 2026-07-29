# SHADOWGRID finalization decisions

Run: `finalize-20260729T205043Z-9e706c8`

## 2026-07-29 — Source priority

- `docs/architecture/ARCHITECTURE.md` is the canonical technical source named by
  `AGENTS.md`.
- `docs/ARCHITECTURE.md` is a compatibility pointer and does not define a competing
  architecture.
- FastAPI, ARQ, PostgreSQL, Redis, React and Expo remain in place. The older Flask,
  Celery and Socket.IO roadmap references are non-canonical.
- Database migrations remain the physical schema source. OpenAPI and Pydantic schemas
  remain the API-contract source.

## 2026-07-29 — Preservation of existing work

The baseline working tree contains extensive modified and untracked implementation work.
It is treated as user-owned input. No reset, checkout, destructive clean or broad rewrite
is permitted. Finalization continues on `codex/finalize-shadowgrid`.

## 2026-07-29 — External actions

All six `FINALIZE_ALLOW_*` flags are absent and therefore false. External deployment,
push, tag creation, paid image generation, store submission and production SMTP activation
are prohibited. Locally reproducible artifacts and exact operator gates will be completed.

## 2026-07-29 — Asset generation mode

Paid generation is disabled. The repository's deterministic procedural provider is the
only authorized generation path unless the external flag changes. Procedural output must
still pass manifest, safety, integration, responsive-format and reporting gates.

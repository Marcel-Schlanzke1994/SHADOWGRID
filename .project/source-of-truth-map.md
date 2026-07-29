# SHADOWGRID source-of-truth map

Run: `finalize-20260729T205043Z-9e706c8`

| Priority | Concern | Canonical source | Conflict rule |
| ---: | --- | --- | --- |
| 1 | Technical architecture | `docs/architecture/ARCHITECTURE.md` | Retain FastAPI, ARQ, PostgreSQL, Redis, React and Expo |
| 2 | Repository execution rules | `AGENTS.md` | Security, ledger, migration, testing and Git rules are mandatory |
| 3 | Implemented domain contracts | `docs/game-design/PHASE_*.md` | Tested phase contracts define the current release behavior |
| 4 | Functional vision | `docs/game-design/SHADOWGRID_SPEC.md` | Broader ideas remain roadmap unless a phase contract implements them |
| 5 | Requirement mapping | `docs/TRACEABILITY.md` | Claims require current implementation and current test evidence |
| 6 | RC baseline | `docs/RELEASE_NOTES_0.1.0-RC1.md` | Historical evidence must be reproduced before promotion |
| 7 | Audit trail | `docs/RELEASE_CANDIDATE_FINDINGS.md` | Remediations must remain present and regression-tested |
| 8 | Quality policy | `docs/TESTING.md`, `docs/ACCESSIBILITY.md`, `docs/SECURITY_THREAT_MODEL.md`, `docs/PRIVACY.md` | No lower gate may be introduced |
| 9 | Operations | `docs/DEPLOYMENT.md`, `docs/OPERATIONS_RUNBOOK.md`, `docs/BACKUP_RESTORE.md`, `docs/MOBILE_RELEASE.md` | External actions require their explicit flags |
| 10 | Visual production | `docs/assets/CODEX_ASSET_GENERATION_GOAL.md` | Manifest order, provenance, safety and integration are mandatory |
| 11 | Localization status | `docs/localization/TRANSLATION_QUALITY.md` | Only English and German may be described as reviewed |
| 12 | Physical schema | Alembic migrations | No model-only schema claim |
| 13 | API contract | OpenAPI plus Pydantic schemas | Generated clients must match regenerated OpenAPI |

## Resolved source relationships

- `docs/ARCHITECTURE.md` is a compatibility link, not a second architecture.
- The old Flask/Celery/Socket.IO wording is superseded by the tested FastAPI/ARQ
  modular-monolith architecture.
- PostgreSQL is authoritative for deployment; SQLite is the supported zero-dependency
  local/test path.
- The broad game-design specification does not by itself prove that every aspirational
  city, industry, takeover or diplomacy mechanic is part of version 0.1.0.
- Historical RC evidence is useful input, but the dirty working tree requires a new,
  unmodified final validation run before any final claim.

# SHADOWGRID open-gap matrix

Run: `finalize-20260729T205043Z-9e706c8`

| ID | Priority | Evidence | Gap | Target phase | Status |
| --- | --- | --- | --- | --- | --- |
| GAP-001 | Critical gate | Docker/PostgreSQL/Redis commands unavailable | Compose topology, PostgreSQL and Redis cannot yet be proven on this host | 1, 3, 10, 13 | open-host |
| GAP-002 | High | 127 untracked files, including 95 under `apps/` | Existing release-critical work is not yet intentionally validated or versioned | 0, 13, 14 | in-progress |
| GAP-003 | High | Fresh `pnpm validate` | Current dirty source release gate passed; final clean-state repetition remains | 13 | resolved-phase-1 |
| GAP-004 | High | Real SQLite lifecycle plus parser/tests | Windows/Linux one-click setup/start/stop/reset/verify contract is complete | 3 | resolved |
| GAP-005 | High | Per-vertical E2E exists | No single evidenced multi-persona lifecycle through season archive | 4 | open |
| GAP-006 | High | 765 pending, one review-required asset | Mandatory asset library and all batch reports are incomplete | 6 | open |
| GAP-007 | High | No final accessibility report | Page matrix and manual WCAG checks are incomplete | 5 | open |
| GAP-008 | High | No real store screenshot readiness report | Store/community materials from the running UI are incomplete | 7 | open |
| GAP-009 | High | Load fixture is not a multi-season balance study | Required strategy simulation and three balance reports are absent | 8 | open |
| GAP-010 | High | Canonical masked scan, Bandit, `pip-audit`, `pnpm audit` | Security gate passed; only the documented unreachable RSC advisory is ignored | 9 | resolved-phase-1 |
| GAP-011 | High | Privacy launch artifacts absent | Retention, processor and incident checklists are incomplete | 9 | open |
| GAP-012 | High | Final operations report/smoke scripts absent | Staging/production dry-run, season runbook proof and monitoring evidence incomplete | 10 | open |
| GAP-013 | External | Zero EAS ID and example associated-link hosts | Signed mobile artifacts and store submission require provider credentials/config | 11 | blocked-external |
| GAP-014 | External | SMTP activation flag absent; Docker/Mailpit unavailable | Production SMTP activation is forbidden and local Mailpit proof is host-blocked | 12 | blocked-external |
| GAP-015 | High | Final release artifacts absent | Release manifest, operator checklist and immutable evidence are incomplete | 13, 14 | open |
| GAP-016 | External | Deploy/push/tag flags absent | Production deployment, remote push and release tag are forbidden | 14 | blocked-external |
| GAP-017 | High | Final completion report set absent | The allowed final status cannot yet be assigned | 15 | open |

Every gap has an owner phase. `open-host` and `blocked-external` do not block independent
repository work; final reports must preserve the exact limitation and operator action.

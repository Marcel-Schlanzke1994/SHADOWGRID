# SHADOWGRID – Architecture decisions

## 2026-07-30 — Provider-disabled assets, real store captures and release evidence

- Paid image generation remains disabled because
  `FINALIZE_ALLOW_PAID_ASSET_GENERATION` is not true. The deterministic pipeline therefore
  produces project-owned procedural premium fallbacks, retains their prompts/seeds/hashes,
  requires batchwise visual approval and never labels a fallback as provider-generated
  photorealism.
- Store screenshots are captured only from the running seeded application. Their metadata
  retains `app-screenshot` source type, Playwright capture provider, route/language report and
  functioning-application provenance. Generated or mocked user interfaces cannot satisfy the
  asset release gate.
- Store dimensions are explicit catalog contracts rather than generic aspect-ratio aliases:
  Google screenshots 2048×1152, icon 512×512, feature graphic 1024×500, iPhone
  1290×2796 and iPad 2048×2732. Catalog tests prevent regression to visually similar but
  rejected dimensions.
- The final release runner accepts only a clean candidate commit and uses a unique ignored
  SQLite database. It records command/exit-code/log-hash evidence without deleting or
  replacing the user's local game database. The evidence commit can therefore identify the
  exact tested candidate without a circular self-hash in its own manifest.

## 2026-07-28 — Release hardening and evidence boundary

- Rate limiting is shared database state rather than process memory. Fixed-window buckets
  use hashed identities and atomic upserts in their own short transactions so a failed game
  mutation does not roll back abuse accounting and multiple API workers share one limit.
- The request-size contract applies to actual received bytes, not only `Content-Length`.
  WebSocket protocol input is bounded before JSON decoding. Production CORS accepts only
  explicit HTTPS origins and never silently inherits the local development allowlist.
- Release integrity is checked from persisted rows: balanced immutable transactions,
  account projections, reserves, ownership basis points, public share supply, report
  allocations and seed identity. The verifier is read-only and runs after local seeding.
- Release load evidence must invoke application/domain services over a database fixture.
  Synthetic loops and health-only traffic remain useful smoke checks but cannot satisfy the
  roadmap's 100-player, 500-company and 10,000-order acceptance target.
- SQLite backup/restore is a zero-dependency local fallback. Production remains PostgreSQL
  custom dumps. Restore sources must resolve inside `backups/`, content must verify first,
  stopped services restart in a guarded path and local restore creates a safety backup.
- Local and CI Playwright use at most two workers against the single API/Vite pair. This is
  an orchestration capacity limit, not a relaxation of any user-flow assertion.

## 2026-07-27 — Cartel persistence, treasury approval and control semantics

- The existing `organizations` aggregate remains the physical cartel record because later
  territory, war, treaty and alliance foreign keys already depend on it. The phase-6 public
  contract uses `/cartels`; no duplicate cartel aggregate or destructive data rewrite is
  introduced.
- Exactly one active membership is enforced by a partial unique index. Historical left and
  removed memberships remain available to audit and finance records.
- Cartels own standard EUR accounts in the same balanced ledger used by players and companies.
  Pre-phase-6 treasury balances become balanced opening transactions during migration rather
  than unlogged money creation.
- Expenses above the configured threshold are requests, not reservations. A different
  authorized member must approve them; account balance is validated and transferred only at
  approval. This avoids self-approval and does not strand reserved money after a rejected
  request.
- Projects burn contributed cash through a balanced system transfer and consume influence or
  intelligence through the resource ledger. Contribution rows and project requirements are
  immutable; current progress and completion status are the mutable projection.
- District control uses integer influence totals. Version 1 requires 100 points and a 20-point
  lead, with both values configurable. The aggregate is authoritative and the existing
  territory control point is an updated compatibility projection.

## 2026-07-26 — Exchange supply, matching and dividend semantics

- One version-1 common share class is issued at IPO. Its total and the listing's issuance
  fields become immutable. Offered shares remain in an explicit issuer holding until sold;
  the sum of holdings, not a client percentage, is the authoritative supply invariant.
- Profile ownership basis points are a compatibility projection over player-held shares.
  Issuer treasury shares stay visible through the IPO order and do not acquire a fictional
  player owner or dividend entitlement.
- Matching uses resting-order price and price-time priority. Limit entry is bounded to
  5,000 basis points from the last price by default. Market remainders cancel immediately;
  limit remainders remain reserved until fill, cancellation or expiry.
- Each fill uses stable account and holding locks, a balanced cash transfer, paired
  append-only share entries, an immutable trade and one price snapshot in the same
  transaction. PostgreSQL serializes world-level exchange mutations before resource locks;
  SQLite adds a process lock for deterministic local concurrency tests.
- Founder control is the version-1 company-leadership permission for IPO and dividend
  declaration. Phase 6 governance can replace that authorization adapter without changing
  dividend snapshots or settlement.
- Dividend recipients are the profile holdings captured at declaration time. Issuer shares
  are excluded. All entitlements must be fully funded and commit together, and one
  declaration idempotency key can never pay twice.

## 2026-07-27 — Intelligence truth, trading and strategic-effect semantics

- The canonical Phase 7 report is a separate immutable snapshot aggregate. Legacy
  `intel_reports` remain readable for compatibility, while new contracts use
  `intelligence_reports`.
- Accuracy state is hidden from normal owners. Players receive a statement, confidence,
  abstract source, observation age and expiry; administrators retain the stored truth state,
  seed and rolls for dispute review.
- Costs are consumed before deterministic resolution in the same transaction. The operation
  row records the reserved amounts and outcome; a rollback restores both resources and
  result state. HMAC input uses the server seed, operation UUID and idempotency key.
- A report sale creates a new immutable buyer row with the source snapshot and original
  expiry. Version 1 buyer copies are not re-tradable, avoiding chains that obscure
  provenance while preserving the source ID.
- Strategic actions create expiring, capped effect rows instead of destructive mutations.
  Existing economy, cartel-deadline, reputation and later-operation reads compose active
  effects. Every category remains fictional and contains no procedural wrongdoing method.

## 2026-07-26 — German-city roadmap adoption

- `docs/game-design/SHADOWGRID_SPEC.md` is the canonical functional source and
  `docs/architecture/ARCHITECTURE.md` is the canonical technical source required by the
  current `AGENTS.md`.
- The newly supplied roadmap names Flask, Celery and Socket.IO, while the repository has a
  tested and deployed FastAPI, ARQ and durable realtime-event implementation. Replacing the
  framework would invalidate migrations, OpenAPI clients and release evidence without
  improving the modular-monolith transaction boundary. The smallest safe consistent choice
  is to retain FastAPI/ARQ and implement the roadmap's behavior through versioned services,
  repositories and authoritative REST contracts.
- The existing Vesper release remains historical evidence only. Roadmap completion is
  tracked separately and begins with Cologne, five strategic districts, cent-based economy
  accounts and the phased exchange/cartel/season systems.

## 2026-07-27 — Versioned event contracts and deterministic overlap

- An event definition is an immutable versioned rule contract. Administrators may disable
  future use, but balancing changes create a new version. Each activation copies the exact
  effective configuration to an immutable instance so historical reports remain reproducible.
- Preview validates scope, timing and overrides without writing state. Activation and safe
  end are distinct idempotent commands with audit records. Scheduled start and expiry use
  the same retry-safe lifecycle in the worker.
- Applicable active instances compose in `(starts_at, id)` order. Multipliers use sequential
  integer basis-point arithmetic, deltas add, and every final modifier is hard-clamped.
- The roadmap requests Socket.IO, but the canonical architecture already has authenticated
  durable realtime events. Event activation and end publish through that adapter; REST and
  PostgreSQL remain authoritative, avoiding a second state channel.

## 2026-07-27 — Season ties, rewards and reset boundary

- Season templates are immutable versions. Concrete seasons copy goals, category keys,
  starting cash and a deterministic UTC phase schedule so later template changes cannot
  rewrite a running or archived season.
- Final scores use non-negative integers. Equal scores receive the same competition rank;
  name and UUID only establish deterministic display order and never break a numeric tie.
  Input metrics and tie-group metadata remain in immutable snapshots.
- Rank-one rewards are account-level achievement, title and cosmetic records. They are
  outside the seasonal reset boundary and remain after new-season creation.
- Closing first snapshots scores, Hall of Fame, companies, share distributions, markets and
  cartels. It then releases exchange reservations and archives seasonal aggregates. Player
  cash returns to the template amount through a balanced transfer against the system
  account, and all resource corrections append ledger entries. No financial, trade, score,
  reward, audit or archive row is deleted.

## 2026-07-27 — Commercial tender and settlement semantics

- Tender scoring is transparent and integer-only, but the issuer makes the final award.
  Price, reputation, compliance, quality and applicable world-event effects are captured in
  the immutable bid breakdown so later balancing cannot rewrite an award decision.
- Capacity is not decremented on the company row. Available capacity is derived from active
  contract reservations under locks, preventing silent drift and releasing it automatically
  when a contract completes, breaches or is cancelled at season close.
- Each contract period is a unique immutable settlement. Successful periods use a balanced
  issuer-to-provider account transfer; insufficient funds create an abstract
  `payment_default` record without overdraft or partial mutation.
- Season close snapshots active contract terms, cancels active contracts and open tenders,
  and keeps bids, settlements, ledger transactions and audit records. Permanent history is
  never cascade-deleted.

## 2026-07-27 — Fixed-rate loan and default semantics

- Loan applications capture an immutable underwriting snapshot. The credit limit is the
  lower of the configured ceiling and half of enterprise value, reduced by active
  outstanding principal. Reputation, compliance, risk, investigation pressure and the
  abstract collateral score determine a clamped integer-basis-point rate.
- An offer does not change money or debt. Confirmed acceptance rechecks the limit and then
  uses one balanced system-to-company disbursement; principal is added to the company's
  debt read model in the same transaction.
- Total contractual interest uses ceiling integer arithmetic. Principal and interest
  remainder cents are placed in the earliest installments, guaranteeing that all periods
  sum exactly to the immutable total repayment.
- Insufficient installment cash creates an abstract default payment without a transaction
  or overdraft. Season close snapshots and cancels active obligations because their
  companies are archived, while payout/payment ledgers and outstanding-term history remain.

## 2026-07-27 — Bond reservation and atomic holder settlement

- Subscription cash is transferred immediately but remains reserved on the issuer account
  until activation. Partial offerings therefore cannot spend investor funds. Activation
  releases exactly sold principal and recognizes the same amount as company debt.
- Bond units are an aggregate holding backed by immutable subscription and ownership-ledger
  entries. They never create company ownership or voting rights.
- Each period preflights the complete holder obligation. Coupons and maturity redemption
  pay every holder in one transaction boundary, or all receive immutable abstract default
  settlements with no partial transfer.
- Season close snapshots live issues. Offering reservations fund full refunds; active
  issues redeem principal early when fully affordable and otherwise record an abstract
  season-close default. Financial and ownership history remains append-only.

## 2026-07-28 — Persistent property and seasonal company-use boundary

- Player property ownership is persistent account progress. Company assignment and leases
  are seasonal state because companies are archived at season close. Closing a season
  therefore snapshots the object, cancels an active lease and clears company use without
  deleting or transferring the property.
- District sale and rent indices are server-owned daily projections. They combine district
  fundamentals, cartel control and active world events with bounded integer basis-point
  arithmetic. Immutable snapshots retain the exact inputs used for each period.
- System inventory purchases, player resales, rent and headquarters upgrades all use the
  existing balanced account ledger. A failed rent period records an abstract default with
  no partial payment or overdraft.
- Property listings, company assignment, purchase, lease and improvement commands are
  idempotent. Property identity/location, transfers, lease payments, index snapshots and
  improvements are immutable historical data.

## 2026-07-26 — Economy period and insolvency semantics

- A game-economy period is one UTC hour. This matches the existing ARQ cadence while keeping
  the period key explicit and replaceable if later balancing changes the real-time duration
  of a game month.
- Market demand is allocated in integer units with deterministic largest-remainder rounding.
  Capacity is a hard ceiling; capped demand is redistributed until demand or all capacity is
  exhausted.
- Company accounts never overdraw. A loss consumes available cash and records the uncovered
  remainder as non-negative company debt. This preserves both the accounting result and the
  database non-negative-money invariant.
- A local process lock covers SQLite concurrency. PostgreSQL deployments additionally use a
  world row lock and a unique world/period constraint, so the same period cannot double-book
  across worker processes.

## 2026-07-26 — Specialist payroll and local-AI semantics

- Specialist candidates rotate once per UTC day. Their immutable generation inputs are the
  world, city, cycle date, slot and role; UUIDv5 makes retry results stable.
- Specialist effects are integer, additive and capped before entering the Phase 3 formulas.
  Low loyalty or energy disables an effect rather than silently scaling it with fractional
  arithmetic.
- Salary is due once per completed hourly economy period. Available company cash is paid
  through the balanced expense service; any uncovered amount becomes company debt. This uses
  the same non-overdraft rule as operating losses.
- Local AI executes at most one decision per profile and period. It calls player-facing
  company application services and records validation failures as skipped decisions. Its
  deterministic seed is not a permission to mutate balances or company metrics directly.
- Local process locks cover SQLite market refresh, payroll and AI execution. PostgreSQL adds
  city/world row locks and unique cycle/period constraints for cross-process serialization.

## 2026-07-19 — RUN 2 Railway release

- The user explicitly authorized the GitHub repository and named Railway project/service/environment as the release target.
- The Railway trial topology uses one supervised SHADOWGRID image for the embedded React SPA, FastAPI and ARQ worker, plus dedicated managed PostgreSQL and Redis services. Docker Compose continues to run API and worker separately.
- A dedicated `ShadowgridPostgres` database was created instead of modifying the unrelated existing EngagementOS database and its incompatible Alembic history.
- `shadowgrid.predeploy` runs Alembic and the idempotent world/admin bootstrap in one Python release process because Railway accepts one pre-deploy command.
- The initial admin password is generated into ignored `.local/production-admin.env`, used once to create and verify the account, then removed from Railway variables. Existing accounts are never silently password-reset on later deploys.
- SMTP username/password, STARTTLS and implicit TLS are supported, but no mail-provider credential is invented. Public email delivery remains an explicit provider configuration item.

## 2026-07-19 — RUN 1 scope

- The repository was uninitialized, therefore the mandatory phase detector selected **RUN 1 – LOCAL FINAL**.
- `ALLOW_EXTERNAL_DEPLOY=true` was treated only as a gate; the external deployment was not executed until local verification and explicit RUN 2 authorization were both present.
- The two “Projekt Netzwerke” PDFs are byte-different exports but have identical extracted text. Both were reviewed; neither contains additional requirements.
- Where the broad product vision and the explicit Season 0 MVP differ, the Master Goal's MVP floor is authoritative: eight districts, four configurable starter archetypes, five businesses, six facilities, eight specialist roles, five core operation categories and twelve world events.

## Architecture

- Monorepo: pnpm workspaces for React/Expo/shared TypeScript packages and a Python FastAPI service.
- API: FastAPI, Pydantic, SQLAlchemy and Alembic. PostgreSQL is the production/local-Compose database; SQLite is supported only for fast isolated tests.
- Worker: ARQ with Redis. Every scheduled task is idempotent and guarded against concurrent execution.
- Web: React, TypeScript, Vite, React Router, TanStack Query, Zustand (UI state only), Zod, Tailwind-compatible design tokens and accessible SVG/network alternatives.
- Mobile: Expo Router, React Native, TanStack Query and SecureStore; it consumes the generated shared API client.
- Server authority: balances, operation results, influence, investigation pressure, rankings and timers are persisted and resolved only by the API/worker.
- Integrity: all resource changes use an append-only ledger, idempotency keys and database transactions. Corrections are compensating entries.
- Time: UTC is stored and transmitted. Clients localize presentation only.
- Authentication: Argon2id passwords, short access tokens, rotating hashed refresh tokens, optional TOTP, explicit authorization dependencies and rate limiting.
- Localization: English is canonical, German is maintained, all configured locales fall back to English; `en-XA` and `ar-XB` exercise expansion and RTL.
- Safety: all organizations, cities and people are fictional. Covert and conflict operations are abstract categories and never provide actionable real-world criminal instructions.

## Version policy

- Runtime baselines are pinned to the locally verified Node 22.16.0 and a compatible Python 3.13 container line. Package-manager lockfiles are authoritative and production images use immutable version tags rather than `latest`.
- Dependencies are installed project-locally; missing system-wide Docker/Java/Android tools are reported by `scripts/check-environment.ps1` and are never installed with elevation automatically.

## Concurrency and dependency hardening

- Lazy operation resolution combines database row locks with an in-process serialization guard for SQLite/local two-device requests; the ARQ production worker uses locked, skip-locked selection.
- Organization role changes are director/permission controlled, protect the director role and create audit entries.
- Security overrides pin patched Vite, PostCSS and UUID versions until their Expo parents advance; React Router is pinned to its patched release. The final low-severity audit gate reports no known vulnerability.
- Root production builds are deliberately serialized so Metro and Vite do not exhaust constrained developer machines.

## 2026-07-28 — Realtime is a scoped reconciliation adapter

- The existing authenticated FastAPI WebSocket remains the realtime transport. Adding
  Socket.IO solely to match the roadmap's example stack would create a parallel application
  framework without improving the required delivery semantics.
- World, player, city and active-cartel audiences are derived from the authenticated
  profile. The client supplies no arbitrary room identifier, and both WebSocket and REST
  feeds use the same database audience predicate.
- Protocol version 1 persists every event before delivery. Event names and canonical
  payload identifiers are validated, payloads are bounded, event rows are immutable and
  optional world-scoped deduplication keys make retries safe.
- WebSockets only invalidate TanStack Query data. REST and the database remain
  authoritative, while a per-world durable cursor allows reconnecting devices to reconcile
  missed events without accepting socket-only ownership or financial state.
- Notification content is immutable. Read-one and read-all only set `read_at`, are
  idempotent and never expose another user's notification or event cursor.

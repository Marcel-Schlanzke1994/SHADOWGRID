# SHADOWGRID global localization implementation

Status: technical foundation verified; linguistic release blocked by external human review

This document maps `docs/SHADOWGRID Global Localization Masterplan.pdf` to the repository.
The architecture, current source catalogues and automated evidence supersede the PDF's
historic count of 777 strings: after the Engagement implementation and explicit game-value
labels, the canonical catalogue contains 1,279 keys.

## Implemented contract

- `packages/i18n/locales/manifest.json` defines the exact 36 primary BCP 47 packages,
  eleven additional regional overlays, seven production RTL locales, two pseudo-locales,
  twelve content domains and a zero-fallback release policy.
- Every primary package has identical domain/key structure, a review record, coverage
  record and 23-term economy/gameplay glossary. Central context metadata records source,
  route, audience, tone, variables, length budget and sensitivity for every key.
- ICU syntax and placeholder parity are parsed for all 46,044 localized message entries.
  Empty values, unknown/missing/duplicate keys, unsafe values, invalid BCP 47 tags and
  visible hardcoded Web/Mobile JSX text fail `pnpm i18n:validate`.
- Runtime fallback is disabled. Only approved packages are compiled into runtime resources;
  local development retains English, German and the two pseudo-locales. Draft selections
  fail rather than silently showing English. The production Vite build injects an explicit
  compile-time flag, and a preview-level Playwright regression test proves that a persisted
  internal or pseudo locale is rejected by the built application.
- Web and Mobile share CLDR-backed number, EUR, percentage, relative-time and
  Europe/Berlin date/time formatting. Seven production packages and `ar-XB` activate RTL;
  mobile persists the native reading direction and reports when one restart is required.
- Account e-mails use the same domain catalogue, preserve `{link}`, and reject unapproved
  locales. The production container includes the locale packages.
- API errors and form validation are presented through localized client messages instead
  of exposing server English.
- `apps/web/e2e/localization-release.capture.ts` creates the required 36-locale matrix for
  small/large mobile, tablet, desktop, light and dark modes; it also checks direction,
  horizontal overflow and serious/critical accessibility findings.
- PR validation runs the technical gate. Tag publishing and `pnpm release:final-run` also
  run `pnpm i18n:release`, which cannot be bypassed by machine-generated approvals.

## Current truthful status

| Package group             | Current content                                              | Release status                                                                                                                       |
| ------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| English                   | canonical source, runtime and accessibility tested           | catalogue approved; glossary examples, shared context, screenshot and full non-game scope evidence still required by the global gate |
| German                    | complete translated catalogue and existing store/e-mail copy | `human_translated`; independent native and in-game review pending                                                                    |
| Other 34 primary packages | full key/context/glossary scaffolds containing source text   | `not_started`; not selectable and detected as source clones by the release gate                                                      |
| Regional overlays         | empty versioned overlays                                     | internal scaffold; review required when regional wording differs                                                                     |
| `en-XA`, `ar-XB`          | generated from canonical English                             | internal layout/RTL testing only                                                                                                     |

## Commands

```powershell
pnpm i18n:bootstrap    # synchronize new keys without overwriting reviewed catalogues
pnpm i18n:validate     # technical parity, ICU, context, glossary, RTL and source scan
pnpm i18n:report       # show the truthful workflow state of every package
pnpm i18n:screenshots  # only after all catalogues/accessibility records are approved
pnpm i18n:release      # mandatory public global-release gate
pnpm --filter @shadowgrid/web test:e2e:production-i18n # verify built-locale isolation
```

## External completion boundary

The repository cannot ethically manufacture professional translators, independent native
reviewers, culture-specific editorial judgment, legal approval, store/support ownership or
physical Android/iOS screen-reader evidence. Those approvals must be added to each
`review.json` and `coverage.json` with real evidence paths. Until then the global release is
correctly blocked; changing statuses without the named work is a release-policy violation.

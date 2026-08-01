# Translation quality contract

Last updated: 2026-08-01

English is the canonical source catalogue. The current 1,279-key German catalogue is
translated but must still receive independent native review, linguistic in-game QA and
release-owner approval under the new global contract. The other 34 launch packages are
complete technical source scaffolds with status `not_started`; they are neither described
nor exposed as translations.

No public locale uses an English or German fallback. `fallbackLng` is disabled, the locale
selector contains only internally available or fully approved packages, and account e-mail
creation rejects a locale without approved e-mail copy. Machine output may only enter a
package with status `machine_draft` and cannot pass the release gate.

`en-XA` expands messages without changing ICU variables. `ar-XB` exercises right-to-left
layout. Both are internal test locales and never count toward the 36 production packages.

Every locale must progress through:

1. `machine_draft` after an actual automated translation proposal;
2. `human_translated` after the lead translator edits every affected key and glossary term;
3. `native_reviewed` after an independent native reviewer signs the catalogue;
4. `in_game_approved` after linguistic QA, accessibility evidence and release-owner approval.

The lead translator, native reviewer, linguistic QA reviewer, domain reviewer,
localization owner and release owner must be separately identified in each locale's
`review.json`. The global gate refuses incomplete or duplicate role assignments, missing
evidence, source clones and incomplete game/e-mail/store/support/legal coverage.

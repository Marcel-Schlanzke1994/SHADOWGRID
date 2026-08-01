# String freeze and linguistic QA

Before a release candidate, the localization owner records the UTC freeze time and source
catalogue commit. After the freeze, a source change is permitted only when all 36 packages
receive the same key and ICU variables, affected reviews are reopened, screenshots are
regenerated and the release owner approves the exception.

For each locale, the lead translator completes the catalogue and glossary. A different
native reviewer checks meaning, grammar, tone, terminology, cultural suitability and every
variable. Linguistic QA then tests the running Web, Android and iOS surfaces, including
loading/empty/error/success states, dialogs, story chains, notifications, e-mails and
accessibility labels. Financial, security, privacy, moderation, irreversible and legal text
also requires its domain owner.

The screenshot matrix must contain 216 captures: 36 locales across small mobile, large
mobile, tablet and desktop with both light and dark coverage. Seven RTL locales additionally
require human checks for mirrored navigation, tables, breadcrumbs, progress, directional
icons and Unicode isolation of user-provided names and monetary values. Logos, playback
controls, mathematical operators and neutral symbols remain unmirrored.

Evidence paths belong in `review.json`; game, e-mail, store, support and legal completion
belongs in `coverage.json`. `in_game_approved` is valid only after both independent language
stages, accessibility review and the final release-owner signature.

# Translation quality

Last updated: 2026-07-19

## Fully reviewed project catalogs

- English (`en`) — canonical source.
- German (`de`) — manually maintained for all current interface keys.

## Pseudo-locales

- `en-XA` — generated expansion stress test.
- `ar-XB` — generated right-to-left stress test.

## Technical fallback locales

French, Spanish, Italian, Brazilian and European Portuguese, Dutch, Polish, Czech, Slovak, Hungarian, Romanian, Bulgarian, Greek, Turkish, Russian, Ukrainian, Arabic, Hebrew, Persian, Urdu, Hindi, Bengali, Tamil, Telugu, Thai, Vietnamese, Indonesian, Malay, Simplified and Traditional Chinese, Japanese, Korean, Swedish, Norwegian, Danish, Finnish, Estonian, Latvian, Lithuanian, Slovenian, Croatian, Serbian, Swahili and Afrikaans are configured with Unicode/CLDR-aware locale selection and safe English fallback.

They are **not** described as translated or human-reviewed. The provider-independent adapter preserves existing keys, ICU parameters and fallback behavior; translation credentials are never stored in the repository.

## Known issues

- Non-English/non-German locales display canonical English until a reviewed catalog is supplied.
- Store metadata translations require a separate human-language review before submission.

# Batch 06 — München premium city package verification

## Result

The fourth premium city package is approved and runtime-integrated. It contains
eight coordinated, text-free assets:

- 21:9 day and night heroes,
- 16:9 day and night desktop heroes,
- separately composed 9:16 day and night mobile heroes,
- one separately composed and revised 1:1 city card,
- one deterministic transparent skyline silhouette.

The package evokes a prosperous southern metropolis through a landscaped urban
river, high-quality public space, pale-stone neighborhoods, restrained research
and technology offices, and subtle low foothill atmosphere. It does not
reproduce a real Isar viewpoint, corporate campus, landmark, church silhouette,
known photograph, street plan, or operational layout.

## Card review correction

The first square recomposition was held back before ingestion. A detailed
wet-stone terrace, planter, and tree entered the requested lower label-safe
band.

The accepted revision:

- removes detailed terrace and landscape geometry below the 76% height line,
- extends calm dark river water across the complete lower 24%,
- keeps reflections subtle and low-contrast,
- preserves the river, original bridge, park, pale-stone/technology district,
  and subtle foothills above the label band.

Only the corrected square image was added to the production asset store and
runtime.

## Responsive composition

The desktop, mobile, and square images are genuine recompositions:

- ultra-wide: dark low-detail left 38% for localized interface content,
- desktop: dark low-detail left 32% with additional wet-stone terrace and
  river-edge depth,
- mobile: calm upper 32%, central river-and-city decision area, and quiet lower
  18% for one primary action,
- square card: centered river, original bridge, park, and mixed district with
  the complete lower 24% reserved as calm dark water for external localized
  labels and status.

The Germany page renders Köln, Hamburg, Berlin, and München from one
data-driven package list. Each city exposes six responsive AVIF sources for
mobile, desktop, ultra-wide, day, and night conditions, plus PNG fallbacks, a
square card, and a transparent silhouette.

## Quality

The seven raster assets passed individual visual review:

| Asset | Mean review score | Lowest criterion | Safety |
| --- | ---: | ---: | ---: |
| Ultra-wide day | 98.1 | 92 | 100 |
| Ultra-wide night | 98.1 | 92 | 100 |
| Desktop day | 98.3 | 94 | 100 |
| Desktop night | 98.3 | 94 | 100 |
| Mobile day | 99.0 | 97 | 100 |
| Mobile night | 98.9 | 96 | 100 |
| Square card | 98.9 | 97 | 100 |

The silhouette is generated deterministically as a safe, self-contained SVG
with transparent background, original skyline geometry, and no embedded text,
scripts, external references, or real landmarks.

## Runtime and accessibility

- Contact sheet: `assets/reports/contact-sheets/premium-cities.png`
- Runtime directory: `apps/web/public/assets/cities/`
- In-game preview: `/germany`, “Premium city packages”
- Package articles: 4
- Responsive sources: 24
- Visible fallback/card/silhouette images: 12
- Localized catalogs: complete English and German parity
- Accessible equivalents: localized alt text and explanatory captions
- Gameplay authority: no invented ownership, score, balance, or city state
- Performance behavior: off-screen packages retain native lazy loading

The isolated browser suite intentionally does not start the API service.
Profile-proxy connection refusals are therefore expected diagnostic noise and
do not affect the local asset, accessibility, keyboard, or overflow assertions.

## Verification evidence

- Asset pipeline tests: 5 passed
- Asset manifest validation: passed
- Asset integration validation: passed
- Runtime synchronization: 83 assets and 702 files
- Web formatting: passed
- Web lint: passed
- Web typecheck: passed
- Web component tests: 9 passed
- Web production build: passed
- Germany page browser tests: 2 passed on Desktop Chrome and Pixel 7
- Automated accessibility: no serious or critical Axe findings
- English/German localization: 331 canonical keys with complete parity
- Recorded generation spend: €0.0000

Manifest state after the München package: 98 approved, 798 pending, 0 review
required, 0 rejected, and 0 failed.

# Batch 06 — Stuttgart premium city package verification

## Result

The seventh premium city package is approved and runtime-integrated. It
contains eight coordinated, text-free assets:

- 21:9 day and night heroes,
- 16:9 day and night desktop heroes,
- separately composed and revised 9:16 day and night mobile heroes,
- one separately composed 1:1 city card,
- one deterministic transparent skyline silhouette.

The documented data-driven fictional city profile combines a green urban
basin, wooded slopes, layered hillside neighborhoods, pale-stone and restrained
glass research/services districts, planted terraces, and a linear rainwater
garden. It evokes engineering, research, advanced services, education, and
culture without reproducing a real Stuttgart landmark, automobile brand or
product, factory, corporate campus, test track, rail or road plan, industrial
process, authority, or photograph.

## Review corrections

### Ultra-wide day hero

The first generation was held back before ingestion because bright water and
building detail entered the left overlay zone, while an isolated narrow distant
tower could create a Stuttgart landmark association.

The accepted revision:

- extends shadowed tree canopy, foliage, atmospheric slope, and wet terrace
  across the full left 38%,
- moves the rainwater garden and first pale building center-right,
- replaces the isolated tower with continuous wooded ridge and neutral
  flat-roofed hillside development,
- retains the green basin, planted terraces, and research/services identity.

### Mobile day hero

The first portrait recomposition was held back because dense hillside
residences entered the upper 32% and competed with localized title content.

The accepted revision extends layered cloud and soft basin haze downward. The
first readable wooded ridge and hillside neighborhood now begins below the
title-safe zone, while the middle research/rainwater-garden decision and the
lower wet-terrace/foliage control zone remain intact.

Only the corrected ultra-wide-day and mobile-day images were added to the
production asset store and runtime.

## Responsive composition

The desktop, mobile, and square images are genuine recompositions:

- ultra-wide: dark tree, foliage, slope, and terrace across the left 38%,
- desktop: calm dark left 32% with the rainwater garden, pale research district,
  and layered wooded basin concentrated center-right,
- mobile: calm upper 32%, one central research/rainwater-garden decision, and
  quiet lower 18% wet terrace and foliage for one primary action,
- square card: basin, hillside neighborhoods, rainwater garden, and pale
  research district above a complete lower 24% calm dark terrace label band.

The Germany page renders Köln, Hamburg, Berlin, München, Frankfurt, Düsseldorf,
and Stuttgart from one data-driven package list. Each city exposes six
responsive AVIF sources for mobile, desktop, ultra-wide, day, and night
conditions, plus PNG fallbacks, a square card, and a transparent silhouette.

## Quality

The seven raster assets passed individual visual review:

| Asset | Mean review score | Lowest criterion | Safety |
| --- | ---: | ---: | ---: |
| Ultra-wide day | 98.4 | 91 | 100 |
| Ultra-wide night | 98.4 | 91 | 100 |
| Desktop day | 98.7 | 94 | 100 |
| Desktop night | 98.7 | 94 | 100 |
| Mobile day | 99.3 | 97 | 100 |
| Mobile night | 99.3 | 97 | 100 |
| Square card | 99.3 | 97 | 100 |

The silhouette is generated deterministically as a safe, self-contained SVG
with transparent background, original skyline geometry, and no embedded text,
scripts, external references, named tower, automobile association, or real
landmark.

## Runtime and accessibility

- Contact sheet: `assets/reports/contact-sheets/premium-cities.png`
- Runtime directory: `apps/web/public/assets/cities/`
- In-game preview: `/germany`, “Premium city packages”
- Package articles: 7
- Responsive sources: 42
- Visible fallback/card/silhouette images: 21
- Localized catalogs: complete English and German parity
- Accessible equivalents: localized alt text and explanatory captions
- Gameplay authority: no invented ownership, score, balance, or city state
- Performance behavior: off-screen packages retain native lazy loading

## Verification evidence

- Asset pipeline tests: 5 passed
- Asset manifest validation: passed
- Asset integration validation: passed
- Runtime synchronization: 107 assets and 1,020 files
- Web formatting: passed
- Web lint: passed
- Web typecheck: passed
- Web component tests: 9 passed with 99.18% statement coverage
- Web production build: passed
- Germany page browser tests: 2 passed on Desktop Chrome and Pixel 7
- Automated accessibility: no serious or critical Axe findings
- English/German localization: 343 canonical keys with complete parity
- Recorded generation spend: €0.0000

Manifest state after the Stuttgart package: 122 approved, 774 pending, 0 review
required, 0 rejected, and 0 failed.

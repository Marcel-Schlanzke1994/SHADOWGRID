# Batch 06 — Hamburg premium city package verification

## Result

The second premium city package is approved and runtime-integrated. It contains
eight coordinated, text-free assets:

- 21:9 day and night heroes,
- 16:9 day and night desktop heroes,
- separately composed 9:16 day and night mobile heroes,
- one separately composed and revised 1:1 city card,
- one deterministic transparent skyline silhouette.

The package evokes a major northern maritime metropolis through layered
waterways, original brick waterfront architecture, trade, media, and civic
life. It does not reproduce a real port plan, terminal, shipping-company
livery, infrastructure identifier, landmark, known photograph, or operational
route.

## Card review correction

The first square recomposition was held back before ingestion. Two foreground
vessels and a bright lower-right office/quay frontage made the requested bottom
label area too detailed.

The accepted revision:

- removes both foreground vessels,
- removes the bright lower-right frontage from the label band,
- replaces the complete lower 24% with calm dark open water,
- keeps bridge and city geometry above the label-safe area,
- preserves the centered fictional brick-waterfront anchor.

Only the corrected square image was added to the production asset store and
runtime.

## Responsive composition

The desktop, mobile, and square images are genuine recompositions:

- ultra-wide: dark low-detail left 38% for localized interface content,
- desktop: dark low-detail left 32% with additional lower-right quay depth,
- mobile: calm upper 32%, central city-and-water decision area, and quiet lower
  18% for one primary action,
- square card: centered water, brick district, and bridge with the full lower
  24% reserved for external localized labels and status.

The Germany page renders Köln and Hamburg from one data-driven package list.
Each city exposes six responsive AVIF sources for mobile, desktop, ultra-wide,
day, and night conditions, plus PNG fallbacks, a square card, and a transparent
silhouette.

## Quality

The seven raster assets passed individual visual review:

| Asset | Mean review score | Lowest criterion | Safety |
| --- | ---: | ---: | ---: |
| Ultra-wide day | 97.8 | 92 | 100 |
| Ultra-wide night | 97.9 | 92 | 100 |
| Desktop day | 98.0 | 94 | 100 |
| Desktop night | 98.1 | 94 | 100 |
| Mobile day | 98.7 | 96 | 100 |
| Mobile night | 98.7 | 95 | 100 |
| Square card | 98.6 | 96 | 100 |

The silhouette is generated deterministically as a safe, self-contained SVG
with transparent background, original skyline geometry, and no embedded text,
scripts, external references, or real landmarks.

## Runtime and accessibility

- Contact sheet: `assets/reports/contact-sheets/premium-cities.png`
- Runtime directory: `apps/web/public/assets/cities/`
- In-game preview: `/germany`, “Premium city packages”
- Package articles: 2
- Responsive sources: 12
- Visible fallback/card/silhouette images: 6
- Localized catalogs: complete English and German parity
- Accessible equivalents: localized alt text and explanatory captions
- Gameplay authority: no invented ownership, score, balance, or city state

## Verification evidence

- Asset pipeline tests: 5 passed
- Asset manifest validation: passed
- Asset integration validation: passed
- Runtime synchronization: 67 assets and 490 files
- Web formatting: passed
- Web lint: passed
- Web typecheck: passed
- Web component tests: 9 passed
- Web production build: passed
- Germany page browser tests: 2 passed on Desktop Chrome and Pixel 7
- Automated accessibility: no serious or critical Axe findings
- English/German localization: 323 canonical keys with complete parity
- Recorded generation spend: €0.0000

Manifest state after the Hamburg package: 82 approved, 814 pending, 0 review
required, 0 rejected, and 0 failed.

# Batch 06 — Frankfurt am Main premium city package verification

## Result

The fifth premium city package is approved and runtime-integrated. It contains
eight coordinated, text-free assets:

- 21:9 day and night heroes,
- 16:9 day and night desktop heroes,
- separately composed 9:16 day and night mobile heroes,
- one separately composed and revised 1:1 city card,
- one deterministic transparent skyline silhouette.

The package evokes a finance and services metropolis through a broad fictional
river, compact original glass-and-stone tower cluster, lower historic-influenced
stone district, trade, data services, and public riverfront. It does not
reproduce the real Frankfurt skyline, a named tower, financial institution,
bank mark, exchange symbol, trade-fair structure, bridge, street/rail plan, or
known photograph.

## Review corrections

### Night hero

The first ultra-wide night conversion was held back before ingestion because a
bright white square near a tower crown could read as a logo or display, while
several bright facade bands were too regular.

The accepted revision:

- replaces the square with ordinary dark glass and restrained office windows,
- converts the brightest bands to irregular warm-neutral office lighting,
- keeps tower crowns unbranded,
- preserves only tiny plausible aviation safety points,
- retains river, bridge, tower geometry, lower district, and UI safe area.

### Square card

The first square recomposition was held back because an isolated pointed church
spire on the far-right skyline could create a real cathedral association.

The accepted revision replaces it with modest neutral original stone and glass
blocks. The complete lower 24% remains calm dark river water for external
localized labels, badges, and one action.

Only the corrected night and card images were added to the production asset
store and runtime.

## Responsive composition

The desktop, mobile, and square images are genuine recompositions:

- ultra-wide: dark low-detail left 38% for localized interface content,
- desktop: dark low-detail left 32% with additional wet-stone terrace, steps,
  trees, and riverfront depth,
- mobile: calm upper 32%, central tower/stone-district decision area, and quiet
  lower 18% for one primary action,
- square card: centered river, bridge, compact tower cluster, and lower stone
  district with the complete lower 24% reserved as calm dark water.

The Germany page renders Köln, Hamburg, Berlin, München, and Frankfurt from one
data-driven package list. Each city exposes six responsive AVIF sources for
mobile, desktop, ultra-wide, day, and night conditions, plus PNG fallbacks, a
square card, and a transparent silhouette.

## Quality

The seven raster assets passed individual visual review:

| Asset | Mean review score | Lowest criterion | Safety |
| --- | ---: | ---: | ---: |
| Ultra-wide day | 98.1 | 92 | 100 |
| Ultra-wide night | 98.2 | 92 | 100 |
| Desktop day | 98.4 | 94 | 100 |
| Desktop night | 98.4 | 94 | 100 |
| Mobile day | 99.0 | 96 | 100 |
| Mobile night | 99.0 | 96 | 100 |
| Square card | 99.0 | 97 | 100 |

The silhouette is generated deterministically as a safe, self-contained SVG
with transparent background, original skyline geometry, and no embedded text,
scripts, external references, named tower, or real landmark.

## Runtime and accessibility

- Contact sheet: `assets/reports/contact-sheets/premium-cities.png`
- Runtime directory: `apps/web/public/assets/cities/`
- In-game preview: `/germany`, “Premium city packages”
- Package articles: 5
- Responsive sources: 30
- Visible fallback/card/silhouette images: 15
- Localized catalogs: complete English and German parity
- Accessible equivalents: localized alt text and explanatory captions
- Gameplay authority: no invented ownership, score, balance, or city state
- Performance behavior: off-screen packages retain native lazy loading

## Verification evidence

- Asset pipeline tests: 5 passed
- Asset manifest validation: passed
- Asset integration validation: passed
- Runtime synchronization: 91 assets and 808 files
- Web formatting: passed
- Web lint: passed
- Web typecheck: passed
- Web component tests: 9 passed
- Web production build: passed
- Germany page browser tests: 2 passed on Desktop Chrome and Pixel 7
- Automated accessibility: no serious or critical Axe findings
- English/German localization: 335 canonical keys with complete parity
- Recorded generation spend: €0.0000

Manifest state after the Frankfurt package: 106 approved, 790 pending, 0 review
required, 0 rejected, and 0 failed.

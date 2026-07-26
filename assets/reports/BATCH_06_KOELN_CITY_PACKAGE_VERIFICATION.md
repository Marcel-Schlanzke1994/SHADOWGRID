# Batch 06 — Köln premium city package verification

## Result

The first premium city package is approved and runtime-integrated. It contains
eight coordinated, text-free assets:

- 21:9 day and night heroes,
- 16:9 day and night desktop heroes,
- separately composed 9:16 day and night mobile heroes,
- one separately composed 1:1 city card,
- one deterministic transparent skyline silhouette.

The package evokes a large contemporary Rhine metropolis through river scale,
urban density, trade, media, culture, and logistics. It does not reproduce a
real landmark, coat of arms, company brand, authority mark, known photograph,
or operational wrongdoing.

## Review correction

The first ultra-wide daytime attempt was rejected before ingestion. Its
dominant twin-spired cathedral and multi-arch railway bridge too closely evoked
a recognizable Cologne landmark combination.

The accepted revision replaced both elements with:

- a fictional low- and mid-rise civic district,
- a modest and varied historic roofline without monumental twin spires,
- an original low-profile asymmetric truss bridge,
- a generic distant cable-stayed bridge,
- a reworked viewpoint that cannot be matched to a known Cologne photograph.

All later variants derive from the accepted fictional city family. The
rejected source was not added to the production asset store or runtime.

## Responsive composition

The desktop, mobile, and square images are genuine recompositions rather than
simple center crops:

- ultra-wide: dark low-detail left 38% for localized interface content,
- desktop: dark low-detail left 32% with additional lower-right riverbank depth,
- mobile: calm upper 32%, central decision area, and quiet lower 18% for one
  primary action,
- square card: centered river-and-bridge anchor and darker lower 24% for
  external localized labels and status.

The Germany page exposes the package in an expandable localized preview.
Responsive AVIF sources select mobile, desktop, or ultra-wide compositions and
their coordinated dark-mode counterparts. PNG fallbacks and the transparent
silhouette remain available.

## Quality

The seven raster assets passed individual visual review:

| Asset            | Mean review score | Lowest criterion | Safety |
| ---------------- | ----------------: | ---------------: | -----: |
| Ultra-wide day   |              96.9 |               91 |    100 |
| Ultra-wide night |              97.3 |               92 |    100 |
| Desktop day      |              97.8 |               94 |    100 |
| Desktop night    |              97.8 |               93 |    100 |
| Mobile day       |              98.4 |               95 |    100 |
| Mobile night     |              98.4 |               94 |    100 |
| Square card      |              98.4 |               95 |    100 |

The silhouette is generated deterministically as a safe, self-contained SVG
with transparent background, original skyline geometry, and no embedded text,
scripts, external references, or real landmarks.

## Runtime and accessibility

- Contact sheet: `assets/reports/contact-sheets/premium-cities.png`
- Runtime directory: `apps/web/public/assets/cities/`
- In-game preview: `/germany`, “Premium city packages”
- Localized catalogs: complete English and German parity
- Responsive formats: AVIF, WebP, and PNG fallbacks
- Mobile structure: one narrow-column composition below 720 px
- Accessible equivalents: localized alt text and explanatory captions
- Gameplay authority: no invented ownership, score, balance, or city state

## Verification evidence

- Asset pipeline tests: 5 passed
- Asset manifest validation: passed
- Asset integration validation: passed
- Runtime synchronization: 59 assets and 384 files
- Web formatting: passed
- Web lint: passed
- Web typecheck: passed
- Web component tests: 9 passed
- Web production build: passed
- Germany page browser tests: 2 passed on Desktop Chrome and Pixel 7
- Automated accessibility: no serious or critical Axe findings
- English/German localization: 319 canonical keys with complete parity
- Recorded generation spend: €0.0000

Manifest state after the Köln package: 74 approved, 822 pending, 0 review
required, 0 rejected, and 0 failed.

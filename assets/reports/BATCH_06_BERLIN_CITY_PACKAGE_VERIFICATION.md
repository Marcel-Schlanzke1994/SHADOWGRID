# Batch 06 — Berlin premium city package verification

## Result

The third premium city package is approved and runtime-integrated. It contains
eight coordinated, text-free assets:

- 21:9 day and night heroes,
- 16:9 day and night desktop heroes,
- separately composed 9:16 day and night mobile heroes,
- one separately composed 1:1 city card,
- one deterministic transparent skyline silhouette.

The package evokes a diverse capital through an original tree-lined canal,
mixed historic, postwar, adaptive-reuse, and contemporary architecture,
culture, research, media, technology, and civic life. It does not reproduce a
real government site, street or transit plan, authority building, landmark,
monument, known photograph, or operational surveillance layout.

## Responsive composition

The desktop, mobile, and square images are genuine recompositions:

- ultra-wide: dark low-detail left 38% for localized interface content,
- desktop: dark low-detail left 32% with additional canal-edge and public-realm
  depth,
- mobile: calm upper 32%, central canal-and-city decision area, and quiet lower
  18% for one primary action,
- square card: centered canal, original bridge, trees, and mixed architecture
  with the full lower 24% reserved as calm dark canal water for external
  localized labels and status.

The Germany page renders Köln, Hamburg, and Berlin from one data-driven package
list. Each city exposes six responsive AVIF sources for mobile, desktop,
ultra-wide, day, and night conditions, plus PNG fallbacks, a square card, and a
transparent silhouette.

## Quality

The seven raster assets passed individual visual review:

| Asset | Mean review score | Lowest criterion | Safety |
| --- | ---: | ---: | ---: |
| Ultra-wide day | 97.9 | 92 | 100 |
| Ultra-wide night | 97.9 | 92 | 100 |
| Desktop day | 98.1 | 94 | 100 |
| Desktop night | 98.1 | 94 | 100 |
| Mobile day | 98.8 | 96 | 100 |
| Mobile night | 98.7 | 95 | 100 |
| Square card | 98.7 | 96 | 100 |

The silhouette is generated deterministically as a safe, self-contained SVG
with transparent background, original skyline geometry, and no embedded text,
scripts, external references, or real landmarks.

## Runtime and accessibility

- Contact sheet: `assets/reports/contact-sheets/premium-cities.png`
- Runtime directory: `apps/web/public/assets/cities/`
- In-game preview: `/germany`, “Premium city packages”
- Package articles: 3
- Responsive sources: 18
- Visible fallback/card/silhouette images: 9
- Localized catalogs: complete English and German parity
- Accessible equivalents: localized alt text and explanatory captions
- Gameplay authority: no invented ownership, score, balance, or city state
- Performance behavior: off-screen packages retain native lazy loading

## Browser-test correction

The first three-package mobile test tried to assert all lazy images before the
off-screen packages entered the viewport. Desktop passed, while Mobile timed
out with unloaded off-screen images.

The test now scrolls each package into view and verifies its three images
individually. Productive lazy loading remains enabled. The corrected test passes
on both Desktop Chrome and Pixel 7.

## Verification evidence

- Asset pipeline tests: 5 passed
- Asset manifest validation: passed
- Asset integration validation: passed
- Runtime synchronization: 75 assets and 596 files
- Web formatting: passed
- Web lint: passed
- Web typecheck: passed
- Web component tests: 9 passed
- Web production build: passed
- Germany page browser tests: 2 passed on Desktop Chrome and Pixel 7
- Automated accessibility: no serious or critical Axe findings
- English/German localization: 327 canonical keys with complete parity
- Recorded generation spend: €0.0000

Manifest state after the Berlin package: 90 approved, 806 pending, 0 review
required, 0 rejected, and 0 failed.

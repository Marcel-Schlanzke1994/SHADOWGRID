# Batch 06 — Leipzig premium city package verification

## Result

The eighth premium city package is approved and runtime-integrated. It contains
eight coordinated, text-free assets:

- 21:9 day and night heroes,
- 16:9 day and night desktop heroes,
- separately composed 9:16 day and night mobile heroes,
- one separately composed 1:1 city card,
- one deterministic transparent skyline silhouette.

The documented data-driven fictional city profile combines a flat green
floodplain, tree-lined canal, simple original low-profile bridge, pale
sandstone and warm-gray courtyard districts, restrained research buildings,
one adapted red-brown brick cultural/workshop cluster, and landscaped public
gardens. It evokes culture, publishing, research, education, trade, and
creative services without reproducing a real Leipzig institution, landmark,
church, station, trade fair, publisher, media company, industrial complex,
logistics route, authority, or photograph.

## Review correction

### Ultra-wide day hero

The first generation was held back before ingestion because the bridge, a
bright foreground tree, and high-contrast terrace detail entered the left
overlay zone. The cloud field there was too bright, the bridge looked more
ornate than intended, and tiny human silhouettes were visible.

The accepted revision:

- leaves only dark canal water, low-detail tree canopy, floodplain haze, and
  darker cloud across the full left 38%,
- moves the bridge and all bright architecture center-right,
- replaces the ornate crossing with a restrained original pale-stone and
  dark-steel span,
- removes every visible person from the bridge, paths, terrace, and gardens,
- retains the canal, courtyard, research, brick-hall, and garden identity.

Only the corrected ultra-wide-day image was added to the production asset store
and runtime.

## Responsive composition

The desktop, mobile, and square images are genuine recompositions:

- ultra-wide: dark canal, tree canopy, floodplain haze, and cloud across the
  left 38%,
- desktop: calm dark left 32% with the bridge, pale courtyard district,
  research buildings, adapted brick hall, and gardens center-right,
- mobile: calm upper 32%, one central canal/bridge/culture-quarter decision,
  and more than the lower 18% as uninterrupted dark canal water,
- square card: canal, simple bridge, pale courtyard district, brick hall, and
  gardens above a complete lower 24% calm-water label band.

The Germany page renders Köln, Hamburg, Berlin, München, Frankfurt, Düsseldorf,
Stuttgart, and Leipzig from one data-driven package list. Each city exposes six
responsive AVIF sources for mobile, desktop, ultra-wide, day, and night
conditions, plus PNG fallbacks, a square card, and a transparent silhouette.

## Quality

The seven raster assets passed individual visual review:

| Asset | Mean review score | Lowest criterion | Safety |
| --- | ---: | ---: | ---: |
| Ultra-wide day | 98.5 | 92 | 100 |
| Ultra-wide night | 98.5 | 92 | 100 |
| Desktop day | 98.7 | 94 | 100 |
| Desktop night | 98.7 | 94 | 100 |
| Mobile day | 99.3 | 97 | 100 |
| Mobile night | 99.3 | 97 | 100 |
| Square card | 99.3 | 97 | 100 |

The silhouette is generated deterministically as a safe, self-contained SVG
with transparent background, original skyline geometry, and no embedded text,
scripts, external references, station, monument, church, cultural-institution
shape, or real landmark.

## Runtime and accessibility

- Contact sheet: `assets/reports/contact-sheets/premium-cities.png`
- Runtime directory: `apps/web/public/assets/cities/`
- In-game preview: `/germany`, “Premium city packages”
- Package articles: 8
- Responsive sources: 48
- Visible fallback/card/silhouette images: 24
- Localized catalogs: complete English and German parity
- Accessible equivalents: localized alt text and explanatory captions
- Gameplay authority: no invented ownership, score, balance, or city state
- Performance behavior: off-screen packages retain native lazy loading

## Verification evidence

- Asset pipeline tests: 5 passed
- Asset manifest validation: passed
- Asset integration validation: passed
- Runtime synchronization: 115 assets and 1,126 files
- Web formatting: passed
- Web lint: passed
- Web typecheck: passed
- Web component tests: 9 passed with 99.18% statement coverage
- Web production build: passed
- Germany page browser tests: 2 passed on Desktop Chrome and Pixel 7
- Automated accessibility: no serious or critical Axe findings
- English/German localization: 347 canonical keys with complete parity
- Recorded generation spend: €0.0000

Manifest state after the Leipzig package: 130 approved, 766 pending, 0 review
required, 0 rejected, and 0 failed.

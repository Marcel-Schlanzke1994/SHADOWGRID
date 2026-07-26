# Batch 05 — Map markers and control points verification

## Result

All 19 required 24×24 SVG markers are approved:

- 8 city markers,
- 5 influence markers,
- 6 control-point markers.

Each asset is text-free, self-contained, and available in both the production
asset store and `apps/web/public/assets/markers/`.

## Visual system

The marker family uses redundant shape, frame, interior glyph, and category
color:

- city markers: gold and individually shaped by settlement or state,
- influence markers: blue circular frames with distinct interior glyphs,
- control points: off-white hexagonal frames with distinct network geometry.

The application does not rely on those colors for meaning. The authenticated
Germany page exposes an expandable marker key with a visible English or German
label beside every icon.

## Review corrections

Three issues found during contact-sheet review were fixed before final
approval:

1. External SVG images do not inherit the surrounding page's `currentColor`.
   A root category color was added so the icons remain visible on dark map
   surfaces.
2. Information and social influence initially used overly similar triangular
   node arrangements. Information now uses a distinct observation glyph while
   social influence retains the connected-person geometry.
3. The logistics control point initially contained a plus sign that could be
   mistaken for a medical symbol. It now uses a neutral transfer point with
   four directional connections.

No real coat of arms, gang mark, authority logo, extremist symbol, company
brand, weapon, route instruction, or operational wrongdoing procedure is
present.

## Runtime and accessibility

- Contact sheet: `assets/reports/contact-sheets/map-markers.png`
- Runtime directory: `apps/web/public/assets/markers/`
- In-game key: `/germany`, “Marker and control-point key”
- Touch target for each catalog row: 44 px minimum
- Accessible equivalent: localized text label adjacent to each decorative SVG
- Dynamic placement: deliberately absent until supplied by authoritative game
  data

The marker catalog does not invent city coordinates, influence values, control
ownership, or other gameplay state.

## Verification evidence

- Asset pipeline tests: 5 passed
- Unique marker hashes: 19 of 19
- Production/runtime byte equality: 19 of 19
- SVG safety checks: no script, image, text, or external `href`
- Asset manifest validation: passed
- Asset integration validation: passed
- Web component tests: 9 passed
- Germany page browser tests: 2 passed on Desktop Chrome and Pixel 7
- Automated accessibility: no serious or critical Axe findings
- English/German localization: 311 canonical keys with complete parity

Manifest state after Batch 05: 66 approved, 830 pending.

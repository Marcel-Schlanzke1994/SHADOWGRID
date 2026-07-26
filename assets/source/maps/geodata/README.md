# Licensed Germany map inputs

SHADOWGRID map geometry is derived deterministically from official BKG data.
Image generation is never used to invent geographic shapes.

## Sources

- BKG Verwaltungsgebiete 1:250 000 (VG250), data status 01.01.2025:
  https://gdz.bkg.bund.de/index.php/default/open-data/verwaltungsgebiete-1-250-000-stand-01-01-vg250-01-01.html
- BKG Digitales Landschaftsmodell 1:250 000 (DLM250), data status
  31.12.2025:
  https://gdz.bkg.bund.de/index.php/default/digitales-landschaftsmodell-1-250-000-ebenen-dlm250-ebenen.html
- License: https://www.govdata.de/dl-de/by-2-0

The build uses EPSG:25832 WFS features and stores the exact queries, feature
counts, local raw-file hashes, simplification tolerances, and output hashes in
`bkg-2025/sources.json`.

## Derivation

| Output layer          | Official source selection                                                     | Transformation                                                           |
| --------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Germany outline       | VG250 state areas with `GF=4`                                                 | Country geometry merged visually and simplified                          |
| Federal-state borders | VG250 boundary lines with `AGZ=2` and `GMK=0`                                 | Internal boundaries simplified                                           |
| Coasts and water      | VG250 coastlines with `AGZ=9`; DLM250 river surfaces; lakes of at least 1 km² | Water geometry clipped by the common German view box and simplified      |
| Major rivers          | DLM250 water surfaces and axes selected by canonical `GWK` identifiers        | Broad river surfaces combined with narrower official axes and simplified |

The major-river selection uses stable watercourse identifiers rather than a
name search or a partial width class. This preserves broad rivers represented
as surfaces and narrower rivers represented as axes without inventing
geography.

## Required public attribution

The rendered map must show both notices in visible proximity to the map:

```text
© BKG 2025 dl-de/by-2-0 (Daten verändert), Datenquellen:
https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_vg_nuts.pdf

© GeoBasis-DE / BKG 2025 dl-de/by-2-0 (Daten verändert)
```

On the web, `BKG` must link to https://www.bkg.bund.de and `dl-de/by-2-0`
must link to https://www.govdata.de/dl-de/by-2-0.

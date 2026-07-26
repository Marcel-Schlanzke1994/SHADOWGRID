# Auth UI asset verification

Date: 2026-07-25

## Scope

The responsive login and registration backgrounds were verified in the live
React application after the browser decoded the selected production image.
Each route uses a desktop 16:9 asset and a separately composed mobile 9:16
asset.

| Route | Desktop asset | Mobile asset |
| --- | --- | --- |
| `/login` | `global-login-desktop-v1` | `global-login-mobile-v1` |
| `/register` | `global-registration-desktop-v1` | `global-registration-mobile-v1` |

## Visual review

- Login desktop: approved. The centered form remains on the calm dark wall;
  the architectural depth and restrained gold light remain visible around it.
- Login mobile: approved. The native portrait composition preserves the full
  form-safe center at Pixel 7 dimensions and keeps detail at the edges.
- Registration desktop: approved. Daylight and landscaping make the route
  more welcoming while the tall form remains on the low-detail stone surface.
- Registration mobile: approved. The native portrait composition retains the
  longer registration form without covering the architectural focal edges.
- All four states preserve brand and form contrast without adding generated
  text, people, real brands, real locations, authorities, weapons, or explicit
  wrongdoing.

## Browser and accessibility checks

- Chromium desktop and Pixel 7 select the expected `currentSrc` asset.
- AVIF is preferred, WebP is available as the next fallback, and PNG remains
  the final fallback.
- The decorative pictures are hidden from the accessibility tree and have
  empty alternative text.
- The image decode, layer order, natural dimensions, and absence of horizontal
  overflow are asserted in Playwright.
- Axe reported no serious or critical violations on either route in desktop or
  mobile projects.
- The desktop 200% zoom checks have no horizontal overflow. Equivalent mobile
  checks are covered by the native Pixel 7 project and intentionally skipped
  in the desktop-only zoom test.

## Approved previews

- `assets/previews/auth-login-desktop.png`
- `assets/previews/auth-login-mobile.png`
- `assets/previews/auth-registration-desktop.png`
- `assets/previews/auth-registration-mobile.png`

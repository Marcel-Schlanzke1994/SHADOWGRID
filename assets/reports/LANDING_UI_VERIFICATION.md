# Landing UI verification

Assets:

- `global-landing-desktop-day-v1`
- `global-landing-desktop-night-v1`
- `global-landing-mobile-day-v1`
- `global-landing-mobile-night-v1`

## Browser evidence

| View | Viewport | Responsive source selected | Horizontal overflow | Axe violations |
| --- | ---: | --- | --- | ---: |
| Desktop day | 1920 × 1080 | Desktop day 1920 px AVIF | none | 0 |
| Desktop night | 1920 × 1080, dark scheme | Desktop night 1920 px AVIF | none | 0 |
| Mobile day | 320 × 800 | Mobile day 320 px AVIF | none | 0 |
| Mobile night | 320 × 800, dark scheme | Mobile night 320 px AVIF | none | 0 |
| 200% zoom | 640 × 900 with 2× page zoom | Responsive AVIF | none | 0 |

The desktop heroes occupy the calm left side while preserving the river and headquarters on the right. The 9:16 mobile assets are independent portrait compositions rather than center crops. At 320 px, the copy remains readable with stacked 44 px controls. At 200% zoom, vertical scrolling is required but no horizontal scrolling occurs.

The committed Playwright coverage verifies exact day/night and desktop/mobile `currentSrc` selection, successful image decoding, no serious or critical Axe violations, and 200% zoom reflow. Result: 5 passed, 1 deliberate mobile skip for the desktop-only zoom case.

## Preview artifacts

- `assets/previews/landing-desktop-day.png`
- `assets/previews/landing-desktop-night.png`
- `assets/previews/landing-mobile-day.png`
- `assets/previews/landing-mobile-night.png`
- `assets/previews/landing-zoom200.png`

The local preview ran without the API service, so unauthenticated refresh requests returned connection-refused proxy diagnostics. This did not affect the public route, image delivery, responsive selection, accessibility scan or layout checks.

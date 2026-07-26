# Command center UI asset verification

Date: 2026-07-25

## Assets

| Preferred scheme | Asset | Composition |
| --- | --- | --- |
| Light | `global-command-center-day-v1` | Native 16:9 |
| Dark | `global-command-center-night-v1` | Lighting edit with locked geometry |

## Visual review

- The day and night scenes retain identical architecture, camera position, and
  workstation placement; only lighting, reflections, and the fictional city
  ambience change.
- Desktop content remains readable over the low-detail left side, while the
  scene depth stays visible behind the resource cards on the right.
- The mobile single-column layout keeps headings, cards, navigation, and touch
  controls clear at Pixel 7 dimensions.
- The restrained graphite, blue, and warm-gold palette remains consistent with
  the frozen style lock.
- Neither asset contains generated text, interface elements, real geography,
  people, brands, authorities, weapons, or explicit wrongdoing.

## Runtime verification

- `/command` uses `GlobalDayNightBackdrop` and switches through
  `prefers-color-scheme` without JavaScript-controlled game state.
- Chromium desktop and Pixel 7 select
  `global-command-center-day-v1` in light mode and
  `global-command-center-night-v1` in dark mode.
- AVIF, WebP, and PNG fallback paths are present.
- Playwright asserts the selected `currentSrc`, completed image decode, natural
  dimensions, and absence of horizontal overflow.
- The command-center checks use deterministic local API mocks and do not
  depend on credentials, seeded accounts, or a running backend.
- Axe reported no serious or critical violations in desktop or mobile.
- The complete asset-only suite passed with 16 tests and 4 intentional mobile
  zoom skips.

## Approved previews

- `assets/previews/command-center-desktop-day.png`
- `assets/previews/command-center-desktop-night.png`
- `assets/previews/command-center-mobile-day.png`
- `assets/previews/command-center-mobile-night.png`

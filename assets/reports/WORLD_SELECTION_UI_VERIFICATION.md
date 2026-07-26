# World selection UI asset verification

Date: 2026-07-25

## Assets

| Viewport | Asset | Composition |
| --- | --- | --- |
| Desktop | `global-world-selection-desktop-v1` | Native 16:9 |
| Mobile | `global-world-selection-mobile-v1` | Native 9:16 |

## Visual review

- Both assets preserve a wide, low-detail central stone surface for the full
  world-selection form.
- The desktop scene keeps city depth and strategic scale at the outer edges.
- The mobile scene is a native portrait composition and is not a desktop crop.
- The blue-hour and restrained warm-gold lighting remain consistent with the
  frozen style lock.
- No generated text, interface, map, real geography, people, brands,
  authorities, weapons, or explicit wrongdoing appear in either image.

## Runtime verification

- `/worlds` uses the shared responsive `GlobalBackdrop` component.
- Chromium desktop selects `global-world-selection-desktop-v1`.
- Pixel 7 selects `global-world-selection-mobile-v1`.
- AVIF, WebP, and PNG fallback paths are present.
- Playwright asserts decode completion, natural dimensions, layer order, and
  absence of horizontal overflow.
- Axe reported no serious or critical violations.
- The 200% desktop zoom test completed without horizontal overflow.

## Approved previews

- `assets/previews/world-selection-desktop.png`
- `assets/previews/world-selection-mobile.png`

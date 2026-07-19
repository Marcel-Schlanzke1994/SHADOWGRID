# Accessibility

The target is WCAG 2.2 AA. Web provides semantic landmarks, a skip link, keyboard focus styles, reduced-motion handling, textual status in addition to color, accessible tables for map/network visualizations, responsive layouts and RTL direction. Forms use visible labels and errors; async states expose status/alert roles and request IDs.

Mobile controls use at least 48-point heights, readable 16-point body text, accessibility labels/roles and high-contrast dark tokens. Release testing must include keyboard-only web navigation, browser zoom to 200%, screen reader smoke tests, Android/iOS text scaling and pseudo-locales `en-XA`/`ar-XB`.

Automated axe checks detect common violations but do not replace manual reading order, focus, comprehension and touch-target review.

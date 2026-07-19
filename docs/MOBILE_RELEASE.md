# Mobile release

The Expo Router application shares API contracts and localization with web. Refresh tokens are stored in Expo SecureStore and access tokens remain in memory. The bundle identifiers are `game.shadowgrid.mobile` for Android and iOS.

## Required provider setup

1. Replace the placeholder EAS project ID and example associated-link domains in `app.json`.
2. Configure `EXPO_PUBLIC_API_URL` for preview/production HTTPS endpoints.
3. Create EAS credentials in the organization account; never commit keystores or signing certificates.
4. Build preview APK and production AAB/IPA with `eas build --profile preview|production`.
5. Run device checks for login/session restore, deep links, offline behavior, dark mode, text scaling, screen reader labels and 44-point touch targets.
6. Submit to internal tracks first, then staged production after backend compatibility and privacy metadata review.

The local `pnpm --filter @shadowgrid/mobile build` produces a static web export as a compilation gate; it is not a signed store artifact. Store copy and the data-safety draft live under `apps/mobile/store/`.

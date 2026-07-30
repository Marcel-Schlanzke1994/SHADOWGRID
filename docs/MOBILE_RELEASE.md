# Mobile release

The Expo Router application shares API contracts and localization with web. Refresh tokens are stored in Expo SecureStore and access tokens remain in memory. The bundle identifiers are `game.shadowgrid.mobile` for Android and iOS.

## Required provider setup

1. Link the repository to the real EAS organization with `eas init`; no placeholder
   project ID is committed.
2. Production `EXPO_PUBLIC_API_URL` is validated as
   `https://shadowgrid-production-be34.up.railway.app/api/v1`. Configure a separate HTTPS
   preview endpoint in the EAS `preview` environment before cloud builds.
3. Create EAS credentials in the organization account; never commit keystores or signing certificates.
4. Build preview APK and production AAB/IPA with `eas build --profile preview|production`.
5. Run device checks for login/session restore, the `shadowgrid://` custom scheme, offline
   behavior, dark mode, text scaling, screen reader labels and 44-point touch targets.
6. Submit to internal tracks first, then staged production after backend compatibility and privacy metadata review.

The local `pnpm --filter @shadowgrid/mobile build` produces a static web export as a compilation gate; it is not a signed store artifact. Store copy and the data-safety draft live under `apps/mobile/store/`.

`pnpm --filter @shadowgrid/mobile build:preview` additionally exports unsigned Android,
iOS and web bundles into ignored `apps/mobile/dist/preview`. Universal HTTPS links remain
disabled until a real controlled web domain and its Apple/Android association files exist;
no example domain is shipped.

See [Mobile release readiness](MOBILE_RELEASE_READINESS.md) for exact external commands and
the physical-device checklist.

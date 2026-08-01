# Mobile release readiness

## State

```text
repository_complete: true
preview_build_complete: true after the recorded unsigned Expo export
signed_build_external: true
store_submission_external: true
```

`repository_complete` means the identifiers, runtime API validation, unsigned export,
tests, store copy and engineering data-safety draft are ready. It does not imply an Apple
or Google signature, account approval, legal privacy approval or store acceptance.

## Verified repository configuration

- Android package and iOS bundle ID: `game.shadowgrid.mobile`.
- Custom deep-link scheme: `shadowgrid://`.
- Production API: HTTPS, non-local and versioned at `/api/v1`.
- Public builds reject HTTP and localhost API configuration at startup.
- Placeholder EAS project IDs and example associated-link domains are absent.
- No keystore, certificate, provisioning profile or private signing key is present.
- Refresh tokens use Expo SecureStore; access tokens remain in memory.
- Store copy exists in German and English; Data Safety remains explicitly a legal draft.
- The local unsigned preview export requires no provider credential.

## Recorded unsigned preview export

The repository-local preview export completed successfully on
`2026-07-30T01:05:57Z` with:

- 69 files and 7,853,718 bytes (7.49 MiB) in `apps/mobile/dist/preview`;
- an Android Hermes bundle of 3,029,763 bytes, SHA-256
  `6c5deb0f3f0ab406fab2367c3e5d820165f65e05298cb5bc8285ee167b3777a2`;
- an iOS Hermes bundle of 3,027,014 bytes, SHA-256
  `a3abd2618ec2e230877192900c5930953227012a1e57fcaea69922fd20ac6e37`;
- a web bundle of 1,305,643 bytes, SHA-256
  `2431489027c55948fa6ae2c48306f8a9850e09c74c2baa995d0ffcc644837703`;
- 15 statically exported routes.

`pnpm mobile:release:verify` also passed after the export. The export is deliberately
ignored by Git: the configuration and hashes are release evidence, while generated build
output is reproducible and is not committed.

## Physical device acceptance checklist

These checks require real signed/internal builds and remain `EXTERNAL-DEVICE` until recorded
by an operator:

| Check | Android phone/tablet | iPhone/iPad |
| --- | --- | --- |
| Login, 2FA and generic failures | pending | pending |
| Session restore after process kill/reboot | pending | pending |
| `shadowgrid://` deep link from outside app | pending | pending |
| Offline start, retry and recovery | pending | pending |
| Dark mode and system contrast | pending | pending |
| 200% text scaling without clipping | pending | pending |
| TalkBack/VoiceOver order and labels | pending | pending |
| Touch targets at least 44 points | pending | pending |
| Rotation/tablet layout where supported | pending | pending |
| Logout removes the SecureStore refresh token | pending | pending |

## Exact external EAS sequence

Run only from the real organization account. Do not commit credentials:

```text
npx eas-cli init
npx eas-cli env:create --environment preview --name EXPO_PUBLIC_APP_ENV --value preview --visibility plaintext
npx eas-cli env:create --environment preview --name EXPO_PUBLIC_API_URL --value https://<preview-host>/api/v1 --visibility plaintext
npx eas-cli build --profile preview --platform android
npx eas-cli build --profile preview --platform ios
```

After device acceptance, privacy review and
`FINALIZE_ALLOW_STORE_SUBMISSION=true`:

```text
npx eas-cli build --profile production --platform android
npx eas-cli build --profile production --platform ios
npx eas-cli submit --profile production --platform android
npx eas-cli submit --profile production --platform ios
```

Submit to internal testing first, then a staged rollout. EAS project creation, signing
credentials, paid developer accounts, physical-device evidence and submission are
`blocked_external`; this finalization does not fabricate any of them.

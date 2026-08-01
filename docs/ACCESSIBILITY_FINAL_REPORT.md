# SHADOWGRID accessibility final report

Date: 2026-07-29

Local web gate status: passed
Physical assistive-technology/device status: operator follow-up required

## Automated evidence

The final page matrix runs with:

```powershell
pnpm --filter @shadowgrid/web exec playwright test e2e/accessibility-matrix.spec.ts
```

Result: four passed in 7.5 minutes. The run contains 31 primary-page scans in
Chromium desktop and the Pixel 7 mobile viewport, for 62 page scans in total, plus one
interaction test per viewport. Every page has a visible `main` landmark and `h1`.
Critical and serious Axe findings: zero.

The gate also verifies the skip-link target, dialog focus, reduced-motion CSS,
left-to-right `en-XA`, right-to-left `ar-XB`, responsive navigation and localized
loading, empty, error and success primitives. The component state suite passed 12/12
with 95.74% statement coverage.

## Page matrix

| Page | Primary purpose | Desktop Axe/structure | Mobile Axe/structure | Async states |
| --- | --- | --- | --- | --- |
| `/worlds` | Select a world | passed | passed | shared contract |
| `/tutorial` | Learn core actions | passed | passed | shared contract |
| `/command` | Review current position | passed | passed | shared contract |
| `/city` | Explore Cologne districts | passed | passed | shared contract |
| `/germany` | Inspect the strategic map | passed | passed | shared contract |
| `/companies` | Found and manage companies | passed | passed | explicit |
| `/exchange` | Trade fixed-supply shares | passed | passed | explicit |
| `/facilities` | Review facilities | passed | passed | shared contract |
| `/specialists` | Hire and assign specialists | passed | passed | explicit |
| `/operations` | Plan operations | passed | passed | shared contract |
| `/network` | Review relationship network | passed | passed | shared contract |
| `/intelligence` | Run intelligence actions | passed | passed | explicit |
| `/investigation` | Review investigation pressure | passed | passed | shared contract |
| `/cartels` | Manage cartel governance | passed | passed | explicit |
| `/diplomacy` | Manage treaties | passed | passed | shared contract |
| `/pvp` | Use abstract strategic actions | passed | passed | shared contract |
| `/territories` | Review district control | passed | passed | shared contract |
| `/wars` | Review abstract conflicts | passed | passed | shared contract |
| `/alliances` | Manage alliances | passed | passed | shared contract |
| `/communications` | Read and send messages | passed | passed | shared contract |
| `/market` | Review resource markets | passed | passed | shared contract |
| `/contracts` | Tender, bid and award | passed | passed | explicit |
| `/finance` | Request and manage loans | passed | passed | explicit |
| `/bonds` | Issue and subscribe to bonds | passed | passed | explicit |
| `/real-estate` | Buy, lease and upgrade property | passed | passed | explicit |
| `/research` | Review research progression | passed | passed | shared contract |
| `/news` | Reconcile news and notifications | passed | passed | explicit |
| `/rankings` | Review season rankings and rewards | passed | passed | explicit |
| `/settings` | Manage language, sessions and privacy | passed | passed | explicit |
| `/admin` | Operate administrator controls | passed | passed | authorization error visible |
| `/moderation` | Review immutable audit activity | passed | passed | authorization error visible |

“Shared contract” means the page uses the tested `StateView` primitive. It exposes
loading as `role=status`, errors as `role=alert`, request IDs for API failures, an
actionable retry control, an explicit empty message and normal success content.
Financial flows additionally display exact costs in a modal confirmation before the
request is sent.

## Manual and assisted review checklist

| Review | Status | Evidence or required operator action |
| --- | --- | --- |
| Screenreader reading order | structure passed; physical smoke pending | Landmarks, heading order, labels, tables and accessible SVG groups pass Axe. Run NVDA/VoiceOver narration on a release device before public store submission. |
| Dialog focus | passed | Real desktop/mobile Playwright confirms initial focus remains inside both company financial dialogs on the cancel action. |
| Mobile text scaling | browser passed; native device pending | Mobile viewport, responsive reflow, 200% desktop zoom and 16-point/48-point native tokens are verified. Confirm maximum Android/iOS accessibility text size on signed builds. |
| iOS and Android touch operation | repository passed; physical devices pending | Pixel 7 viewport flows and minimum web/native targets pass. Complete TalkBack/VoiceOver touch exploration on signed AAB/IPA artifacts. |
| Economic terminology | passed | German/English catalogs have complete 777-key parity; confirmations state exact costs and server errors retain request IDs. |

The two physical-device items cannot be executed on this Windows host because no signed
provider builds or iOS/Android devices are connected. They are explicit store-readiness
operator checks, not silently claimed as completed.

## Findings resolved

1. The Cologne SVG was exposed as one image containing five focusable links. It is now
   an accessible labelled group whose district links remain independent controls.
2. The unread marker used an `aria-label` on a neutral span. The marker is now decorative
   and its meaning is provided by separate screenreader-only text.

No Axe exception, rule suppression or unresolved Critical/Serious finding remains.

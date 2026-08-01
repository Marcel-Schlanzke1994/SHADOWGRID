# SHADOWGRID Visual System

Status: implemented visual foundation for web and mobile
Visual target: premium cinematic strategy interface, not a SaaS dashboard

## Product feeling

SHADOWGRID presents the player with an executive cyber-finance war room. The
interface communicates wealth, control, intelligence and strategic pressure
through material depth and restrained light. Realism wins over decorative
sci-fi: surfaces are smoked glass, obsidian, titanium and satin gold; cyan is a
technical signal and never the dominant paint color.

## Design tokens

The cross-platform source is `packages/ui-tokens/src/index.ts`. The web runtime
maps the same system to CSS custom properties in `apps/web/src/premium.css`.

| Layer | Core tokens | Rule |
| --- | --- | --- |
| Foundation | `--bg-obsidian`, `--bg-carbon`, graphite, steel | 80–85% of every view remains dark |
| Material | `--panel-glass`, `--panel-metal` | Panels use layered gradients, edge light, blur and internal shadow |
| Prestige | `--accent-gold`, dark gold, champagne | Capital, ownership, rank, VIP and primary actions |
| Technology | `--accent-cyan`, deep cyan, ice | Active state, market data, maps, network and intelligence |
| Signals | success, warning, danger, intel | Functional meaning only; never general decoration |
| Depth | soft, deep and floating shadows | Depth follows hierarchy, not arbitrary blur |
| Shape | panel and button corner pairs | Asymmetric machined corners replace generic pills |
| Motion | fast, medium, slow, premium easing | Controlled weight; reduced-motion removes nonessential movement |

Typography separates display, UI and numeric information. Headlines use a
condensed technical stack, body copy a highly readable system sans stack and
financial values tabular monospace numerals.

## Component contract

Every interactive control provides default, hover, pressed, focus-visible,
disabled and loading states. The component layer in
`apps/web/src/components.tsx` supplies physical panel edges, status signals,
metric scan details, loading states and accessible confirmation behavior.

- Primary buttons are dark metal controls with gold edge light and tactile
  press depth. Secondary actions use cyan/steel treatment; danger actions use
  a restrained red light edge.
- Panels, cards and metrics use asymmetric frames, reflections, material noise,
  fine separators and functional accent lights.
- Forms, selects, tables, dialogs, disclosures, progress indicators, empty,
  loading and error states share the same material language.
- Charts and maps use subdued grids, luminous data strokes, glass tool regions
  and selected-state depth. The relationship graph uses bespoke gold nodes and
  cyan directional links.
- Focus remains clearly visible. Forced-colors mode falls back to native system
  colors and reduced-motion mode removes camera drift, scans and transitions.

## Screen identities

| Surface | Identity |
| --- | --- |
| Landing and authentication | Cinematic city reveal, premium entry panel and weighty CTA hierarchy |
| Command Center | Executive war room with coherent day/night environment and layered tactical metrics |
| Exchange and network | Restrained cyan terminal grid, luminous data and high-focus charts |
| Intelligence | Cold dossier system with cyan and controlled intel-purple signals |
| Cartels | Gold authority, hierarchy and strong governance modules |
| Real estate and HQ | Asset prestige, warmer material accents and ownership weight |
| Rankings | Monumental gold hierarchy; first place receives unique table treatment |
| City and Germany maps | Atmospheric tactical field, illuminated selection and glass layer controls |

## Responsive behavior

Desktop uses the full command rail and a 12-column-capable content canvas.
Tablet compacts the rail and metric grid. Below 760 px the rail becomes a
drawer, cinematic backdrops receive a readability shade and touch layouts use
larger controls. Mobile uses a custom floating glass/metal dock with original
signal glyphs, minimum 52-point primary controls, asymmetric panels and safe
bottom spacing. RTL positioning is mirrored explicitly.

## Cinematic command-center assets

The project-owned v2 day and night assets are registered in
`assets/asset-manifest.json`, reviewed under `assets/reports/reviews`, normalized
by the asset pipeline and distributed as responsive AVIF/WebP/PNG plus mobile
WebP.

- `global-command-center-premium-night-v2`
- `global-command-center-premium-day-v2`

Accepted generation prompts and style references are retained in:

- `assets/prompts/global-command-center-premium-night-v2.txt`
- `assets/prompts/global-command-center-premium-day-v2.txt`

The day image is a lighting edit of the night composition so geometry, camera,
command table and skyline remain coherent across the time transition.

## Guardrails

Do not introduce generic rounded cards, default browser buttons, stock icons,
unskinned charts, flat admin tables, decorative neon or arbitrary accent colors.
New UI must use the shared tokens and component states. New hero art must be
project-owned, text-free, provenance-tracked and processed through the existing
asset review and runtime-sync pipeline.

## Visual definition of done

Before release, validate desktop and mobile at minimum, including keyboard-only,
reduced-motion and forced-colors behavior. A screen passes only when hierarchy,
material depth, financial scanning, loading/empty/error/success states and touch
targets remain clear without relying on animation or color alone.

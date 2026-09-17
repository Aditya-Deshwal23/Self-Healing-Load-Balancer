# UI Context

Canonical source: `frontend/app/globals.css` and the component
markup in `frontend/app/`, `frontend/components/`,
`frontend/features/`. This reflects what is actually shipped and
confirmed against the live console and public site — not a design
aspiration. (`FRONTEND_UX_DESIGN.md` describes an indigo/OLED
direction that was never implemented; treat it as superseded by
this file. See `progress-tracker.md`.)

## Theme

A warm, editorial "copper" console — not the generic indigo SaaS
dashboard look. Light is the default `:root`; dark is an explicit
`[data-theme="dark"]` override on the same token set, toggled via
the header's theme control (Light / Dark / System). Structure and
spacing carry hierarchy; color marks state and one brand accent —
copper — marks "active/primary," never "healthy." The product
narrates a difficult moment (evidence incomplete, a control system
about to change routing) calmly: a plain-language situation brief
first, typed facts and matrices underneath it.

## Colors

CSS custom properties, defined once in `:root` (light) and
overridden in `[data-theme="dark"]`. Never hardcode a hex value in
a component — reference the token.

| Token                 | Light      | Dark       | Use |
| ---------------------- | ---------- | ---------- | --- |
| `--canvas`              | `#f2efe8`  | `#111311`  | Page background |
| `--panel`               | `#fbf9f4`  | `#191c19`  | Cards, panels, table surfaces |
| `--raised`              | `#ffffff`  | `#222622`  | Inputs, buttons, matrix cells, popovers |
| `--inset`               | `#e8e4dc`  | `#0d0f0d`  | Recessed surfaces (toolbars, table headers, code blocks) |
| `--text-primary`        | `#1b1d1a`  | `#f1eee7`  | Primary text |
| `--text-secondary`      | `#5a5f58`  | `#b2b8af`  | Body/explanatory text |
| `--text-muted`          | `#747a72`  | `#91988f`  | Metadata, labels, timestamps |
| `--border-subtle`       | `#d5d0c7`  | `#343934`  | Default hairline borders |
| `--border-strong`       | `#a59e92`  | `#555d55`  | Emphasized borders, dialogs, active cards |
| `--accent-copper`       | `#9a4f2d`  | `#d07a50`  | Brand, primary buttons/links, active nav, active selection |
| `--accent-copper-soft`  | `#efe0d7`  | `#3a271f`  | Copper-tinted backgrounds (active nav row, selection) |
| `--destructive`         | `#7d3828`  | `#c26045`  | Primary-button hover/pressed (danger-adjacent) |
| `--amber`               | `#a25d00`  | `#f0a62e`  | Uncertain / pending / drift / verifying / warning |
| `--amber-soft`          | `#f4e6cc`  | `#352919`  | Amber-tinted backgrounds |
| `--verified`            | `#287449`  | `#54b77a`  | Passed / healthy / complete / confirmed |
| `--verified-soft`       | `#dcebe1`  | `#173323`  | Verified-tinted backgrounds |
| `--danger`              | `#a63c32`  | `#ef7468`  | Failing / quarantined / harmful / current incident |
| `--danger-soft`         | `#f1dcd7`  | `#3b211f`  | Danger-tinted backgrounds |
| `--neutral`             | `#65706a`  | `#9aa69e`  | Default/unset state (no strong signal yet) |
| `--neutral-soft`        | `#e1e5e1`  | `#29302b`  | Neutral-tinted backgrounds |
| `--focus`               | `#7b4d2f`  | `#e0a078`  | Keyboard focus ring |

Non-color tokens: `--rail-width: 240px` (216px under 1439px, 64px
icon-only under 1023px, slide-over drawer under 767px);
`--header-height: 56px`; `--shadow-menu` (elevation for menus/
dialogs, heavier in dark mode); `--font-sans`; `--font-mono`.

Semantic rules (five states, not six — there is no separate
"quarantine" color; quarantine uses `--danger`):
- **Copper** = active/primary/selected. Never implies healthy.
- **Verified (green)** = an observed or verified condition actually
  passed — not merely attempted.
- **Danger (red)** = current harm: failing cells, quarantine,
  reserve breach.
- **Amber** = an unresolved obligation next to it: pending,
  uncertain, stale, verifying, drift.
- **Neutral** = default/no-signal-yet.
- Color is always paired with a label, icon, or position — never
  the sole carrier of state (e.g. `.matrix-cell-button` combines
  border color, fill pattern, and a text badge for the same state).

## Typography

| Role      | Font                                                | Variable      |
| --------- | ---------------------------------------------------- | ------------- |
| UI text   | Source Sans 3 Variable (fallback: Source Sans 3 → Segoe UI → system-ui) | `--font-sans` |
| Code/mono | IBM Plex Mono (fallback: SFMono-Regular → Consolas)   | `--font-mono` |

Both are bundled locally via `@fontsource-variable/source-sans-3`
and `@fontsource/ibm-plex-mono` — no external font CDN. Monospace is
used for identifiers, hashes, weights, timestamps, and any tabular
numeric telemetry (`.fact-number`, `time`, `code`, `kbd` all get
`font-variant-numeric: tabular-nums`). Body text is 14px/1.45 by
default (set on `body`); headings use weight 620.

## Border Radius

| Context                                   | Radius |
| ------------------------------------------ | ------ |
| Buttons, inputs, icon buttons, matrix cells | `4px` (`3px` on the densest matrix cells) |
| Panels, cards, menus, dialogs               | `5px`–`6px` |
| Status tags / pills / segmented control     | `999px` (fully rounded) |

Shadows (`--shadow-menu`) are reserved for menus, the command
dialog, and the matrix side-sheet — not used on ordinary panels or
cards, which rely on a `1px` border instead.

## Component Library

- **No CSS framework.** Styling is hand-authored semantic CSS
  classes in `globals.css` (`.panel`, `.button`, `.status-tag`,
  `.matrix-cell-button`, `.decision-language`, etc.) built on the
  custom-property tokens above. There is no Tailwind, no
  `tailwind.config`, and no `shadcn/ui` in this project — new
  components should follow the same class-naming pattern, not
  introduce a utility-class or component-library dependency
- **Icons**: `lucide-react` (installed), stroke-based only
- **Data fetching**: TanStack Query, via `frontend/lib/api`
- **Charts/telemetry graphs**: Recharts (`.chart-canvas`,
  `.evidence-chart`, `.interval-plot` wrap it)
- **Theme switching**: a `[data-theme]` attribute on the root
  element (`light` / `dark`, plus a `System` option in the theme
  menu), not a Tailwind `dark:` variant or `prefers-color-scheme`
  alone

## Layout Patterns

- **Shell**: fixed `.app-rail` navigation (`--rail-width`, see
  above) + sticky `.global-header` (56px: breadcrumb, environment
  switcher, operating-mode indicator — `Automatic` / `Rules only` /
  `Safe` / `Manual`, shown live as e.g. `RULES_ONLY` — freshness/
  connection indicator, `⌘K` command trigger, theme control, user
  control)
- **Navigation sections** (`.rail-nav`, exactly as shipped):
  - **Command** — Command Center
  - **Traffic** — Live Topology, Route Matrix, Traffic Analysis, Backends
  - **Response** — Incidents, Healing Actions, Reintegration, Version Health
  - **Evidence** — Metrics, Logs
  - **Research Lab** — Fault Lab, Experiments, Baseline Comparison
  - **Configuration** — Routing Policies, Settings
- **Status banners**: `.fixture-strip` (amber) marks demo/typed-
  fixture data with no live control-API mutation; `.safe-mode-strip`
  (danger, non-dismissable) marks Safe mode with reason and
  suppressed actions
- **Command Center**: `.operational-strip` — a 6-stat row, each
  item's top border colored by severity (neutral/amber/danger/
  verified) — above a two-column `.command-working-row`: live
  topology on the left, the current decision panel on the right
- **Decision panel** (`.decision-class`, `.decision-chain`,
  `.decision-language`): a 2×2 evidence grid —
  **Classifier suggested** (pattern + confidence, e.g. "shadow
  model 0.82"), **Safety engine allowed**, **HAProxy observed**,
  **Verification confirmed** — with `.decision-language > div.pending`
  getting an amber-soft background when that cell isn't resolved
  yet. This is the exact slot the HYBRID_SHADOW statistical signal
  (`Classification.evidence_support.shadow_statistical_signal`)
  should be wired into — see the note in `progress-tracker.md`
- **Route × Instance Matrix** (`.matrix-cell-button`): a desired-
  state outline (`.desired-frame`) over an observed-state fill
  (`.observed-fill`), with named states — `state-healthy`,
  `state-quarantined`, `state-failing`, `state-reintegrating`,
  `state-degraded`, `state-unknown`, `state-no-membership` — plus a
  dashed-border drift indicator and a hover card with per-cell
  metrics
- **Decision Trace**: a 6-chapter tab strip (`.trace-chapters`) over
  a two-column workspace — a canvas (pipeline stages,
  `.trace-stage-list`, and a dual-verification branch showing
  symptom relief vs. preserved capacity separately,
  `.trace-verification-branch`) and a sticky inspector panel
  (evidence constellation, scope comparison table, capacity
  calculation, raw fields behind a `<details>` disclosure)
- **Command palette**: `⌘K`/`Ctrl+K` opens `.command-dialog`, a
  centered modal with grouped, keyboard-navigable results

## Icons

`lucide-react`, stroke-based only. No fixed size token is declared
in `globals.css`; components size icons to match their control's
height (inline text ~14–16px, `.icon-button`/`.user-button` controls
are 32–34px tall) — follow that ratio rather than introducing a new
one.
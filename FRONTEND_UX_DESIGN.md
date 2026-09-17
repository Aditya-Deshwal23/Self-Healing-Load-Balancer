# Self Healing Load Balancer — Product Experience & Interface Design

> **⚠️ STATUS NOTE (2026-09-17):** This document is **superseded** as the implementation authority. The shipped console uses a warm "copper" design system documented in `CONTEXT/ui-context.md` and implemented in `frontend/app/globals.css` — not the "Quiet OLED" / indigo / charcoal direction described in Section 4 below. The installed fonts are `@fontsource-variable/source-sans-3` (Source Sans 3) and `@fontsource/ibm-plex-mono` (IBM Plex Mono) — not Geist. The styling is hand-authored semantic CSS with no framework; `shadcn/ui`, `tailwindcss`, and `framer-motion` are **not installed** in `frontend/package.json`. For all new frontend work, read `CONTEXT/ui-context.md` first. The experience principles (Sections 2–3.3) and the telemetry boundary (Section 3) remain valid product intent and are preserved here. See ADR-023 in `docs/design/20_RISK_REGISTER_AND_DECISION_LOG.md` for the formal reconciliation record.

Status: ~~final UI/UX direction~~ superseded — see note above  
Canonical frontend design authority: `CONTEXT/ui-context.md`  
Applies to: operator console, research console, setup, and incident review  
Implementation target: Next.js, TypeScript, hand-authored CSS (no framework), TanStack Query, SSE — ~~Tailwind CSS, shadcn/ui primitives, Framer Motion~~ not installed


## 1. The product should feel like an explanation, not an instrument panel

Self Healing Load Balancer is an operations product for a difficult moment: traffic is failing, evidence is incomplete, and a control system may be about to change production routing. The interface must make that moment feel calm, legible, and reversible.

The product opens with a plain-language account of what matters now, then lets an operator move naturally from summary to proof:

> Backend-B handled 3,402 requests successfully in the last 15 minutes. `/checkout` is 42% slower than its peer instances, while `/public` and `/auth` on the same machine remain stable.

That sentence is not generated speculation. Every clause is assembled from typed, cited facts and links to the exact evidence window. The deeper experience exposes the route × instance × version comparisons, deterministic constraints, HAProxy targets, readback, and verification obligations behind it.

The interface is the clearest visible manifestation of Evidence-Bounded Minimum-Scope Healing (EBMSH): it shows why a small intervention was supported, why broader interventions were rejected, what healthy capacity was intentionally preserved, and whether both halves of the post-action invariant passed.

This remains a preliminary patent-exploration posture, not a “patented” marketing claim. Standard health checks, outlier ejection, quarantine, canary weighting, and staged recovery are identified as established mechanisms. The product-specific technical story is the complete EBMSH transaction and its measured effect.

## 2. Non-negotiable experience principles

### 2.1 Tell the situation before showing the system

Each primary view begins with a concise situation brief: what changed, where it is localized, what remains healthy, and whether action is pending. Metrics support the sentence; they do not replace it.

### 2.2 Make minimum scope visible

The UI always distinguishes a physical instance from its logical route memberships. A route-local problem on Backend-B never paints all of Backend-B as failed. Selected and rejected routing scopes remain inspectable.

### 2.3 Give preserved health equal visual weight

Symptom relief alone is not success. The unaffected cohort is present before action, in the Blast Radius Map, and throughout split-track verification. Preserved capacity is not a footnote.

### 2.4 Separate suggestion, permission, execution, and proof

These are four different product states:

1. deterministic rules or an optional classifier suggest a failure class;
2. the deterministic safety envelope permits or rejects concrete targets;
3. the single writer applies and reads back a HAProxy change;
4. dual verification commits or restores it.

No color, icon, or sentence may collapse these states into “AI fixed it.”

### 2.5 Progressive disclosure over permanent density

The first glance is quiet. Hover, keyboard focus, filtering, and click-to-expand reveal more detail in predictable layers. The matrix can scale to many routes and instances without making the default experience feel like a spreadsheet wall.

### 2.6 Reversibility is part of every action

Previous state, requested state, observed state, expiry, rollback target, and verification clock travel with the action. A user never has to search for the escape path.

### 2.7 Motion explains causality

Transitions show selection, scope, state convergence, and verification progress. Nothing moves merely to imply that the product is intelligent or alive.

## 3. Absolute telemetry boundary: zero target-side integration

The console must never request, imply, or reward installation of customer-side JavaScript, browser tags, tracking pixels, SDKs, agents in application code, or frontend modifications.

All UI facts originate from these black-box, out-of-path sources:

| Source | UI facts it may support |
|---|---|
| HAProxy Runtime and Stats sockets | observed member state, effective weight, health/admin state, queue, sessions, counters |
| Structured HAProxy/NGINX access logs | route group, selected member, outcome family, retry, timing, request correlation |
| Prometheus time series | bounded rates, latency distributions, errors, capacity/headroom, controller health |
| Direct non-mutating HTTP probes | route/member reachability and response timing on approved endpoints |

Every evidence panel exposes source, collection time, window, sample count, freshness, and completeness. Customer payloads, response bodies, cookies, authorization values, raw query values, and user identifiers never become presentation data.

The product may say “Observed from proxy traffic” or “Confirmed by a direct probe.” It must never say “Reported by the customer frontend.”

## 4. Visual direction: Quiet OLED

### 4.1 Character

The console is dark, spacious, and exact. Deep OLED surfaces create focus; hairline charcoal boundaries provide structure; vivid accents appear only where the operator’s attention is required. Layout and typography carry most hierarchy.

The visual reference is the restraint and fit-and-finish of Linear, Vercel, Stripe, and Raycast—not their branding. There are no generic dashboard gradients, glass panes, oversized KPI cards, AI sparkles, chat bubbles, or decorative circuit illustrations.

Soft radial glows are permitted behind active topology nodes and the current Decision Trace chapter. They are diffuse, low-opacity, clipped to their container, and never used behind body text.

### 4.2 Dark-mode color tokens

Dark mode is the canonical product expression and default for the operations console. Light and System modes may ship, but light mode must be a deliberate semantic translation with equal contrast and state clarity—not an inverted afterthought.

| Token | Value | Use |
|---|---:|---|
| `bg-root` | `#000000` | OLED page background |
| `bg-canvas` | `#050505` | Main workspace |
| `bg-surface` | `#0A0A0A` | Panels, cards, sheets |
| `bg-elevated` | `#0F0F10` | Menus, command palette, dialogs |
| `bg-hover` | `#141416` | Hover and keyboard-current row |
| `bg-selected` | `#151526` | Selected evidence/routing context |
| `border-subtle` | `#1F1F1F` | Default structure |
| `border-strong` | `#303036` | Selected or nested structure |
| `text-primary` | `#F5F5F5` | Primary text |
| `text-secondary` | `#A1A1AA` | Explanatory text |
| `text-tertiary` | `#71717A` | Metadata; never sole state carrier |
| `accent-routing` | `#6366F1` | Active routing context and selection |
| `accent-routing-bright` | `#818CF8` | Focused path and active trace chapter |
| `state-verified` | `#34D399` | Verified health or passed obligation only |
| `state-quarantine` | `#FB7185` | Quarantined membership or rollback target |
| `state-danger` | `#F43F5E` | Harmful result, failed rollback, reserve breach |
| `state-uncertain` | `#FBBF24` | Unknown, incomplete, stale, verifying |
| `state-info` | `#38BDF8` | Neutral evidence/probe annotation |
| `focus-ring` | `#A5B4FC` | Keyboard focus |
| `overlay-scrim` | `rgba(0,0,0,.72)` | Modal/sheet separation |

Accent rules:

- Electric indigo means “this is the active route, selection, or control context”; it does not mean healthy.
- Emerald appears only after an observed or verified condition passes.
- Muted rose marks capacity intentionally removed or a rollback boundary; bright red is reserved for current harm.
- Amber always names the unresolved obligation beside it: stale, insufficient, unknown, pending, or conflict.
- Color is redundant with label, icon, position, or texture.

### 4.3 Glows and depth

Use three depth mechanisms only:

1. a `1px` charcoal boundary;
2. a surface step from `#050505` to `#0A0A0A` or `#0F0F10`;
3. a contextual radial glow at 8–14% opacity.

Example active-routing glow:

```css
radial-gradient(circle at 50% 50%, rgba(99, 102, 241, 0.14), transparent 64%)
```

Verified and quarantined glows use the same geometry at lower opacity. Do not use outer neon shadows, full-card gradients, or glow on every healthy node.

### 4.4 Typography

- Primary typeface: Geist Sans, locally bundled.
- Fallback: Inter, then `ui-sans-serif`, then SF Pro/system UI.
- Monospace: Geist Mono for identifiers, hashes, weights, timestamps, and aligned telemetry.
- Display: `clamp(32px, 3vw, 48px) / 1.08`, weight 560–620.
- Page narrative: `24px / 1.3`, weight 520.
- Section title: `16px / 1.4`, weight 560.
- Body: `14px / 1.55`, weight 400.
- Compact data: `12px / 1.45`, weight 440.
- Micro metadata: `11px / 1.4`, weight 500; avoid excessive uppercase.

Headings use sentence case. Numeric telemetry uses tabular figures. Human-readable names are primary; stable IDs remain one click or copy action away.

### 4.5 Layout, spacing, and shape

- Four-pixel base; common spacing: 4, 8, 12, 16, 20, 24, 32, 40, 56, 72.
- Main content uses a fluid 12-column grid and a maximum readable narrative width of 1,440 px.
- Matrix, topology, and trace canvases may expand to the viewport.
- Standard page gutters: 32 px at desktop, 24 px at compact desktop, 16 px on tablet.
- Primary panels use 10–12 px radii; nested controls use 7–8 px; compact tags may use full rounding.
- A normal page contains fewer visible borders than the old console. Grouping comes first from spacing and alignment.
- Shadows are subtle and limited to the command palette, modal dialogs, and floating inspectors.

## 5. Product shell and navigation

### 5.1 Persistent shell

The shell has a quiet 216 px navigation rail that can collapse to 56 px. The header is 52 px and contains:

- environment switcher;
- operating mode (`Automatic`, `Rules only`, `Safe`, `Manual`);
- freshness and stream state;
- centered command-palette trigger;
- notifications, help, theme, and user controls.

The current environment is always visible. Safe mode adds a persistent rose/amber-tinted strip with the reason, start time, suppressed actions, and recovery prerequisites. It cannot be dismissed.

### 5.2 Command palette as the primary hub

`Cmd/Ctrl + K` opens a Raycast-style command surface. It is the fastest path to navigation, inspection, and permitted workflows.

The palette supports:

- natural-language entity search: “checkout on backend b,” “open incident 1042,” “show stale routes”;
- direct navigation to routes, instances, versions, incidents, actions, policies, and experiments;
- context-aware commands: “Compare peers,” “Open Decision Trace,” “Preview quarantine,” “Pause reintegration”;
- recent and pinned entities;
- grouped keyboard results with path, current state, and freshness;
- a preview pane for the highlighted result at ≥1,024 px.

The palette never completes a traffic mutation. A routing command opens the standard Blast Radius and confirmation journey with the target already selected. Disabled commands remain searchable and explain the missing permission or safety condition.

### 5.3 Information architecture

```text
Command Center
Traffic
├── Route × Instance Matrix
├── Live Topology
├── Traffic Analysis
├── Backend Inventory
└── Backend Detail
Response
├── Incidents
├── Decision Traces
├── Healing Actions
├── Reintegration
└── Version Health
Evidence
├── Metrics
└── Structured Logs
Research Lab
├── Fault Lab
├── Experiments
└── Baseline Comparison
Configuration
├── Routes & Memberships
├── Policies
├── Environments
└── Settings & Audit
```

Research Lab is absent when lab mode or authorization is absent. It is not merely hidden in the browser.

## 6. Voice, narrative, and human-readable data

### 6.1 Situation briefs

Each primary page begins with a generated-from-facts brief containing:

1. time window;
2. affected scope;
3. magnitude and comparison;
4. preserved or uncertain cohort;
5. current system action/state.

Examples:

> Since 14:02, `/checkout` on Backend-B has timed out 4.8× more often than `/checkout` on its peer instances. Three other routes on Backend-B remain within their normal range. The system is checking whether a route-only quarantine is safe.

> Checkout recovered after Backend-B was removed from one logical pool. Public, auth, and catalog traffic on the same physical instance held steady. Reintegration can begin after 276 more real requests or 48 seconds, whichever is later.

> Evidence is incomplete. HAProxy state is fresh, but Prometheus samples are 94 seconds old. No automatic action is allowed.

Each quantitative phrase links to a fact chip. Copy never asserts root cause when the system only classified a failure pattern. “Associated with,” “localized to,” and “consistent with” are preferred to “caused by.”

### 6.2 Labels that read like decisions

Prefer:

- “Why this scope?” over “Classifier details”;
- “What stays healthy” over “Unaffected set” in primary copy;
- “Waiting for enough real traffic” over “INSUFFICIENT_SAMPLE_COUNT”;
- “HAProxy has not confirmed this change” over “desired ≠ observed” in narrative copy;
- “View raw fields” as a secondary forensic action.

Precise domain terms and machine states remain visible in badges and detail panels.

### 6.3 Narrative safety

Natural-language headers are deterministic templates over typed facts by default. If the optional reporting LLM is used elsewhere, its prose is visibly marked and never supplies live status, safety permission, or action copy.

## 7. Command Center

The opening screen is a situation room, not a KPI dashboard.

```text
┌ Environment · Automatic · Live 3s ·                      ⌘K ┐
├──────────────────────────────────────────────────────────────┤
│ “Traffic is stable overall. Checkout on Backend-B needs      │
│  attention; three healthy routes on the same host are safe.” │
│  Last 15 min · 18.4k requests · evidence 96% complete        │
├────────────────────────────────┬─────────────────────────────┤
│ Active traffic topology        │ Current decision            │
│ soft route-flow emphasis       │ Why this scope?              │
│                                │ Safety checks 6/7            │
├────────────────────────────────┴─────────────────────────────┤
│ Route × Instance Matrix · overview mode                      │
├────────────────────────────────┬─────────────────────────────┤
│ What changed                   │ What happens next            │
│ incident/action narrative      │ verification/reintegration   │
└────────────────────────────────┴─────────────────────────────┘
```

The headline changes only when a material persisted fact changes. Supporting facts animate by cross-fade, never counting theatrically from zero. When nothing requires action, the page states what is stable and when the controller last reconciled.

## 8. Route × Instance Matrix

The matrix is the fastest way to understand logical isolation across shared physical capacity. It must be powerful without feeling hostile.

### 8.1 Mental model

- Rows are logical route groups.
- Columns are physical instances, optionally grouped by deployment version.
- A cell is one HAProxy membership `(backend, server)`.
- Physical capacity is shown once in the instance header, never duplicated into every membership.
- Cross-route aggregate load belongs to the column header; route allocation and observed share belong to the cell.

### 8.2 Three density levels

The matrix has a persistent view switcher:

1. **Overview:** state glyph, configured weight, one dominant deviation. Default.
2. **Operational:** adds error rate, p95, sample count, and freshness.
3. **Forensic:** adds desired/observed values, check/admin state, control comparisons, and evidence flags.

Changing density does not change filters or selection. The operator can scan first and expand only the region that matters.

### 8.3 Default cell

A 72–88 px overview cell contains no more than:

- a state glyph and short label;
- effective weight such as `100` or `20% stage`;
- one small deviation label such as `p95 +42%`;
- an edge marker for quarantine, drift, or reintegration.

Healthy cells are quiet. They do not all glow green. Verified health uses a small emerald check or edge only when relevant to the current comparison.

### 8.4 Hover, focus, and side panel

Hover or keyboard focus opens a lightweight popover with:

- “what changed” sentence;
- error, latency, request, weight, and freshness values;
- same-route peer comparison;
- same-instance other-route comparison;
- desired versus observed state;
- links to evidence and Decision Trace.

Click/Enter pins the selection and opens a 420–520 px side panel. The panel starts with the narrative, then shows charts and fields. Selecting a cell never changes traffic.

### 8.5 Desired and observed state

Desired state is a thin outer frame. Observed HAProxy state is the interior. A mismatch uses a diagonal seam, an amber edge, and the label `Not yet confirmed` or `Drift`.

| Desired | Observed | Primary copy |
|---|---|---|
| ready / 100 | ready / 100 | Ready at full weight |
| drain | ready | Drain requested · awaiting HAProxy |
| drain | drain | Quarantined from this route |
| ready / 20 | ready / 20 | Reintegrating · 20% stage |
| ready / 20 | ready / 5 | HAProxy differs from requested weight |
| no membership | no membership | Not in this pool |
| populated | unavailable | HAProxy readback unavailable |

Weight zero, drain, and maintenance remain visibly different states.

### 8.6 Route-local quarantine example

When `checkout × Backend-B` is quarantined:

- that one cell gains a muted rose edge and `Quarantined` label;
- the Backend-B header reads `1 of 4 memberships quarantined`;
- public, auth, and catalog cells stay visually active;
- an indigo focus line connects the selected cell to the Blast Radius Map;
- the physical-capacity summary recalculates unique load/headroom without counting four copies of Backend-B.

The entire Backend-B column must never turn red for a route-local action.

### 8.7 Scale and accessibility

- Both axes virtualize after measured thresholds.
- Route and instance headers stay pinned.
- Filters are expressed as removable natural-language chips.
- Hidden quarantined/drifting cells create a persistent “3 critical cells hidden by filters” notice.
- Arrow keys navigate cells; Enter opens detail; Shift+arrow builds a comparison selection.
- A semantic table mode contains the identical facts and actions.

## 9. Decision Trace: an interactive diagnostic narrative

The Decision Trace is not a stepper and not a log. It is a time-aware diagnostic canvas that shows how evidence became a bounded intervention and how the intervention earned—or failed to earn—commit.

### 9.1 Page composition

```text
┌ Incident story · scope · status · evidence age · owner ──────────────┐
│ “Checkout on Backend-B diverged; three routes on B stayed healthy.” │
├ Chapter rail: Observe · Localize · Bound · Act · Verify · Recover ──┤
├──────────────────────────────────────────┬───────────────────────────┤
│ Interactive trace canvas                 │ Context inspector         │
│ evidence cards + causal links            │ selected node’s proof     │
│ competing scope branches                 │ fields, rules, versions   │
├──────────────────────────────────────────┴───────────────────────────┤
│ Shared time scrubber · pre-window · action marker · post-window      │
└──────────────────────────────────────────────────────────────────────┘
```

The canvas has six human chapters while preserving the full technical sequence:

| Human chapter | Technical stages |
|---|---|
| Observe | Evidence window and source completeness |
| Localize | Fingerprint, affected sets, classification, competing hypotheses |
| Bound | Safety envelope, candidate routing units, deterministic cost |
| Act | Prepared snapshot, HAProxy command saga, observed readback |
| Verify | Affected symptom relief and unaffected-capacity preservation |
| Recover | Commit, restore, or staged reintegration |

### 9.2 Interaction model

- Scroll moves chapter by chapter while the incident summary remains anchored.
- The chapter rail supports direct navigation and shows completed, current, blocked, and superseded states.
- Selecting a node highlights its inputs and outputs; unrelated branches fade but remain present.
- The shared time scrubber aligns all charts to the evidence and verification windows.
- `Compare revision` overlays a prior classification or safety decision without overwriting history.
- `Show machine detail` reveals raw typed fields, rule identifiers, versions, digests, and correlation IDs.
- Export creates a redacted evidence bundle and rendered trace with a hash.

### 9.3 Observe: evidence constellation

Evidence appears as a small constellation around the affected membership:

- same route on peer instances;
- other routes on the same instance;
- control deployment versions;
- direct probes;
- proxy state and access outcomes;
- capacity and retry context.

Each evidence card shows source, sample count, time alignment, freshness, and whether it supports, contradicts, or cannot decide the suspected scope. Missing sources occupy visible empty slots; they do not disappear.

### 9.4 Localize: competing scope branches

The fingerprint produces visible scope branches: route membership, whole instance, complete route, version cohort, overload/traffic condition, and unknown. Branch width does not encode model confidence. Each branch lists supporting and counter-evidence.

When an optional classifier runs, the inspector shows:

```text
Suggested pattern
Route-instance failure · probability 0.82 · model v3

Deterministic permission
Not decided here. Continue to safety envelope.
```

Probability uses neutral/indigo styling. It never receives the emerald “verified” treatment.

### 9.5 Bound: safety envelope and minimum-scope choice

The selected scope sits inside a visible envelope of hard constraints:

- evidence support and counter-evidence;
- unique physical capacity floor;
- retry and idempotency semantics;
- action conflicts and ownership;
- cooldown/flapping state;
- rollback availability;
- approval policy and plan expiry.

Candidates appear as a scope ladder ordered by deterministic blast-radius cost. Each row contains concrete HAProxy targets, healthy capacity displaced, criticality, target count, intervention risk, and result.

```text
Route membership    1 target   0 healthy pools displaced   Allowed · selected
Whole instance      4 targets  3 healthy pools displaced   Rejected by evidence
Complete route      3 targets  2 healthy peers displaced   Rejected by evidence
Version cohort      4 targets  Insufficient control data   Not allowed
```

The interface states “smallest supported safe action,” not merely “smallest action.” A cheaper unsupported unit cannot win.

### 9.6 Act: observable saga

The action node expands into a three-column diff:

| Previous | Requested | Observed |
|---|---|---|
| ready · weight 100 | drain · weight 100 | drain · weight 100 |

The saga shows controller generation, target digest, idempotency key, attempts, HAProxy response, readback, and rollback snapshot. `Requested` uses indigo. `Observed` remains amber until readback matches. Only a match gains an emerald check; it still does not mean the action was effective.

### 9.7 Verify: the trace splits into two equal tracks

At verification, the single trace physically divides. The two tracks share the same time axis, action marker, and verdict gate.

```text
                    action applied
                         │
Track A · Relief         │  checkout errors 18.2% → 3.1%
Affected cohort  ────────┼──────────────╲_____  PASS
                         │
Track B · Preservation   │  public/auth/catalog throughput ±1.4%
Healthy cohort   ────────┼────────────────────  PASS
                         │
                         ▼
              DUAL-VERIFICATION GATE
              Both obligations passed
                         │
                      COMMIT
```

The tracks have identical visual weight and neither collapses by default.

#### Track A — affected cohort relief

Track A shows:

- affected route/member/version identity;
- pre-action baseline and aligned peer control;
- error, timeout, and latency change;
- required versus observed request samples;
- relief threshold and confidence/interval where configured;
- direct-probe evidence identified as synthetic;
- remaining deadline.

Primary copy example:

> Checkout errors fell from 18.2% to 3.1% after the route membership was drained. The relief criterion passed with 428 real requests.

#### Track B — preserved cohort

Track B shows:

- explicitly named healthy routes and/or version controls;
- same-instance throughput and success continuity;
- unique remaining physical capacity versus policy floor;
- latency non-regression;
- queue and retry amplification guardrails;
- control validity and sample sufficiency.

Primary copy example:

> Public, auth, and catalog traffic on Backend-B remained eligible. Success changed by −0.1 percentage points, p95 changed by +1.8%, and unique reserve stayed 16 points above its floor.

#### The invariant gate

The tracks converge into a two-key gate:

| Track A | Track B | Overall verdict | Next state |
|---|---|---|---|
| pass | pass | `EFFECTIVE` | commit quarantine; schedule reintegration |
| pass | fail | `HARMFUL` or policy-defined ineffective | restore/compensate |
| fail | pass | `INEFFECTIVE` | restore or review |
| unknown | any | `INSUFFICIENT` | wait within deadline or restore/review |
| any | unknown | `INSUFFICIENT` | never commit as effective |

The overall verdict cannot turn emerald until both tracks pass. “No traffic” cannot pass either track as health.

### 9.8 Recover: reintegration or restoration

The final chapter explains the consequence in plain language, links to the exact rollback or reintegration run, and preserves the failed alternatives. A restored action remains in the trace; history is never rewritten as if it did not happen.

## 10. Blast Radius Map

The Blast Radius Map appears before every manual approval and within every automated action review. It is a visual proof of what will change and what is intentionally protected.

### 10.1 Core visual

The map centers the physical instance and fans its logical memberships into route ribbons.

```text
                           BACKEND-B · physical capacity 100
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
  /public · ready              /auth · ready              /catalog · ready
  PRESERVED                    PRESERVED                  PRESERVED
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      │
                              /checkout · drain
                              CHANGES · 1 membership
```

Visual language:

- changed membership: muted rose ribbon, solid boundary, before→after state;
- preserved memberships: neutral ribbon with an emerald confirmation edge and explicit `Unchanged` label;
- active selection/context: electric indigo focus line;
- uncertain readback: amber dashed boundary;
- no membership: no ribbon, not a disabled fake cell.

### 10.2 Before/after diff

A segmented toggle changes between `Before`, `Proposed`, and `Observed`. The node positions do not move; only the affected ribbon and capacity annotations morph. This makes the diff cognitively stable.

The summary reads:

> This action changes 1 of Backend-B’s 4 route memberships. Public, auth, and catalog remain eligible on Backend-B. Checkout retains two peer instances. Unique physical reserve remains 66%, above the 50% floor.

### 10.3 Scope comparison

Below the map, an expandable “Why not broader?” section compares the selected target with whole-instance, whole-route, and version alternatives. It shows healthy memberships displaced and deterministic rejection reasons.

This is where the product visibly demonstrates minimum blast radius: the operator can see the healthy route ribbons a conventional backend-wide removal would have cut.

### 10.4 Approval journey

The exact journey is:

1. Operator invokes `Preview quarantine` from a cell, incident, action, or command palette.
2. A full-height review sheet opens with the natural-language intent.
3. Blast Radius Map loads from an immutable plan snapshot.
4. The user reviews changed targets, preserved memberships, capacity floor, retry policy, expiry, and rollback.
5. Any stale safety-relevant input invalidates the preview and requires regeneration.
6. The user provides a reason; an Approver step appears when policy requires it.
7. Confirmation submits an idempotent domain command—never a raw HAProxy command.
8. The sheet changes from `Proposed` to `Applying`, then `Observed` only after Runtime readback.
9. The user is taken into the Decision Trace at the split verification chapter.

Automated actions use the same map in read-only mode and show the rule/policy version that authorized them.

## 11. Reintegration experience

Reintegration uses a calm horizontal journey on wide screens and stacked cards on compact screens:

`Quarantined → Probing → 5% → 20% → 50% → 100% → Healthy`

Percentages are configured weight relative to baseline, never promised traffic share. Every stage card displays both configured weight and observed share.

The lead sentence answers what is blocking progress:

> Backend-B’s checkout membership is holding at 20%. Symptom relief still passes, but 124 more real requests are required before moving to 50%.

Each stage includes dual-obligation progress, desired/observed state, real samples, probe state, cross-route physical load, cooldown, flap count, attempts, deadline, and the last verified rollback point. Other routes on the same instance remain visible as preservation controls.

Controls—pause, resume, roll back one stage, quarantine, require review—use the Blast Radius Map when they change traffic.

## 12. Supporting screen behavior

### Incidents

The list begins with a one-line brief per incident, then class/scope/status/evidence metadata. Default order is needs review, harmful/active, verifying, and recent resolved. Bulk resolve is prohibited.

### Backend inventory and detail

Inventory rows represent physical instances once. The detail page separates machine-wide evidence from route-local membership evidence. Shared capacity is never multiplied across logical pools.

### Traffic analysis

Charts use coordinated time cursors and event annotations. Error families, latency, queue, retries, and unique healthy capacity use small multiples rather than stacked percentiles or dual-axis clutter.

### Version health

Current and control cohorts show sample/traffic comparability before deltas. A version-removal preview lists every membership and the preserved stable-version capacity.

### Policies

Policy editing uses plain-language sections with a machine-readable diff available on demand. Structural changes say `Validated reload required`. Raw HAProxy directives cannot be entered.

### Logs and evidence

The default view summarizes structured events by route/member/outcome. Raw bounded fields are one layer deeper. There is no chatbot over logs and no payload/body viewer.

### Research Lab

Experiment and baseline pages prioritize distributions, intervals, effect sizes, excluded trials, and reproducibility facts. Fault injection retains a persistent isolated-lab warning and two-step confirmation.

## 13. Component system

shadcn/ui and Radix primitives provide behavior and accessibility; the visible components use this product’s tokens, spacing, voice, and state model.

| Family | Product components |
|---|---|
| Shell | AppRail, EnvironmentSwitch, ModePill, FreshnessIndicator, SafeModeBanner |
| Command | CommandHub, EntityResult, CommandPreview, PermissionReason |
| Narrative | SituationBrief, FactLink, ComparisonPhrase, LimitationCallout |
| Routing | RouteInstanceMatrix, MatrixCell, PhysicalCapacityHeader, MembershipInspector |
| EBMSH | DecisionTraceCanvas, TraceChapterRail, EvidenceConstellation, ScopeLadder, SafetyEnvelope |
| Blast radius | BlastRadiusMap, RouteRibbon, BeforeAfterToggle, PreservedSet, CapacityImpact |
| Verification | DualVerification, ReliefTrack, PreservationTrack, InvariantGate, VerdictSummary |
| Actions | StateTriptych, SagaTimeline, ReadbackStatus, RollbackAnchor, ApprovalReview |
| Recovery | ReintegrationJourney, StageCard, SampleGate, FlapHistory |
| Data | MetricSentence, SmallMultipleChart, VirtualTable, StructuredEvent, DiffInspector |
| Feedback | StructuralSkeleton, StaleSurface, ReconnectNotice, InlineProblem, EmptyState, Toast |

High-risk controls use dedicated review sheets, not generic confirmation modals.

## 14. Motion and micro-interactions

Framer Motion supplies shared layout transitions and orchestrated state changes.

### Timing

- hover/focus: 100–140 ms;
- panel and side-sheet entrance: 180–240 ms;
- chapter transition or before/after morph: 240–320 ms;
- spring interactions: high damping, no overshoot for operational state;
- skeleton-to-content cross-fade: 160–220 ms.

### Meaningful transitions

- Matrix selection expands into the side panel with a shared route/instance label.
- A selected matrix cell’s focus line continues into the Blast Radius Map.
- The Decision Trace splits into two verification tracks only when verification begins.
- Requested state moves into Observed through a short cross-fade after readback, not immediately after submit.
- The dual-verification gate closes only when both tracks pass.
- Reintegration advances one stage at a time with the previous verified stage remaining visible.

### Prohibited motion

- perpetual healthy-state pulsing;
- drifting topology nodes;
- particle traffic simulations;
- number count-ups on initial load;
- celebratory confetti;
- motion that suggests commit before observed confirmation.

`prefers-reduced-motion` replaces spatial transitions with opacity/border changes and removes background glow animation.

## 15. Loading, stale, unknown, and failure states

Skeletons mirror the actual final structure: sentence lines, topology nodes, matrix headers/cells, trace branches, and verification tracks. They never show fake metric numbers.

- Initial load: structural skeleton and a simple “Loading current evidence” label.
- Incremental refresh: retain content, soften it, and show age; do not blank the page.
- No traffic: “No real requests in this window” and the implication for decidability.
- No membership: a topology fact, visually different from missing telemetry.
- SSE reconnect: quiet inline notice for 10 seconds, then persistent amber state; REST resync on cursor gap.
- Result unknown: freeze duplicate controls and explain that HAProxy readback is in progress.
- Stale evidence: retain last fact with timestamp and prevent it from appearing current.
- Prometheus loss: verification becomes insufficient; desired or HAProxy state cannot substitute for outcome evidence.
- Rollback failure: full-width danger state, overlapping actions frozen, explicit operator next steps.

## 16. Real-time interaction contract

The browser uses a versioned REST snapshot plus one ordered, environment-scoped SSE stream:

1. load snapshot and record `snapshot_event_id`;
2. open SSE after that cursor;
3. ignore duplicate or older aggregate versions;
4. detect gaps and refetch before applying later events;
5. keep desired and observed state as distinct typed objects;
6. never optimistically render a routing mutation as applied;
7. render a verification result only from persisted verification facts.

TanStack Query owns snapshots, caching, mutation submission, and invalidation. REST carries browser commands; WebSockets are unnecessary.

## 17. Data visualization rules

- Every chart includes title, unit, timezone, aggregation, sample count, missing intervals, and evidence window.
- Action and evidence-window markers align across small multiples.
- Measured lines are not smoothed in ways that invent values.
- More than six comparable series becomes small multiples or an interactive selection.
- Green/rose are state colors, not ordinary series colors.
- The Blast Radius Map and topology have list/table alternatives.
- Dual verification shares one time scale so relief and preservation cannot be compared across mismatched windows without a visible warning.

## 18. Accessibility

WCAG 2.2 AA is a release gate.

- Visible 2 px focus ring with adequate offset.
- Semantic landmarks and headings; skip links; focus restoration for sheets/dialogs.
- Matrix announces route, physical instance, version, membership state, desired/observed state, and dominant deviation.
- Decision Trace has an ordered narrative alternative with the same branches and rejected candidates.
- Blast Radius Map has a before/proposed/observed table listing every changed and preserved membership.
- Dual Verification announces Track A, Track B, their criteria, and the combined gate separately.
- Charts include concise text summaries and data tables.
- Live regions announce only material transitions, not every metric refresh.
- Status never depends on color, hover, or animation.
- Touch targets are at least 44×44 px outside intentionally compact pointer/keyboard data grids.

## 19. Responsive behavior

| Width | Experience |
|---|---|
| `≥1440 px` | full shell, trace canvas + inspector, matrix at selected density, split verification side by side |
| `1024–1439 px` | collapsed rail option, overlay inspectors, Blast Radius Map remains full width |
| `768–1023 px` | read/acknowledge focus; matrix and trace open dedicated full-screen modes; verification tracks stack with shared axis labels |
| `<768 px` | incident story, evidence status, acknowledgement, and policy-permitted emergency pause only |

Policy editing, broad routing approvals, topology manipulation, and fault injection are desktop-only. The mobile experience is intentionally safe and limited, not a squeezed desktop.

## 20. Frontend implementation blueprint

### Routes

```text
/command
/traffic/matrix
/traffic/topology
/traffic/analysis
/backends
/backends/[instanceId]
/incidents
/incidents/[incidentId]
/incidents/[incidentId]/trace
/actions
/actions/[actionId]
/reintegration
/versions
/policies
/evidence/metrics
/evidence/logs
/lab/faults
/lab/experiments
/lab/baselines
/settings
```

### Rendering and state

- Next.js App Router provides the application shell, route boundaries, and initial authenticated snapshot.
- Client components own live matrix, trace, charts, command palette, and action review interactions.
- Tailwind consumes CSS custom properties for semantic tokens.
- TanStack Virtual/Table handles matrix and inventory scale.
- React Flow or a bespoke accessible canvas may power topology and trace relationships; stable layout is mandatory.
- Framer Motion owns shared element and chapter transitions.
- Recharts or an equivalent bounded chart layer renders time series and research plots with accessible data fallbacks.
- Storybook captures every semantic state, density mode, evidence condition, and permission boundary.

No frontend package receives HAProxy credentials or direct Data Plane/Runtime connectivity.

## 21. Critical user journeys

### 21.1 Understand a new incident

1. Notification opens the incident story.
2. User reads affected and preserved scope in one sentence.
3. “Show how we know” opens the Decision Trace at Observe.
4. User explores same-route peers and same-instance routes.
5. User sees competing scope branches and the deterministic safety boundary.
6. User opens the Blast Radius Map to understand the selected unit.

### 21.2 Approve a route-local quarantine

1. User invokes preview from matrix, incident, or `Cmd+K`.
2. Immutable action snapshot and freshness load.
3. Blast Radius Map shows one changed checkout membership and three preserved routes on Backend-B.
4. Capacity and retry guardrails pass visibly.
5. User supplies reason and approval if required.
6. Request remains `Submitted` until HAProxy readback confirms it.
7. UI moves into split dual verification.
8. Both tracks pass before commit; otherwise the UI follows restore/review state.

### 21.3 Explain an automated action

1. User opens action from Command Center.
2. Situation brief states what changed and why.
3. Decision Trace exposes rule/model separation and rejected broader scopes.
4. Blast Radius Map shows protected healthy memberships.
5. State triptych proves desired and observed state.
6. Split tracks prove relief and preservation.
7. Export yields a redacted, hashed evidence bundle.

### 21.4 Recover capacity

1. User opens Reintegration from the verification outcome.
2. Lead sentence states current stage and blocking gate.
3. Other routes on the physical instance remain visible.
4. Each stage waits for observed weight plus both fresh obligations.
5. Failure rolls back to the last verified stage and increases cooldown.

## 22. Acceptance scenarios

The frontend direction is satisfied only when fixture-driven tests demonstrate:

- A new operator can explain the current incident from the situation brief without decoding raw metric names.
- Draining `checkout / Backend-B` leaves public, auth, and catalog visibly active on the same physical instance.
- The Blast Radius Map labels exactly one changed membership and three preserved memberships.
- A whole-instance alternative visibly displaces more healthy capacity and records why it was rejected.
- Physical capacity is counted once across four logical pools.
- Desired state never looks applied before Runtime readback.
- Optional classifier probability never looks like deterministic safety permission.
- Decision Trace is navigable as Observe → Localize → Bound → Act → Verify → Recover and retains the complete technical lineage.
- Verification visibly splits into Track A and Track B on a shared time axis.
- `EFFECTIVE` is impossible unless both tracks pass with sufficient fresh evidence.
- A symptom improvement plus preserved-cohort regression renders harmful/ineffective and follows restoration policy.
- No-traffic and stale-source cases render insufficient, never healthy.
- Command-palette mutations always enter the same Blast Radius and approval workflow.
- Matrix, trace, Blast Radius Map, and verification have complete keyboard and screen-reader alternatives.
- Reduced-motion mode preserves causality without spatial animation.
- No workflow requests target-side JavaScript, SDK installation, tracking, or customer application changes.

## 23. Explicit non-goals

- no chatbot as the primary interface;
- no “AI health score” or autonomous-agent theater;
- no drag-to-rewire production routing;
- no raw HAProxy command console;
- no payload or customer-user analytics;
- no fabricated savings, root-cause certainty, patent badge, or novelty claim for standard health checks;
- no mobile policy editor or fault injector;
- no decorative real-time animation;
- no dashboard-builder framework in the MVP.

## 24. Phase boundary

Phase 1 supplies this design authority and a static delivery endpoint. It does not fabricate live product telemetry or imply that the console is implemented. Subsequent frontend work must build from versioned REST/SSE fixtures and preserve the EBMSH distinctions defined here.

The headless traffic and control system remains authoritative. If the frontend, SSE, optional classifier, or reporting LLM is unavailable, HAProxy continues serving its last-known-good configuration and the worker suppresses evidence-dependent changes according to the frozen safety rules.

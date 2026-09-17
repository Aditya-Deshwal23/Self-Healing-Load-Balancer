# AI Workflow Rules

## Approach

Build this project incrementally using a spec-driven workflow. The
context files (`project-overview.md`, `architecture.md`,
`code-standards.md`, `ui-context.md`) define what to build and how;
`progress-tracker.md` defines current state. Always implement
against these specs and the frozen dossier in `docs/design/`/
`docs/research/` — do not infer or invent behavior from scratch, and
do not silently override an existing ADR.

## Scoping Rules

- Work on one feature unit at a time
- Prefer small, verifiable increments over large speculative changes
- Do not combine unrelated system boundaries in a single
  implementation step

## Current Focus

**Phase 1: wiring the existing `fastpath` EWMA signal into the
`RuleDecision` pipeline, strictly under `HYBRID_SHADOW`.** Scope for
this phase, in order:
1. Generalize `classify()` off any hardcoded route/instance so every
   cell in the topology is evaluated the same way.
2. Thread the fast-path signal into `classify()` as advisory-only
   evidence (`statistical_support`) — it may annotate a decision's
   `support` payload, never its `final_class` or `actionable`.
3. Confirm the signal is captured in existing telemetry
   (`ObservationWindow.metrics`, `Classification.evidence_support`)
   with no new migration.

Each step ships with its own test before moving to the next — do not
bundle steps 1–3 into one untested change.

## When to Split Work

Split an implementation step if it combines:

- Backend decision-pipeline changes and frontend Decision Trace UI
  changes — they have different verification loops (`pytest` vs.
  `vitest`/Playwright) and should land separately
- Any change to `route_instance_capacity`/`instance_capacity` with
  unrelated feature work — the safety floor always gets its own
  step and its own tests in `test_worker_policy.py`
- Behavior not clearly defined in the context files

Promoting the statistical signal from `HYBRID_SHADOW` to
`HYBRID_ACTIVE` is never an incremental step done opportunistically
alongside other work — it requires the full gate defined in
`docs/design/20_RISK_REGISTER_AND_DECISION_LOG.md` (shadow
validation window, calibration thresholds, false-action rate ≤1%,
two-reviewer sign-off) and is treated as its own dedicated unit when
it's actually undertaken.

If a change cannot be verified end to end quickly, the scope is too
broad — split it.

## Handling Missing Requirements

- Do not invent product or ML behavior not defined in the context
  files or the frozen `docs/design/`/`docs/research/` dossier
- If a requirement is ambiguous, check whether it's already resolved
  by an existing ADR before asking; if it isn't, resolve it in the
  relevant context file before implementing
- If a requirement is missing, add it as an open question in
  `progress-tracker.md` before continuing — do not guess and move on

## Protected Files

Do not modify the following unless explicitly instructed:

- `docs/design/*.md`, `docs/research/*.md` — frozen ADR dossier;
  changing a decision requires a new dated entry in
  `docs/design/20_RISK_REGISTER_AND_DECISION_LOG.md`, not a silent edit
- `route_instance_capacity()` / `instance_capacity()` in
  `worker_policy.py` — the safety floor; any change ships with new
  tests, never as a side effect of unrelated work
- `control-api/alembic/` — never hand-edit a past migration; always
  add a new one
- Any generated/vendored UI primitives added via a component CLI
  (if/when one is adopted — see the open question in
  `progress-tracker.md` about `shadcn/ui`)

## Keeping Docs in Sync

Update the relevant context file whenever implementation changes:

- System architecture or boundaries → `architecture.md`
- Storage model decisions → `architecture.md`
- Code conventions or standards → `code-standards.md`
- Feature scope → `project-overview.md`
- Visual/theme decisions → `ui-context.md`

## Before Moving to the Next Unit

1. The current unit works end to end within its defined scope
2. No invariant defined in `architecture.md` was violated
3. `progress-tracker.md` reflects the completed work
4. Backend units: `cd control-api && pytest` passes. Frontend
   units: `cd frontend && npm run build` (and `npm run test` for
   Vitest suites) passes. A unit that touches both stacks is not
   done until both pass.
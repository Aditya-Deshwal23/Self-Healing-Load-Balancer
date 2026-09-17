# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- In Progress — Phase 1 (HYBRID_SHADOW wiring)

## Current Goal

- Close the loop between the existing `fastpath` EWMA signal and
  the deterministic decision pipeline, without granting it
  actuation authority, so `benchmarks/run_experiments.py`-driven
  runs can produce real MTTD_shadow-vs-MTTD_rules data for the
  H_new ablation in the IEEE paper.

## Completed

- Generalized `classify()` in `worker_policy.py` from the hardcoded
  `checkout`/`inst-b` flagship scenario to a full per-cell evaluator
  over `ROUTES × INSTANCES`; `route_instance_capacity()`/
  `instance_capacity()` left untouched (already topology-generic)
- Added `statistical_support` parameter to `classify()`; threaded
  through as `shadow_statistical_signal` in every decision branch's
  `support` payload — advisory-only, verified never to change
  `final_class`/`actionable`
- Added `LAB_POLICY.hybrid_shadow_enabled` flag (default `True`)
- `worker.py`: `ControlWorker` now tracks per-cell `flagged_since`
  onset timestamps (`_fastpath_onset`); `_observe()` returns
  `fast_recommendations`; `tick()` passes it into `classify()`
- Added regression and safety tests to `test_worker_policy.py`
  (22/22 passing — includes two tests proving the generalization and
  one proving the shadow signal can never flip actionability)

## In Progress

- None — Phase 1 code is written and unit-tested in isolation; not
  yet run against the live Compose stack

## Next Up

- Run `local-smoke` / `scripts/test_safety_scenarios.py` against the
  live stack to confirm the wiring survives real Postgres/Redis/
  HAProxy, not just unit tests
- Run `benchmarks/run_experiments.py` for baselines B1–B4 to unblock
  the IEEE draft's placeholder numbers
- Build the MTTD_shadow-vs-MTTD_rules extraction query for the
  H_new ablation, joining `ObservationWindow.metrics`,
  `Incident.opened_at`, and `LabFault.applied_at`
- Reconcile docs vs. shipped code (see Open Questions below)

## Open Questions

- ~~Which theme/fonts/component libraries are authoritative 
  **resolved**: the real console is the warm "copper" theme already
  shipped in `frontend/app/globals.css` (light `:root` +
  `[data-theme="dark"]`), Source Sans 3 Variable / IBM Plex Mono,
  hand-authored CSS with no framework, no shadcn/ui, no Framer
  Motion. `FRONTEND_UX_DESIGN.md` is superseded by `ui-context.md`
  for anything the two disagree on
- `HYBRID_SHADOW → HYBRID_ACTIVE` promotion criteria are already
  ADR'd in `docs/design/20` — not revisited here

## Architecture Decisions

- Shadow signal travels through `classify()`'s existing `support`/
  `evidence_support` payload rather than a new table or columns —
  zero migration needed for Phase 1. A `model_version`/
  `calibration_id` migration is deferred until a trained classifier
  (a later phase) replaces the raw EWMA passthrough
- Onset-time tracking (`_fastpath_onset`) lives in `ControlWorker`,
  not `FastPathController` — kept `fastpath.py` itself untouched
  since it was already tested and working; onset bookkeeping is a
  consumer-side concern, not the EWMA controller's
- UI theme/typography/component-library baseline locked to the
  shipped `globals.css` system, confirmed against the live console
  screenshots — not the earlier `FRONTEND_UX_DESIGN.md` direction
- The Decision Trace's existing `.decision-language` "Classifier
  suggested" cell is the real UI slot for the shadow signal.
  `frontend/lib/api/operations.ts` already types
  `evidence_support` as `Record<string, unknown>`, so no frontend
  schema change is needed — the display component just needs
  pointing at `evidence_support.shadow_statistical_signal` once
  real data replaces the current fixture value

## Session Notes

- Baseline before Phase 1: 18 tests passing across
  `test_worker_policy.py` + `test_fastpath.py`. After Phase 1: 22
  passing (4 new), 0 regressions, `worker.py` compiles clean —
  verified with
  `PYTHONPATH=control-api/src pytest control-api/tests/test_worker_policy.py control-api/tests/test_fastpath.py -v`
- The single call site for `classify()` and for `_observe()` is
  `ControlWorker.tick()` — both already updated; no other module
  calls either function
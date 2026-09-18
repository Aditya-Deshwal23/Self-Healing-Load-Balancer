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
- Verified the Step 1 documentation and dead-code alignment is
  already present in the repo itself: zero `encode_secret_for_file`
  call sites, no stale `and_`/`Project` imports in
  `routers/operations.py`, ADR-023 and the theme/status notes are
  present, and the README/docs already reflect the Phase 1 +
  `CONTEXT/` authority reconciliation

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
- [2026-09-17] Completed documentation and dead-code alignment pass; deleted unused `encode_secret_for_file` and unused imports, added ADR-023, and added status notes to stale architectural docs.
- [2026-09-18] Verified the Step 1 repo state directly: no `encode_secret_for_file` call sites remain, `routers/operations.py` has no stale `and_`/`Project` usage, the ADR and status notes are already present, and the README/docs already reflect the Phase 1 / `CONTEXT/` reconciliation. Attempted `cd control-api && pytest`, but this shell does not have `pytest` installed (`zsh: command not found: pytest`).
- [2026-09-18] Step 2: checked `models.py` and the two migrations directly. `BackendInstance` and `RouteMembership` are versioned only via the generic `VersionMixin` and the current migrations contain all schema needed for the code paths that actually read/write today; there is no version-membership column/table dependency that is missing. The frontend also exposes a `Version Health` nav destination, but it is a UI stub for cohort comparison rather than a backend contract requiring an uncreated membership-versioning field. Archived `docs/architecture/FRICTIONLESS_ONBOARDING.md` to `docs/archive/FRICTIONLESS_ONBOARDING.md` and prefixed it with the required out-of-scope note.
- [2026-09-18] Step 3: classified the five docs against the real repo state and Phase 1 scope. `PATENT_DISCLOSURE.md` is archival-out-of-scope because it describes a speculative patent overlay beyond the current single-environment lab prototype. `MERMAID_DIAGRAMS.md`, `INTERACTIVE_DEMO_MODE.md`, and `PROMPT_VAULT.md` all contradict the actual Phase 1 scope and single-writer, rule-only implementation; I archived them to `docs/archive/` with the required “out of scope” note. `FINAL_PHASES_PROMPT_VAULT.md` is still a future-phase operational prompt vault and does not contradict the current repo by itself, so it remains in place as a future-work artifact rather than an active architecture document.
- [2026-09-18] Step 4: reran the frontend/scripts/benchmarks dead-code sweep with `node_modules`, `.next`, build output, and cache directories excluded. It found only heuristic zero-reference exports and three standalone script candidates; no high-confidence deletion was justified, so no code was removed.
- [2026-09-18] Step 5: attempted live-stack validation with `./local-status` and `./local-smoke`. Docker was unreachable (`failed to connect to the Docker API`), and the smoke test returned `FAIL: <urlopen error [Errno 61] Connection refused>`. Live Postgres/Redis/HAProxy integration remains unverified until the Docker daemon and Compose stack are available.
- [2026-09-18] Step 5 rerun after Docker became available: `./local-status` reached Docker but reported that `edge-nginx` is not running; `./local-smoke` again returned `FAIL: <urlopen error [Errno 61] Connection refused>`. Live integration remains unverified because the Compose proxy service is still down.
- [2026-09-18] Step 6: inspected and ran `python3 benchmarks/run_experiments.py`. The current runner supports only `baseline_round_robin` (there is no B1-B4 CLI selector), and the run could not inject its gray fault because Compose reported `service "demo-backend-a" is not running`; no benchmark CSV or measurements were produced.
- [2026-09-18] Step 7: added `benchmarks/extract_mttd_shadow_vs_rules.sql`, initially joining `lab_faults.applied_at`, `incidents.opened_at`, classification evidence, and observation windows. A later trace of `ControlWorker._observe()` corrected the shadow source to pre-incident `ObservationWindow.metrics.fast_path_recommendations`; see Step 9. PostgreSQL execution remains pending while the Compose database/proxy services are down.
- [2026-09-18] Step 8: reconciled the IEEE draft implementation-status block with shipped code. It now identifies the runner's three actual scenarios, states that B1-B4 baseline ablations are not implemented or executed, links the new MTTD query, and distinguishes persisted shadow evidence from true pre-incident MTTD. Validation found no stale status claim or whitespace error.
- [2026-09-18] Step 9: corrected the MTTD query after tracing `ControlWorker._observe()`: pre-incident `fast_path_recommendations` are persisted in `ObservationWindow.metrics`, so a separate shadow-event ledger is not required for this extraction. Updated the IEEE status accordingly; structural validation and `git diff --check` passed.
- [2026-09-18] Step 10: ran `./local-up`. Images built successfully and the core lab services became healthy, including Postgres, Redis, control API, control worker, all three demo backends, HAProxy, Prometheus, and `edge-nginx`. The wrapper did not declare the stack semantically healthy within 180 seconds because Kibana remained in `Restarting (1)`; smoke validation is the next step.
- [2026-09-18] Step 11: reran `./local-smoke` against the started stack. Authentication and independent LAB ground-truth application passed, but the test timed out waiting for a real `ROUTE_INSTANCE_FAILURE` incident (`last observation: None`). Live incident persistence remains unresolved; no broader safety suite was run in this step.
- [2026-09-18] Step 12: diagnosed the smoke failure from `control-worker` logs. Every worker loop raises `ValueError: capacity must satisfy total >= 1 and 0 <= active <= total`: `_observe()` counts active route memberships across all routes (12) but passes `len(INSTANCES)` (3) as total capacity. The worker therefore never reaches classification or incident persistence. No code patch was applied in this diagnostic step.
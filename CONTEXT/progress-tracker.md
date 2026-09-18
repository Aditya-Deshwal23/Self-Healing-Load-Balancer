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
- Fixed `_observe()` fast-path capacity to be computed per sampled
  route and verified the full 40-test control API suite in Compose
  with secrets and database access available
- Verified the live flagship fault path end to end after fixing the
  demo backend route-fault `UnboundLocalError`: incident persistence,
  route-local quarantine, sibling-route preservation, reintegration,
  and resolution all pass
- Reviewed HLD/LLD against design docs 06–08; retained both because
  they contain unique operational, security, runtime, RCA, and
  resource-envelope detail. Restored `PATENT_DISCLOSURE.md` in place
  with the required human-judgment note and found no links to the
  four old pre-archive architecture paths
- Added and verified a generalized `AUTH_INST_A_FAILURE` LAB scenario;
  route-instance certificate/action/verification now use the classified
  route and instance instead of checkout/inst-b hardcoding
- Completed the clean-state test proof bundle: 40 control API tests,
  the full live safety scenario suite, and the flagship end-to-end
  smoke test all passed in order
- Created `docs/DEMO_SCRIPT.md` from measured live evidence only,
  including the three fault scenarios, timings, MTTD query rows,
  sustained-load observations, exact startup/reset commands, and the
  final proof bundle
- Final verification complete: `./local-status` showed all 11 default
  services running with core health checks green, and the final unit,
  safety, and smoke proof bundle passed again in order

## In Progress

- None — Phase 1 code is written and unit-tested in isolation; not
  yet run against the live Compose stack

## Next Up

- Make Elasticsearch, Logstash, and Kibana optional in Compose and
  update `wait_for_stack()` to the measured default service count
- Review HLD/LLD against design docs 06–08, restore the live patent
  disclosure note, and check archived-document links
- No remaining Step 8 verification work; the measured MTTD query still
  has null shadow timing/signal columns and pytest reports one harmless
  read-only cache warning
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
- [2026-09-18] Step 1: fixed `_observe()` so fast-path capacity and 5xx error rate are computed per sampled route; `python3 -m py_compile src/shlb_api/worker.py` passed and the old global capacity variable has no remaining `_observe()` reference. Required `cd control-api && pytest` and equivalent `python3 -m pytest` could not run because this environment has neither the `pytest` executable nor the `pytest` module.
- [2026-09-18] Step 1 completion: after installing the already-pinned local test dependencies, host pytest reached 35 passed and 5 environment-bound database failures because Compose secrets are container-only; the required full suite then passed in the healthy `control-api` container: 40 passed, 1 read-only pytest-cache warning.
- [2026-09-18] Step 2: measured 14 default Compose services before profiling ELK and 11 after adding `observability-full` profiles to Elasticsearch, Logstash, and Kibana; aligned `wait_for_stack()` to `seen>=11`. Removed the stale profiled containers during `local-up` teardown, removed mandatory Logstash startup targets from HAProxy/Nginx, and verified `./local-up` from a clean launch: all 11 default services started healthy and printed `Local LAB is ready: https://192.168.0.101:8443`.
- [2026-09-18] Step 3: `./local-smoke` initially exposed a live backend bug: route faults raised `UnboundLocalError` before recording 503 metrics because `gray` was initialized only in the probe branch. Initialized it for normal route requests, rebuilt all demo backends, and reran smoke successfully: real `ROUTE_INSTANCE_FAILURE`, durable route-local action, unaffected sibling traffic, full reintegration, and resolution all passed. The live MTTD query returned two rows: the failed pre-fix attempt was `UNKNOWN` at `20.202928s`; the corrected run was `ROUTE_INSTANCE_FAILURE` at `3.679867s`. Both rows had null shadow timing/signal columns.
- [2026-09-18] Step 4: HLD/LLD were compared with design docs 06–08 and retained because they provide unique detail rather than substantial duplication. Added the required dated status line to `docs/research/PATENT_DISCLOSURE.md`. Exact searches for the old `docs/architecture/FRICTIONLESS_ONBOARDING.md`, `MERMAID_DIAGRAMS.md`, `INTERACTIVE_DEMO_MODE.md`, and `PROMPT_VAULT.md` paths returned no links; `git diff --check` passed.
- [2026-09-18] Step 5: added the real `AUTH_INST_A_FAILURE` scenario contract and fixed remaining route-instance actuation/verification hardcoding in `worker.py`. Under the live traffic generator, corrected auth/inst-a detection took 8.192s from request (6.074s active-to-incident), quarantined exactly `be_auth/srv_inst_a`, preserved other inst-a routes, passed the 66.7% remaining-capacity / 50% reserve gate, and reintegrated to `HEALTHY`. `SHARED_CHECKOUT_FAILURE` detection took 8.083s (6.050s active-to-incident), produced `SHARED_ROUTE_FAILURE` with all three checkout cells at 100% errors, `safety_inputs.evaluated=false`, `NO_ACTION`, no new actions, and all memberships remained ready; cleanup resolved it. Traffic-generator output captured real 10-second windows with auth/checkout 5xx during faults and normal 2xx windows afterward.
- [2026-09-18] Step 6: the first combined run passed unit tests (40 passed) but safety activation timed out because the worker coordination lease was stale and prior desired state left three inst-b memberships drained. Cleared the operational lease, used the supported `./local-reset` to restore clean seeded state, and reran the exact bundle successfully: `docker compose exec -T control-api pytest` 40 passed, `python3 scripts/test_safety_scenarios.py` completed all UNKNOWN/shared-route/instance-down checks and recovery, and `./local-smoke` completed the flagship route-instance journey end to end.
- [2026-09-18] Step 7: created `docs/DEMO_SCRIPT.md` using only measured values from the live demonstrations and proof bundle: 8.192s auth/inst-a detection, 8.083s shared-route detection, 3.679867s corrected flagship rule MTTD, 20.202928s pre-fix UNKNOWN MTTD, the 66.7% capacity-gate result, non-actionable shared-route evidence, sustained 10-second traffic windows, exact `./local-up`/`./local-reset` commands, and reset guidance. Placeholder scan and `git diff --check` passed.
- [2026-09-18] Step 8: `./local-status` showed all 11 default services running; control API, worker, backends, edge Nginx, Postgres, Prometheus, Redis, and HAProxy were healthy. The final ordered proof rerun passed: control API `40 passed` with one read-only pytest-cache warning, the full safety scenario suite passed, and `./local-smoke` completed the flagship journey end to end. Remaining measured limitation: the two MTTD query rows have null shadow timing/signal columns.
- [2026-09-18] Step 1: verified the pushed checkout still had hardcoded `checkout/inst-b` verification in `_advance_reintegration()`, replaced it with the action-derived `backend/server` key matching `worker_io.py`, and confirmed only the three intentional `_fault_targets()` literals remain. `worker.py` compiled and `git diff --check` passed. Live Compose proof with `AUTH_INST_A_FAILURE` produced `ROUTE_INSTANCE_FAILURE` and a `ROUTE_MEMBERSHIP_QUARANTINE` targeting `be_auth/srv_inst_a`; readback was `DRAIN` on that target while `be_public/srv_inst_a`, `be_catalog/srv_inst_a`, and `be_checkout/srv_inst_a` stayed ready. The auth action reintegrated to `COMPLETED`/`HEALTHY` and the final `auth/inst-a` matrix cell returned ready/100 with zero errors. The API rejected simultaneous active faults with 409, so the prior checkout fault was cleared through the supported API and its stale evidence remained persisted; no `local-reset` was used.
- [2026-09-18] Step 2: reproduced the stale-lease restart failure: after stopping `control-worker` while preserving its Redis lease, the old image repeatedly crashed with `RuntimeError: another worker holds the Redis coordination lease`. Updated `_acquire_lease()` to back off/retry, classify the owner from `ControllerGeneration.status` and `last_heartbeat_at`, and atomically reclaim only a provably stale owner; live workers remain protected by the PostgreSQL advisory lock. Rebuilt and reran the reproduction without Redis `DEL`: the worker logged `worker_coordination_lease_reclaimed`, generation 4 became `STALE`, generation 5 became `ACTIVE`, Redis held the new owner with TTL 10, and `local-status` reported `control-worker` healthy.
- [2026-09-18] Step 3: traced reintegration to mutable `DesiredRouteState` snapshots and found the final `HEALTHY` transition hardcoded weight `100` instead of restoring `RouteMembership.baseline_weight`/seed `ready`. A live kill during the `HEALTHY` window did not reproduce the previously claimed stuck-run failure after the Step 2 lease fix: the checkout run recovered to `COMPLETED`/`HEALTHY`, and the immediate second `AUTH_INST_A_FAILURE` also completed. Updated the final transition and resolution evidence to use the membership seed baseline. Rebuilt and ran `./local-smoke`, then immediately ran auth without `local-reset`; both completed with final `auth/inst-a` and `checkout/inst-b` ready/100 and no drained cells. `worker.py` compiled and `git diff --check` passed.
- [2026-09-18] Step 4: verified `GRAY_FAILURE_INST_A` was declared but not wired in the API target map and gray faults were ignored on the normal backend request path. Added the API mapping, sustained 500 ms normal-path latency, a 40% sub-`FAILURE_RATE` error signal, and healthy gray direct probes. Corrected fast-path telemetry to use HAProxy total-session/error deltas and real route-cell p95/error evidence, and updated the MTTD extract to preserve shadow-only faults, type the optional timestamp, and exclude unrelated incidents by target. Focused `test_worker_io.py` passed 4 tests. The live 45-second gray run produced a persisted weight-20 shadow recommendation with `shadow_mttd_seconds=5.537007`, `mttd_rules_seconds=NULL`, no destructive rule action, and no drained memberships.
- [2026-09-18] Step 5: reconciled the listed presentation documents against `docs/DEMO_SCRIPT.md`, shipped configuration, and measured tracker values. Corrected stale `Phase 2` labels to Phase 1/HYBRID_SHADOW and noted the measured auth/inst-a and gray-failure proof paths in the presentation script, slide content, and speaker notes. No other presentation architecture, port, ELK, scrape-interval, restart-policy, staged-weight, or test claims contradicted the repository. `presentation/demo_steps.md` and `docs/DEMO_SCRIPT.md` overlap on the flagship flow but each has unique content; recommend `docs/DEMO_SCRIPT.md` as the eventual single source of truth because it carries measured evidence, but no merge was executed.
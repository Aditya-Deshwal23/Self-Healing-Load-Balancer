# SHLB 2026 Phased Execution Plan

Each increment is intentionally pull-request sized and changes no more than
three to five files. A phase is not complete until its reproducible checks
pass and its safety invariants are recorded.

## Phase 1A — Runtime security boundary and frontend contract

**Objective and target files:** `docker-compose.yml`,
`haproxy/haproxy.cfg`, `nginx/nginx.conf`, `observability/logstash.conf`,
`frontend/lib/use-control-plane.tsx`.

**Specification:** remove Docker Engine access; use HAProxy Runtime IPC only;
use Docker DNS through HAProxy resolvers; keep ELK internal; retain strict
memory/JVM budgets; move the edge redirect binding to host port 8081. The
frontend must expose explicit live, reconnecting, and offline states.

**Definition of done:** `docker compose config --quiet`; assert no
`docker.sock`, static observability IP, or public ELK port; start the profile
and verify Elasticsearch, Logstash, HAProxy, and Nginx health. The frontend
must show last-event age and no fixture fallback in live mode.

## Phase 1B — Runtime command safety

**Objective and target files:** `control-api/src/shlb_api/worker.py`,
`control-api/src/shlb_api/worker_io.py`, `control-api/tests/test_worker_policy.py`.

**Specification:** enforce an allow-list for runtime commands, bounded socket
timeouts, absolute desired state, and readback equality before committing.

**Definition of done:** unit tests reject newline injection, unknown
backend/server pairs, and stale readback; accepted drain/weight changes are
idempotent.

## Phase 1C — Forensic evidence adapter

**Objective and target files:** worker evidence module, settings, and focused
tests (maximum three files).

**Specification:** query bounded Elasticsearch windows and Prometheus samples;
normalize evidence by observation-window ID; classify gray failures only when
proxy, metric, and semantic-log signals meet quorum.

**Definition of done:** replayed out-of-order evidence produces the same
classification; empty or timed-out evidence produces no destructive action.

## Phase 2A — Live observability frontend foundation

**Objective and target files:** `frontend/features/overview/live-command-center.tsx`,
`frontend/features/traffic/live-matrix.tsx`, `frontend/components/ui.tsx`,
`frontend/lib/api/operations.ts`.

**Specification:** add accessible loading/error/empty states, stale-data badges,
event-age indicators, route/instance filtering, and explicit evidence freshness
without changing API contracts or introducing fabricated values.

**Definition of done:** unit tests cover unavailable, stale, empty, and active
incident states; accessibility tests pass; live dashboard renders only API
data in live mode.

## Phase 2B — Frontend decision trace

**Objective and target files:** `frontend/features/actions/live-actions.tsx`,
`frontend/components/decision-trace.tsx`, and focused tests.

**Specification:** expose evidence quorum, blast-radius calculation, command
acknowledgement, readback, verification, rollback, and recovery as a
keyboard-accessible timeline.

**Definition of done:** a fixture-backed contract test renders every lifecycle
state and never labels an unconfirmed action successful.

## Phase 2C — Predictive anomaly scoring

**Objective and target files:** worker scoring module, settings, focused tests.

**Specification:** implement bounded rolling baselines for p99 latency, error
rate, queue depth, and semantic anomaly density. Scores recommend scope but
cannot bypass deterministic safety policy.

**Definition of done:** replayed windows are deterministic, bounded, and
produce no action for incomplete evidence.

## Phase 3A — Canary re-attestation

**Objective and target files:** worker recovery logic, persistence model,
recovery tests.

**Specification:** restore drained memberships through probe-gated stages
`PROBING -> 5% -> 20% -> 50% -> 100%`, with rollback to the last confirmed
stage on failed evidence.

**Definition of done:** a failed canary leaves the node drained; successful
stages are durable, idempotent, and visible in the frontend.

## Phase 3B — Evaluation harness

**Objective and target files:** benchmark runner, experiment configuration,
results schema.

**Specification:** measure attenuation precision, recovery latency, active
connection preservation, blast-radius violations, and memory under bounded
fault injection.

**Definition of done:** a reproducible run emits versioned raw results and
confidence intervals without synthetic success paths.

## Rules of Engagement

Use the exact trigger `Commence Phase 1A` (or another phase identifier) to
request implementation of one phase. The executor must touch only that phase's
target files, run its definition-of-done checks, and stop before the next
phase. No mocks, placeholder handlers, or untracked architectural jumps are
permitted.

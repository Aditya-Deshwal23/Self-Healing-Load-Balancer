# Failure points and countermeasures

This table records **52 points**. It deliberately separates things actually
observed while debugging this project from failure modes the implementation or
design is intended to prevent. A guardrail entry is not a claim that the
failure occurred in production. Status on observed entries reflects the last
inspection recorded in the project debugging history; unresolved items need a
fresh live check before closure.

## Observed issues and debugging findings

| # | Kind | Failure point / symptom | Countermeasure or response | Status |
|---:|---|---|---|---|
| 1 | Observed | Fault Lab initially displayed “execution API is intentionally absent,” so confirmation could not apply a fault. | Added the authenticated LAB fault-create/clear API and worker-to-backend fault-control path; the API now accepts requests asynchronously and records them. | Implemented in current source; a clean end-to-end run still needs a clean operational state. |
| 2 | Observed | The original fault selection felt like one fixed scenario rather than a reusable payload library. | Added ten named fault scenarios in the Fault Lab catalog, each with target, duration, expected classification, and recovery behavior. | Implemented in current frontend. |
| 3 | Observed | Previously supplied payloads did not match what the project could submit. | Checked all ten current UI request objects against `LabFaultCreate`; all ten passed schema validation. | Schema-valid; not all ten were injected end to end. |
| 4 | Observed | “Payload works” was conflated with “controller must act.” | Documented that shared-route, gray-failure, and unknown-conflict scenarios are deliberately non-actionable or advisory-only. | Clarified; expected no-action results are intentional. |
| 5 | Observed | The user was viewing an incident page while looking for payload browsing/injection controls. | Pointed to the Lab route in the console navigation; payload browsing belongs in Fault Lab, while incident detail shows the resulting evidence. | Navigation clarified. |
| 6 | Observed | Decision Trace did not show a fresh classification for later faults. | Traced the worker’s active-incident early return: an unresolved `NEEDS_REVIEW` incident blocks another classification cycle. | Open in the last observed state; reconcile the existing incident first. |
| 7 | Observed | A checkout incident and recovery remained in `NEEDS_REVIEW`. | The worker keeps ambiguous or failed recovery in review instead of claiming success; operator reconciliation is required. | Open in the last observed state. |
| 8 | Observed | The running worker container was older than the checked-in worker source. | Rebuilt and recreated only `control-worker`, then checked that its health state and heartbeat were fresh. | Mitigated; it was healthy after recreation. |
| 9 | Observed | Older worker logs contained HAProxy Runtime timeout/connection-refused errors. | Rechecked the Runtime socket from the worker after the socket mount was recreated; `show info` succeeded. | Historical/transient issue; no fresh full fault run was performed. |
| 10 | Observed | A prior `P02_AUTH_A` record was `CLEARED` but had no applied timestamp. | Treat request, application, and clearing as separate lifecycle events; do not call it an applied payload without `applied_at`. | Unresolved for that historical record. |
| 11 | Observed | Checkout × `inst-b` desired state was `drain/0`, while HAProxy readback was `ready/100`. | Surface desired/observed drift and block verification/recovery from claiming alignment. | Open in the last observed state; needs reconciliation. |
| 12 | Observed | One recovery record showed retry count 3 against a configured maximum of 2. | Bounded retry policy exists; the inconsistent persisted run must be reviewed rather than silently advanced. | Open data/state inconsistency in the last observed record. |
| 13 | Observed | Recovery probes passed, but the 5% canary stage failed and moved the run to review. | Keep traffic from advancing when request evidence fails even if probes pass; inspect the canary samples before retrying. | Fail-closed behavior worked; recovery remains unresolved. |
| 14 | Observed | The failed 5% stage recorded 25 samples and a 68% error rate shortly after the injected fault expired. | Compared stage and fault timestamps with policy timing. A 12-second observation window and 3-second cooldown may allow tail failures into the canary window. | Likely timing interaction, not yet proven; tune/verify before retry. |
| 15 | Observed | The user expected a separate HAProxy website/admin page for proof. | The Overview links to HAProxy stats only when opened from a loopback URL; on a remote dashboard it explains that stats are host-local. HAProxy stats/runtime stay private. | A remote console still cannot use the local link; use an approved authenticated management path if remote stats access is needed. |
| 16 | Observed | The user reported Docker demo backends 1, 2, and 3 showing errors. | Preserve this as a reported symptom and inspect per-container health/logs before attributing a cause; no verified root cause was established in the last review. | Unconfirmed/open. |
| 17 | Observed | Historical payload records included both applied and failed/pending outcomes, which made the catalog look unreliable. | Use persisted `status`, `applied_at`, `cleared_at`, and ground-truth ID as the request record; schema acceptance alone is not proof of backend application. | Partially explained; historical failures still need per-record reconciliation. |

## Failure modes the code/design counters

| # | Kind | Failure point / symptom | Countermeasure or response | Status |
|---:|---|---|---|---|
| 18 | Guardrail | Missing telemetry could be mistaken for a healthy backend. | Enforce evidence completeness and require sufficient observations; incomplete evidence classifies as `UNKNOWN`, not healthy/actionable. | Implemented in classifier and policy tests. |
| 19 | Guardrail | Conflicting probes and metrics could produce a confident but wrong classification. | Conflicts are explicit evidence; conflict results in `UNKNOWN` and no automatic destructive action. | Implemented and covered by worker-policy tests. |
| 20 | Guardrail | One failing route could be mistaken for a whole-instance outage. | Compare the same physical instance across its other registered routes and compare route peers before selecting scope. | Implemented for supported classes. |
| 21 | Guardrail | One failed instance could be mistaken for a shared route/dependency failure. | Compare the target route across all instances; classify shared-route failures separately and prohibit mass ejection. | Implemented and tested as non-actionable. |
| 22 | Guardrail | Ambiguous or unknown failure could trigger an automatic quarantine. | `UNKNOWN` is non-actionable; retain evidence for review rather than mutate HAProxy. | Implemented in classifier. |
| 23 | Guardrail | Gray failure can evade binary health checks or create noisy false positives. | Keep the statistical gray-failure signal advisory-only; it cannot override deterministic rules or independently authorize mutation. | Implemented as a shadow signal. |
| 24 | Guardrail | Shared physical capacity could be counted multiple times because one instance appears in several route pools. | Count unique physical instances once when calculating remaining capacity. | Implemented and covered by policy tests. |
| 25 | Guardrail | Draining a member could overload its remaining peers. | Require a physical-capacity reserve and enforce peer-queue limits before allowing a quarantine. | Implemented in capacity policy. |
| 26 | Guardrail | Missing peer/queue evidence could make a drain appear safe. | Reject the action when a route peer is missing or queue evidence exceeds bounds. | Implemented and covered by policy tests. |
| 27 | Guardrail | A controller could choose a broader target than the evidence supports. | Enumerate predeclared route memberships and select the smallest supported scope; record competing scopes and rejection reasons in the decision trace. | Implemented in worker decision path. |
| 28 | Guardrail | An API bug or compromise could directly mutate HAProxy. | Keep HAProxy Runtime socket access on the worker only; the API has no Runtime mount/access. | Implemented through Compose network and mount boundaries. |
| 29 | Guardrail | Two workers could concurrently mutate the same HAProxy. | Use a PostgreSQL advisory lock and bounded Redis lease, while physically giving the Runtime socket to one worker service. | Implemented; single-writer boundary is the decisive control. |
| 30 | Guardrail | A crash could occur after the decision but before action intent is durable. | Persist a `PREPARED` action, prior state, requested state, evidence, and rollback plan before issuing Runtime mutation. | Implemented in the action lifecycle. |
| 31 | Guardrail | Runtime command succeeds but its acknowledgment is lost, leading to a duplicate write. | Read HAProxy state after ambiguous results; record `RESULT_UNKNOWN`/review rather than blindly retrying. | Documented and implemented in action reconciliation. |
| 32 | Guardrail | HAProxy accepts a command but applies a different state than requested. | Confirm the exact backend/server state through Runtime readback before marking the action applied. | Implemented in worker flow. |
| 33 | Guardrail | The UI could show desired state as if it were actual HAProxy state. | Display desired and observed state separately and mark mismatches as drift. | Implemented in matrix/operational views. |
| 34 | Guardrail | HAProxy counter reset could produce negative error/latency deltas. | Discard reset deltas instead of reporting negative rates as real measurements. | Implemented and covered by worker I/O tests. |
| 35 | Guardrail | Missing HAProxy statistic fields could be interpreted as zero. | Preserve unavailable values as `None`/unknown, not zero-valued success evidence. | Implemented and covered by worker I/O tests. |
| 36 | Guardrail | A quiet route with zero requests could be called healthy or recovered. | Treat zero samples as insufficient evidence; require configured minimum real samples for verification. | Implemented in verification policy. |
| 37 | Guardrail | Late samples from an older observation window could contaminate a later retry. | Seal evidence windows; use the active window for decisions and retain late evidence only for audit. | Defined as an algorithmic invariant. |
| 38 | Guardrail | Statistical/ML recommendations could become an unauthorized mutation path. | Statistical support is attached to evidence but does not change deterministic actionability; no model gets control authority. | Implemented for the shadow signal; broader AI remains outside the control path. |
| 39 | Guardrail | Recovery could skip from quarantine directly to full traffic. | Use monotonic `PROBING → 5% → 20% → 50% → 100% → HEALTHY` stages. | Implemented in recovery policy. |
| 40 | Guardrail | A probe-only success could restore traffic despite failed real requests. | Gate each stage on request sample/error evidence, direct probes, and HAProxy state readback. | Implemented in recovery stage checks. |
| 41 | Guardrail | A failed recovery stage could silently restore the failed member. | Keep the last verified reduced/drained state and move to review when verification fails. | Implemented as fail-closed recovery behavior. |
| 42 | Guardrail | Recovery could retry forever and flap traffic. | Set a maximum reintegration retry count and bounded cooldown. | Implemented; the observed retry-count mismatch still needs reconciliation. |
| 43 | Guardrail | A backend could be reintroduced before all of its routes are healthy. | For instance recovery, require every registered route probe to pass repeatedly before reintegration. | Implemented for instance-level recovery. |
| 44 | Guardrail | A test fault could remain active after the operator leaves the page. | Store an expiry and use automatic cleanup/watchdog behavior; allow an authenticated explicit clear. | Implemented in LAB fault lifecycle. |
| 45 | Guardrail | A payload could target an arbitrary public website/backend. | Restrict injection to the registered synthetic LAB backends and private control surface; do not treat arbitrary web URLs as targets. | Implemented by environment and network boundaries. |
| 46 | Guardrail | A payload could request an unbounded duration. | Validate fault duration within the API’s bounded 5–600 second range. | Implemented in request schema. |
| 47 | Guardrail | An unauthorized user or cross-site request could inject/clear faults. | Require authenticated role, CSRF token, allowed Origin, and environment scope on mutations. | Implemented in API dependencies/routes. |
| 48 | Guardrail | A retried browser request could create duplicate faults/actions. | Require an idempotency key and return the original mutation outcome for duplicate requests. | Implemented in write contract. |
| 49 | Guardrail | A stale page could clear a fault after its record changed. | Require `If-Match`/entity version for clear operations and reject stale writes. | Implemented in clear endpoint contract. |
| 50 | Guardrail | A user could read or mutate another project’s records by changing an ID. | Scope database/API access to authorized project/environment; use not-found responses for denied scope. | Implemented in API access pattern. |
| 51 | Guardrail | Dropped/expired SSE events could leave the console showing stale state. | Use bounded Redis event cursors; on cursor expiry send `resync_required` and reload authorized REST state. | Implemented in event flow. |
| 52 | Guardrail | Demo fixtures could be mistaken for live backend evidence. | Keep ordinary LAB mode on real API data; expose fixtures only under explicit demo mode with a persistent simulated-data notice. | Implemented in frontend. |

## Source files used

- [Fault Lab catalog](../frontend/features/lab/live-fault-lab.tsx)
- [API schemas](../control-api/src/shlb_api/schemas.py)
- [Operations and LAB fault endpoints](../control-api/src/shlb_api/routers/operations.py)
- [Control worker](../control-api/src/shlb_api/worker.py)
- [Worker classification and safety policy](../control-api/src/shlb_api/worker_policy.py)
- [HAProxy Runtime adapter](../control-api/src/shlb_api/worker_io.py)
- [Project runbook](../README.md)
- [Risk register](design/20_RISK_REGISTER_AND_DECISION_LOG.md)
- [Algorithmic invariants](research/ALGORITHMIC_INVARIANTS.md)

## Historical observations to recheck after future failures

An earlier live-state inspection recorded checkout × `inst-b` desired/observed
drift, a recovery in `NEEDS_REVIEW`, a retry-count mismatch, and a fault without
an application timestamp. A later verified LAB baseline reset completed and
the containers were healthy, so those entries describe historical findings,
not a claim that they are still active. The reported errors in all three demo
backends were not independently diagnosed at that time. Recheck current
container health and persisted state whenever a new failure is reported; run a
new payload batch only after any active recovery or drift is reconciled.

## HTTP 5xx observation and route protection

The demo backend records each application response with its exact HTTP status,
registered route, backend instance, path without query parameters, request ID,
latency, and a stable failure fingerprint. It exposes bounded-cardinality
Prometheus counters by route, instance, and status code; request IDs are kept in
structured backend logs rather than Prometheus labels.

The worker evaluates a rolling 12-second evidence window every half-second.
Those repeated snapshots overlap, so the controller now requires the same
incident class and scope in two consecutive, non-overlapping windows before it
records a scoped incident or considers a routing action. This applies to
degraded warnings and stronger route, shared-route, and instance failure
classes. A direct `UNKNOWN_CONFLICT` remains visible immediately for manual
review, but never authorizes a routing mutation. Non-action incidents also
need two consecutive, non-overlapping healthy windows before they are closed,
which prevents a short healthy blip from hiding a continuing fault.

Sustained 5xx above the 10% healthy bound needs at least six real samples and
two errors in each window before it can support a non-actuating
`ROUTE_INSTANCE_DEGRADED` incident. A failed direct probe can also support a
warning after six request samples, but it must fail in both independent
windows. Decision Trace retains the opening evidence and links every later
classification revision to its own saved window. Strong isolated failure still
needs at least 50% errors, six target samples, a failed target probe, healthy
same-route peers, healthy sibling routes, and a passing capacity/queue check.
Only then can the controller drain that route/backend, confirm HAProxy
readback, verify affected and preserved traffic, and start probe-gated staged
reintegration after the fault clears. Shared-route failures do not cause mass
ejection.

Gray-failure LAB scenarios are intentionally low-rate (2.5%) and observe-only;
their individual 500s are counted and logged, but do not meet the sustained
degradation or quarantine thresholds by themselves. The HAProxy stats shortcut
is usable from the control host’s loopback dashboard only; it is disabled on a
remote dashboard because that browser's `localhost` would point at the user's
own machine.

# Final Product Specification

## 1. Identity

**Project title:** Self Healing Load Balancer

**One-sentence definition:** An out-of-band reliability controller that converts route-, instance-, and version-resolved traffic evidence into the least disruptive safe HAProxy routing intervention, verifies its effect, and reversibly restores capacity.

## 2. Exact technical problem

Binary instance health conflates several materially different conditions: a dead process, a slow but reachable instance, one broken route on one instance, one route broken across all instances, overload, and a faulty deployment cohort. Whole-instance ejection can discard healthy route capacity; blind retry can amplify shared failures; route-wide failover can spread a dependency failure; and premature re-entry can flap.

The system must infer only the *traffic-relevant failure scope* supported by observable evidence and choose a HAProxy-expressible action that minimizes unnecessary removal without violating remaining-capacity, retry-safety, or rollback constraints.

It does not promise causal root-cause diagnosis. “Likely dependency-related” is permitted only as a qualified developer check, not as a controller fact.

## 3. Exact research gap

Established systems separately provide request-specific health models, host outlier ejection, route pools, capacity thresholds, retries/circuit breakers, canary analysis, and adaptive remediation. The applied research gap addressed here is narrower:

> There is limited open, reproducible evaluation of a commodity HAProxy controller that uses cross-route and cross-instance control comparisons to constrain the admissible routing scope, selects the least-blast-radius safe action, and verifies both symptom improvement and preservation of unaffected route capacity under a common fault matrix.

This is a reproducibility and integration gap, not a claim that no commercial or patented system has ever combined similar ideas.

## 4. Exact patent-exploration nucleus

**Evidence-Bounded Minimum-Scope Healing (EBMSH)** consists of the following inseparable procedure:

1. Build a failure-support matrix keyed by route group, physical instance, and deployment version from synchronized observation windows.
2. Generate an evidence certificate containing cross-controls: target versus same-route peers, target versus other routes on the same instance, version cohort versus stable cohort, provenance, conflicts, and completeness.
3. Enumerate HAProxy-expressible routing units and reject any unit whose asserted scope lacks sufficient evidence or whose action would violate configured safety invariants.
4. Select the admissible action with the minimum blast-radius cost—not merely the smallest label in an enum.
5. Persist the exact prior desired and observed state and apply an idempotent, bounded routing change through the physically isolated single writer, with a current controller generation.
6. Verify the predicted change on the affected cohort and a preservation invariant on disjoint unaffected cohorts.
7. Commit, restore the snapshot, or enter review; later reintroduce traffic only when stage-specific evidence is sufficient.

This is a patent-exploration candidate only. The prior-art risk is medium-high.

## 5. Supporting mechanisms

1. **Multidimensional failure fingerprint:** privacy-minimized route × instance × version features, affected sets, error signature, time window, provenance, prior action, and completeness.
2. **Action safety envelope:** hard capacity, criticality, retry, conflict, cooldown, rollback, and operator-override constraints.
3. **Evidence-gated verification and reintegration:** sequential windows, minimum samples, synthetic probes for low traffic, hysteresis, and pause-on-missing-evidence behavior.

No other component is part of the proposed invention nucleus.

## 6. Failure taxonomy

The top-level class is exclusive; `scope_details` carries route IDs, instance IDs, version IDs, and overload scope.

| Class | Operational definition | Minimum support | Default automatic posture |
|---|---|---|---|
| `HEALTHY` | No actionable deviation after baseline, peer, and completeness checks. | Adequate data and no hard failure. | No change. |
| `INSTANCE_DOWN` | Physical endpoint is unreachable or fails direct/active checks across its route memberships. | Repeated direct probe failures plus HAProxy connection failures or equivalent hard evidence. | Drain/maintain all memberships if capacity permits. |
| `INSTANCE_DEGRADED` | One instance is consistently slower/error-prone across multiple routes while reachable. | Cross-route deviation from peers; no shared route pattern; adequate load. | Bounded whole-instance weight reduction, then verify. |
| `ROUTE_INSTANCE_FAILURE` | One route membership is abnormal; same route on peers and other routes on the same instance are healthy. | Both same-route peer and same-instance cross-route controls. | Reduce then drain only that membership. |
| `SHARED_ROUTE_FAILURE` | A route is abnormal across a configured quorum of otherwise healthy instances. | At least two instances, route prevalence threshold, other-route controls. | Suppress retries; rate/concurrency protect or fail fast. Never eject all instances for that route as if independent. |
| `TRAFFIC_OVERLOAD` | Queue, concurrency, request-rate, and/or resource saturation explains degradation better than a member-local fault. | Saturation signal plus demand/queue correlation; classification retains `route`, `service`, or `global` overload scope. | Load shed/rate/concurrency protect and suppress retries. |
| `VERSION_SPECIFIC_FAILURE` | A version cohort is abnormal relative to a stable cohort under comparable routes/load. | Version metadata, a control version, sufficient requests, preferably at least two instances in the suspect cohort. | Remove/downweight suspect version memberships only if stable capacity suffices. |
| `UNKNOWN` | Evidence is incomplete, conflicting, out of distribution, low confidence, or matches multiple scopes. | Any abstention condition. | No destructive automatic change; gather evidence or review. |

### Class precedence and ambiguity

Hard reachability failure takes precedence over statistical classes. A proven overload pattern takes precedence over generic degradation. Version-specific classification requires a reproducible cohort contrast and does not override an instance-down hard rule. Ties, contradictory scopes, or insufficient controls resolve to `UNKNOWN`; the resolver does not choose the more dramatic class.

## 7. Healing action vocabulary

| Action | Routing target | HAProxy expression | MVP |
|---|---|---|---|
| `NO_CHANGE` | none | none | Yes |
| `REQUIRE_REVIEW` | incident | controller state only | Yes |
| `SET_MEMBERSHIP_WEIGHT` | route × instance | Runtime API weight | Yes |
| `DRAIN_ROUTE_INSTANCE` | route × instance | Runtime API `state drain` | Yes |
| `SET_INSTANCE_WEIGHT` | all memberships of instance | repeated idempotent Runtime API weight sets | Yes |
| `DRAIN_INSTANCE` | all memberships of instance | repeated drain; `maint` only for confirmed down and explicit policy | Yes |
| `SUPPRESS_ROUTE_RETRIES` | route | predeclared map/policy switch; retries become zero | Yes |
| `ACTIVATE_ROUTE_RATE_LIMIT` | route | predeclared policy/map switch | Yes, lab-configured routes |
| `ACTIVATE_ROUTE_CONCURRENCY_LIMIT` | route memberships | predeclared server/request concurrency policy | Yes, bounded |
| `FAIL_FAST_ROUTE` | complete route | predeclared map selects static error backend | Yes, policy-gated |
| `DRAIN_VERSION_GROUP` | memberships with version | idempotent multi-membership drain/weight saga | Yes |
| `ADVANCE_REINTEGRATION` | prior target | 5/20/50/100% default weights | Yes |
| `PAUSE_REINTEGRATION` | prior target | keep current desired weight | Yes |
| `ROLL_BACK_REINTEGRATION` | prior target | return to last verified stage/quarantine | Yes |
| `GLOBAL_TRAFFIC_POLICY` | all routes | only a predeclared emergency policy | Later/manual by default |

Automatic creation of HAProxy ACLs/backends during an incident is prohibited in MVP. Structural configuration is an administrative workflow.

## 8. Minimum viable product

The exact MVP includes:

- four configured route groups: `/public`, `/auth`, `/catalog`, `/checkout`;
- three or more demo backend instances with version labels;
- NGINX TLS/public ingress and HAProxy L7 routing;
- independent logical HAProxy membership per route × instance;
- Prometheus metrics, HAProxy exporter, structured proxy/application logs, and direct synthetic probes;
- PostgreSQL desired state, incidents, classifications, actions, attempts, verification, audit, and experiment metadata;
- Redis locks/caches/SSE streams, but no durable truth held only in Redis;
- rules-only classifier supporting all eight top-level classes in controlled scenarios;
- Logistic Regression and calibrated Random Forest offline evaluation; model actuation remains feature-gated;
- deterministic safety engine and retry policy;
- single-writer reconciliation worker;
- durable route-instance, instance, route-policy, and version-group actions;
- post-action verification and staged reintegration;
- Command Center, matrix, incidents, Decision Trace, actions, reintegration, policies, Fault Lab, experiments, metrics, logs, and settings screens;
- ELK and Ollama as optional profiles;
- fault injection and the four required research baselines.

## 9. Stretch scope

- non-overlapping concurrent actions after formal conflict testing;
- adaptive diagnostic probes selected for uncertainty reduction;
- statistical sequential verification beyond fixed Wilson/threshold rules;
- action-outcome memory used only to recommend thresholds, not self-modify policy;
- OpenTelemetry tracing with customer instrumentation;
- active-passive control worker with a local fenced actuator;
- additional route-group match forms beyond safe prefixes/templates;
- customer SSO/OIDC without making it mandatory.

## 10. Explicit non-goals

- Kubernetes, service mesh, scheduler, or orchestrator replacement;
- container/VM restart, autoscaling, code deployment, or deployment rollback;
- generic infrastructure remediation outside HAProxy routing;
- source-code analysis or exact root-cause claims;
- arbitrary service discovery from the public Internet;
- WAF, DDoS product, bot management, or generic API gateway;
- paid external LLM, monitoring, authentication, database, or cloud dependency;
- deep learning, reinforcement learning, or autonomous online model retraining;
- LLM-selected actions or LLM access to credentials/control APIs;
- exactly-once distributed actuation claims;
- active-active control-plane writers in MVP;
- public fault injection;
- full mobile administration.

## 11. Assumptions and invariants

### Technical assumptions

- HTTP/HTTPS L7 traffic with route groups that can be deterministically matched before backend selection.
- At least two backend instances for peer comparison; three are strongly recommended.
- Clock synchronization within two seconds across participating hosts.
- A stable instance identity independent of IP address, and explicit deployment-version metadata.
- HAProxy is the sole dynamic backend selector; NGINX does not independently retry across application backends.
- Route policies define criticality, capacity, timeouts, safe methods, and failure response.
- Direct probe connectivity exists on a management network.

### Safety invariants

1. The control plane never handles normal client requests.
2. No automatic capacity-removing action may take a critical route below its configured reserve.
3. No ML or LLM output can override retry or action safety rules.
4. `UNKNOWN` cannot trigger destructive automatic actuation.
5. Every applied action has a durable prior-state snapshot and idempotency key.
6. Missing telemetry cannot be interpreted as recovery.
7. Runtime state is observed after every command and reconstructed after restart.
8. An operator override wins over overlapping automation until it expires or is explicitly released.
9. One environment has one physical Runtime API writer in MVP.

## 12. Customer integration requirements

| Requirement | Why it is required | Degraded mode if absent |
|---|---|---|
| Stable project/environment/service/instance IDs | joins evidence and desired state safely | no automatic action |
| Route-group definitions and precedence | bounds telemetry cardinality and routing scope | instance-only health |
| Backend IP/port allowlist | safe registration and direct probing | manual registration only |
| Version label per instance | cohort comparison | no `VERSION_SPECIFIC_FAILURE` |
| HAProxy log fields: route, backend, server, timings, status, retry/termination flags, request ID | route-member observations | active checks only |
| Prometheus access to HAProxy/app/system metrics | windows, capacity, overload | lower completeness; rules only |
| Direct synthetic probe path per route group | recovery and low-traffic evidence | manual reintegration |
| Nominal capacity or safe max concurrency | safety envelope | conservative fixed reserve/manual review |
| Per-route criticality and failure response | chooses fail-fast/rate behavior | default critical; fewer actions |
| Per-route retry/idempotency contract | prevents duplicate side effects | retries disabled except GET/HEAD connection failures |
| Sanitized application error code (optional) | improves signature grouping | status/timing signature only |
| Clock sync | coherent observation windows | wider windows/lower confidence |

Customer application dependencies are observed only through allowed metrics or sanitized application signals. The controller does not receive database passwords or arbitrary dependency credentials.

## 13. Public URL-only limitations

With only a public URL, the system can measure aggregate availability and latency but usually cannot determine which physical instance served a request or force a probe to a specific route × instance cell. It therefore cannot safely distinguish:

- one faulty instance from a shared route failure;
- overload from backend degradation;
- a version regression from random instance variance;
- recovery from absence of traffic;
- retry-safe from side-effecting operations;
- remaining actual capacity.

URL-only mode is monitoring/demo-observer mode. It permits alerts and aggregate incidents, not automatic selective quarantine.

## 14. Controlled college-demo capabilities

The research environment may include deliberately instrumented demo applications and Toxiproxy. It can inject:

- process crash;
- instance-wide delay/error;
- `/checkout` failure on only instance B;
- `/checkout` dependency failure across all instances;
- controlled saturation and queue growth;
- version `v2` regression;
- periodic flapping;
- mixed unknown anomalies.

Fault controls are reachable only from the isolated research network, require a lab role and short-lived token, are disabled outside `LAB` environments, and never share the public ingress.

## 15. Production-style boundaries

- HAProxy Community and its Data Plane API are pinned to a tested compatible LTS pair; the initial target is HAProxy 3.2.x plus Data Plane API 3.2.x, reevaluated before implementation.
- Controller availability is not equivalent to data-plane HA. MVP uses a single controller writer and last-known-good HAProxy state.
- NGINX and HAProxy themselves require external process supervision; self-healing the load balancer process is outside product scope.
- Multi-machine mode separates public/data-plane, persistence, and observability networks but does not claim cloud-scale control-plane HA.
- The product supports one HAProxy data plane per environment in MVP. Federated multi-region traffic control is future work.
- Structural route changes require administrative approval and validated reload. Incident healing uses predeclared objects.
- The system provides decision evidence and reversible traffic actions; it does not guarantee application correctness or uninterrupted service under insufficient capacity.

## 16. Success criteria

The product is ready for research demonstration when all eight classes meet their lab acceptance criteria, duplicate and acknowledgment-loss action tests pass, a HAProxy restart reconstructs desired state, and the proposed controller is compared against all three baselines with preregistered metrics. It is ready for a customer pilot only after external security review, restore testing, workload-specific capacity calibration, and rules-only soak testing with automatic actuation disabled.

# Testing Strategy and Acceptance Criteria

## 1. Test objective

Testing must establish five properties independently:

1. normal requests continue when optional/control components fail;
2. classification and scope evidence are correct or explicitly unknown;
3. every routing mutation is authorized, bounded, idempotent, observed, reversible, and auditable;
4. scoped healing improves the affected technical symptom without discarding unrelated healthy capacity;
5. the published research measurements can be reproduced from independent ground truth.

Passing a classifier test does not imply an action is safe. Passing an HAProxy command test does not imply the controller chose the right scope. The suite preserves these boundaries.

## 2. Test environments

| Level | Environment | Real dependencies | Purpose |
|---|---|---|---|
| Unit | In-process, fixed clock/randomness | None; narrow fakes | Pure policy, fingerprint, state transition, validation |
| Component | Isolated container/module | PostgreSQL or Redis or HAProxy as relevant | Adapter/schema/locking semantics |
| Integration | Compact Compose | NGINX, HAProxy/DPA, API/worker, PG, Redis, Prometheus, demo apps | End-to-end control and request path |
| Fault lab | Full lab profile | Above plus Toxiproxy/load/fault harness | Failure classification/healing/recovery |
| Research | Frozen rig/manifests | Instrumented complete system | Statistical evaluation |
| Deployment/security | Fresh host/network namespace | Pinned production-style images | Isolation, upgrade, restore, exposure, smoke |

Unit tests may use an abstract HAProxy port; every operation also needs a real supported HAProxy/DPA compatibility test. Time-dependent tests use a controllable clock rather than sleeps. Tests never reach the public Internet.

## 3. Test data and oracles

- Factories create project-scoped routes, physical instances, logical memberships, versions, policies, evidence windows, incidents, and actions with stable IDs.
- Golden fixtures contain canonical fingerprints and expected hashes after privacy normalization.
- Fault harness writes an independent truth ledger: scenario, exact target set, intensity, monotonic/UTC onset/end, and confirmed cleanup.
- HAProxy oracle reads complete Runtime state and rendered configuration; it does not trust the controller response.
- Request oracle records offered/admitted/backend-attempted/completed/rejected requests and application-level outcome signatures.
- Every randomized/property test records its seed. No real credentials, personal data, or production addresses enter fixtures.

## 4. Unit tests

### Domain and validation

- route pattern canonicalization rejects ambiguous, overlapping-without-priority, traversal, newline/control, raw directive, and unsupported regex forms;
- backend registration enforces allowlisted CIDR/port/scheme and normalized version/instance identity;
- policy validation catches impossible capacity floor, unsafe retry, empty target, duplicate membership, invalid stage order, and absent rollback strategy;
- project/environment authorization scopes every repository query and event;
- UTC timestamp, correlation ID, idempotency key, entity version, and pagination token validation.

### Fingerprint and evidence

- deterministic canonicalization independent of map/dictionary order;
- keyed signature hash stability inside an environment and unlinkability across environments;
- token/query/header/payload redaction; bounded cardinality and length;
- latency/error/peer/version features on exact window boundaries;
- completeness decays for missing, stale, skewed, and contradictory sources;
- affected-set inference and similarity with missing dimensions;
- conflict-resolution fixtures for route-local, instance-wide, shared-route, version, overload, and mixed evidence;
- expiry/repeated-failure/intervention-memory rules.

### Classification and confidence

- every deterministic hard rule and priority interaction;
- connection-refused/failed-probe cases cannot be overridden by ML;
- low capacity, unsafe retry, low completeness, active conflict, and failed reintegration force the documented gate;
- calibrated probability, rule evidence, completeness, and conflict combine exactly as specified;
- ties/low margin/out-of-distribution/missing features result in UNKNOWN or lower confidence;
- model exception, timeout, incompatible schema, or digest mismatch enters rules-only mode.

### Safety and target selection

- candidate target-set enumeration for each routing unit;
- evidence certificate support and counter-evidence rejection;
- residual capacity computed on unique physical capacity, not duplicated memberships;
- active quarantine, queue, criticality, cooldown, conflict, retry, generation, rollback, and override constraints;
- deterministic blast-radius cost and tie breaking;
- unexpressible smallest target either selects next evidence-supported safe unit or blocks—never silently broadens;
- UNKNOWN yields no automatic destructive action;
- property tests: selected target is expressible, evidence-supported, safety-valid, and no higher-cost valid candidate was skipped.

### Retry safety

- method × idempotency-key × route-policy matrix for GET/HEAD/PUT/POST/PATCH/DELETE;
- response-loss and timeout ambiguity suppress unsafe repeat;
- shared-route and overload detection suppress cross-instance retry;
- maximum one cross-instance retry in MVP and budget exhaustion;
- payment/order POST requires application deduplication contract and valid key;
- model/LLM suggestion cannot modify retry decision.

### State machines

- legal and illegal transitions for incident, action, verification, backend, and reintegration;
- expiry, pause, resume, rollback, manual review, supersession, maximum attempts;
- duplicate event/reordered event behaviour;
- adaptive cooldown/hysteresis monotonic bounds;
- audit event generated for every material transition.

## 5. Database tests

Run against the supported PostgreSQL version, not SQLite.

- migrations apply from empty schema and every supported prior migration checkpoint;
- migration lock prevents two migrators; failed migration leaves a recoverable state;
- foreign keys, uniqueness, check constraints, enums, and immutable identifiers match the ER model;
- optimistic version comparison rejects stale incident/action/policy update;
- transaction atomically stores action plan, rollback snapshot, evidence reference, and audit event;
- duplicate idempotency key returns the original resource without duplicate attempts;
- incident de-duplication under concurrent insert;
- row-level repository filters prevent cross-project reads/writes; authorization is also tested at API level;
- append-only audit permissions reject update/delete by application role and verify hash-chain continuity;
- retention deletion preserves required tombstone/hash and respects legal/research holds;
- query plans use required indexes for active incidents, actions, memberships, audit, and time-window retrieval at target data volume;
- logical backup restores relationships, desired generation, unfinished actions, audit chain, and report metadata.

## 6. Redis and concurrency tests

- lease acquire/renew/release with owner identity and expiry;
- fencing/generation counter is monotonic across restart and Redis reconnection;
- stale owner cannot submit an action after lease expiry/new generation;
- per-routing-domain lock serializes overlapping targets while disjoint read work continues;
- lock loss during apply forces result-unknown/reconciliation; it does not create a second socket writer;
- cooldown, deduplication, recent fingerprint, SSE cursor, and rate-counter TTLs;
- Redis eviction/restart does not delete durable desired/action truth;
- Redis outage transitions worker to safe mode and suppresses mutation/stage advancement;
- network partition/clock-skew simulations cover lease safety limits.

Because external HAProxy writes cannot carry a Redis fencing token, the decisive test is physical: only one worker process/container has the Runtime/DPA credential/socket. A test scans mounts/network policy and proves the API/second worker cannot connect.

## 7. HAProxy adapter and Data Plane tests

### Runtime operations

For `set server ... state/weight`, drain/ready/maint, and relevant counters:

- exact target membership naming and escaping;
- supported weight boundaries and state transitions;
- command response parsing including warning/error/empty response;
- batch order, bounded timeout, reconnect, and no blind retry after ambiguous acknowledgment;
- read-after-write confirms desired field set and unaffected memberships unchanged;
- apply succeeds but acknowledgment is dropped: action becomes result-unknown, observed read identifies success, and no duplicate mutation occurs;
- HAProxy rejects command: action attempt records verbatim-safe response, desired state is compensated/reverted or review; no false `APPLIED`;
- Runtime socket loss leaves request traffic serving and action unresolved safely.

### Structural/Data Plane operations

- base configuration version is required; stale transaction receives conflict;
- logical route pool/membership create/update/delete in one DPA transaction;
- generated config passes HAProxy native validation before commit;
- invalid/overlapping route/config produces rejection and running config remains unchanged;
- graceful reload preserves existing connections within timeout and exposes new process/state;
- config commit with lost acknowledgment is resolved by version/hash and observed config read;
- rollback uses exact prior validated config/version, not a regenerated approximation;
- no structural DPA call is made by an incident action in MVP unless an explicit, approved configuration workflow owns it.

### State reconstruction and drift

- restart with HAProxy state file restores eligible runtime attributes, then durable desired state reconciles them;
- restart without state file rebuilds from PostgreSQL desired state only after complete observed read and safety checks;
- manual runtime/config mutation is detected by generation/hash/state comparison;
- safe auto-correction of known runtime drift versus `UNMANAGED_DRIFT` for unknown structural drift;
- duplicate physical backend in multiple pools maintains independent membership weight/state while capacity accounting remains physical-instance-aware.

Maintain a compatibility matrix of each pinned HAProxy/DPA patch. An unsupported patch blocks release.

## 8. Reconciliation and recovery tests

Use model-based tests around `desired ↔ observed` with injected crash points after every durable/action step.

- no diff produces no write and a health/audit heartbeat only at bounded cadence;
- desired change is read, locked, version checked, applied, observed, and marked confirmed once;
- stale generation/action/entity version is rejected;
- two overlapping action plans have deterministic conflict/merge/manual-review outcome;
- worker crash at `PLANNED`, `PREPARED`, during write, after write/before acknowledgment, `VERIFYING`, and rollback;
- PostgreSQL commit failure before/after HAProxy mutation;
- Redis loss, Prometheus loss, DPA loss, Runtime loss, and partial partition;
- worker restart increments generation, owns physical socket, reconstructs unfinished action, and chooses resume/compensate/review;
- safe-mode exit requires fresh full observation and evidence windows;
- operator override has higher desired-state version, reason/expiry, and blocks conflicting automation;
- action expiry restores/preserves according to explicit policy rather than silently enabling traffic;
- reconciliation latency and database/API load stay within targets at the maximum MVP membership count.

Use stateful property testing to generate event/crash orderings and assert invariants:

1. at most one effective actuator writer;
2. no committed action without observed confirmation and verification verdict;
3. no automatic action outside authorized project/environment/target;
4. every applied target has a durable previous state or explicitly enters review;
5. desired and observed divergence is visible and never reported healthy.

## 9. API contract tests

For every REST endpoint:

- OpenAPI/Pydantic request/response schema, unknown-field policy, limits, enums, ISO timestamps, correlation ID;
- authentication and role/project/environment authorization for allowed and forbidden cases;
- `Idempotency-Key` requirement on mutation, same-key/same-body replay, same-key/different-body conflict;
- `If-Match`/entity-version stale update conflict for policy/override transitions;
- stable error envelope (`code`, safe message, fields, correlation ID, retryability) without stack/secrets;
- cursor pagination stability under concurrent inserts; bounded page size and filter validation;
- API version prefix and backwards-compatible schema checks;
- body/header/time/query limits, rate limiting, CSRF/session protections, audit actor;
- action request returns accepted/planned rather than claiming HAProxy success;
- fault API absent or hard-disabled outside lab mode and cannot target unregistered/non-lab resources.

Contract snapshots are reviewed intentionally; a snapshot update alone is not proof of compatibility.

## 10. SSE tests

- ordered monotonically identifiable event envelopes with entity version, UTC time, project/environment, correlation/incident/action IDs;
- authorization filters prevent cross-project events;
- resume using `Last-Event-ID` sends only unseen retained events;
- duplicate delivery is harmless and frontend de-duplicates;
- cursor older than retention returns explicit resync event/REST snapshot instruction;
- detected gap triggers entity refresh rather than inventing intermediate state;
- heartbeat cadence keeps NGINX connection alive without event spam;
- slow client buffer is bounded and disconnected/resynced safely;
- NGINX proxy buffering disabled only for SSE path; idle/read timeouts exceed heartbeat;
- token/session expiry closes stream and reauthentication does not leak the old project;
- reconnect storm is rate-limited/jittered; 500 simultaneous demo viewers do not starve control APIs (target refined by resource test).

## 11. Frontend component and E2E tests

### Component/visual

- semantic tokens in Light, Dark, and System; contrast and forced/reduced-motion states;
- all state lozenges include text/icon; stale/unknown/drift cannot look healthy;
- matrix keyboard navigation, sticky/virtualized headers, table alternative, desired/observed split, no-membership versus no-data;
- topology stable layout, hierarchical accessibility alternative, incident cross-filter;
- Decision Trace renders competing hypotheses, rejected units, confidence/completeness, safety, action diff, verification and rollback;
- loading/empty/partial/stale/result-unknown states use fixture coverage;
- charts expose units/sample/missing intervals and data-table alternative;
- visual regression at representative desktop/tablet/mobile widths in both themes.

### Playwright critical journeys

1. Login → select project/environment → Command Center live snapshot/SSE.
2. Register/validate a lab backend and route with authorization and SSRF-negative cases.
3. Observe route-instance incident → inspect matrix and Decision Trace → action confirmation → verification → route-only reintegration.
4. Unknown incident → no automatic action → authorized review and operator note.
5. Action result-unknown → UI disables duplicate → reconciliation resolves observed success/failure.
6. Pause/rollback reintegration with reason and audit.
7. Viewer cannot see mutation controls/addresses; crafted requests still receive 403.
8. SSE disconnect/gap/stale banner and snapshot recovery.
9. Generate validated local report and force Ollama failure to deterministic fallback.
10. Lab-only fault control absent in public profile.

Run axe or equivalent automated accessibility checks plus manual keyboard/screen-reader review; automation alone is insufficient.

## 12. Integration and request-path tests

- Client → NGINX → HAProxy → correct logical route pool → physical backend, preserving/generating correlation metadata per policy;
- TLS/security headers, host/path normalization, API/front-end routing, access log redaction;
- same backend B serves public/auth/catalog while checkout membership B is weight 0/drained;
- keep-alive/connection reuse does not defeat new routing scope beyond documented in-flight connection behaviour;
- normal retry rules and maximum attempt count are observable per client request;
- HAProxy queue/connection/concurrency/rate policies activate at known thresholds;
- control API/worker crash, database/Redis/Prometheus/ELK/Ollama/frontend loss while a sustained normal request stream continues;
- NGINX/HAProxy process loss is correctly detected as a data-plane outage, not falsely masked as control-plane resilience;
- restart/reload preserves or deliberately drains connections within specified limits.

## 13. Load, soak, and performance tests

Initial MVP laboratory targets; tune after a no-controller capacity calibration:

- sustain 1,000 requests/s of small HTTP responses for 30 minutes on the recommended lab hardware, with proposed controller disabled/enabled paired; report hardware and actual ceiling rather than claiming a universal RPS;
- controller adds no application request-path hop and causes <2% throughput change and <1 ms median proxy-path difference attributable to passive telemetry at the tested load;
- 2,000 route-instance memberships in observed-state reconciliation complete a no-diff cycle within 5 s and a changed-target cycle within the action deadline, without unbounded memory/query count;
- metric/fingerprint window processing keeps control-loop p95 delay <2× configured cadence and never overlaps mutation generations;
- 24-hour compact soak has no unbounded Redis keys, DB rows outside retention design, file descriptors, SSE buffers, logs, or container memory;
- overload/failure load generator is open-loop and records coordinated omission protections;
- ELK and Ollama performance are measured separately and cannot affect request-path acceptance.

These targets are feasibility gates, not production capacity claims.

## 14. Fault, recovery, and rollback tests

Every required scenario runs in two forms: deterministic acceptance at one frozen intensity and repeated research trials across intensities. Fault lifecycle has a maximum duration and independent cleanup watchdog.

- instance crash/restart;
- global slow instance;
- one route on one instance returns known failure;
- same route fails across peers because dependency is unavailable;
- offered traffic overload with queues/saturation;
- one deployment version regresses relative to control;
- recovery flaps during stage advancement;
- mixed anomaly with missing/conflicting telemetry;
- HAProxy Runtime/DPA rejection, timeout, restart, and config drift;
- worker/PG/Redis/Prometheus partition at each action lifecycle point;
- verification unavailable, ineffective action, harmful action, and rollback failure;
- manual override collides with automation.

Cleanup verifies fault removal, dependency state, routes, weights, queues, open incidents, locks, and next trial readiness. A cleanup failure quarantines the rig.

## 15. Security tests

Execute the full threat-model acceptance gates:

- password/session/token controls, RBAC, object-level project authorization, CSRF, replay, rate/lockout;
- SSRF corpus: private/link-local/metadata/IPv6/alternate encodings/DNS rebinding/redirects/TOCTOU;
- route/config/log/CSV/HTML injection and path canonicalization;
- public port/network/mount scan; API/LLM/frontend/fault runner cannot reach HAProxy credentials/socket;
- telemetry spoof, stale replay, cross-source conflict, adversarial cardinality and ML evasion;
- dependency/image/secret scan, non-root/read-only filesystem, no Docker socket;
- audit tamper and backup encryption/restore authorization;
- DoS: body, query, login, SSE, expensive report, log cardinality, model queue;
- generated report prompt injection, unsupported entity/number/root cause/control instruction rejection.

Dynamic scanners are bounded to the isolated lab. No automated exploit/fault run targets a public environment.

## 16. Model evaluation tests

- feature schema/dtype/range and training-serving parity;
- deterministic reproduction from dataset+seed+artifact lock;
- grouped split prevents run/window leakage;
- missingness/outlier/cardinality/adversarial values;
- class weights and no resampling leakage into validation/test;
- rules, logistic regression, random forest trained and scored by the frozen protocol;
- macro-F1, each class precision/recall, confusion matrix, expected calibration error, Brier score, abstention curve, and false-action mapping;
- bootstrap confidence intervals grouped by run;
- artifact digest/schema mismatch, corrupt/unavailable model, slow inference → rules-only;
- drift monitor on input distributions, unknown/abstention, calibration proxy and delayed labels; no automatic retraining/deployment;
- selection gates must be met on untouched grouped test; Random Forest is not selected by preference alone.

## 17. LLM grounding tests

- schema-valid and invalid outputs, size/depth/time limits;
- every factual sentence references valid fact IDs;
- numeric/entity/action/category/version/timestamp claims exactly match referenced allowlisted facts;
- prompt injection in operator note/log-like text cannot alter instructions or add actions;
- source-code-line, credential, unsupported root-cause, certainty, and control-API language rejected;
- secrets/cookies/tokens/IPs removed from input and output;
- one bounded repair attempt, then deterministic template fallback;
- Ollama absent/timeout/OOM/wrong model digest still produces complete deterministic report;
- report version, input digest, model/prompt/validator version and rejection reason audited;
- no network/mount/credential path from Ollama/report process to HAProxy actuation.

## 18. Deployment smoke, upgrade, and disaster tests

- compact setup from clean host with pinned artifacts, preflight, migration lock and readiness;
- 8 GB resource-constrained run with ELK/Ollama disabled;
- all required networks, read-only mounts, users, ports, volumes, health checks, retention and limits;
- graceful stop/start order while data plane remains serving when only control components change;
- NGINX/HAProxy config validation and graceful reload under traffic;
- upgrade with pre-backup, migration, image change, safe reconciliation, and rollback compatibility check;
- restore PostgreSQL/config/research bundle to a clean volume/host and verify audit/action topology;
- disk pressure and log/TSDB retention; optional services stop before PostgreSQL loses headroom;
- optional public tunnel removed: LAN/VPN fallback remains functional;
- public profile exposes no fault, datastore, metrics admin, Kibana, DPA, Runtime, or Ollama surface.

## 19. Failure-class acceptance criteria

These are deterministic lab acceptance thresholds, not universal production constants. Windows/sample thresholds come from the frozen test policy and are included in results.

| Class | Required evidence/oracle | Accepted classification/action behaviour | Technical acceptance |
|---|---|---|---|
| `HEALTHY` | No injected fault; normal peer/version metrics for 30 min soak | No incident-driven traffic reduction; routine checks only | Zero automatic quarantine; effective weights stay at policy values; false incident/action recorded if any |
| `INSTANCE_DOWN` | B process stopped; independent connect/probe failures across its routes | Hard rule; complete-instance unit if residual capacity floor holds, else protect/fail/review per policy | B receives no new requests within configured check/intervention bound; A/C/D memberships unchanged; no unsafe retry >1 |
| `INSTANCE_DEGRADED` | B latency/error degraded across ≥2 populated routes, peers healthy | Calibrated class plus safety; bounded weight reduction then instance drain only if verification requires | p95/error improves or action rolls back; unaffected instances are not ejected; residual capacity/queue guard holds |
| `ROUTE_INSTANCE_FAILURE` | Checkout fails only on B; B other routes and checkout peers healthy | Select `(checkout,B)` membership; no complete-B action | ≥99% new checkout selections avoid B after observed confirmation; B continues receiving public/auth/catalog traffic; HCP higher than full-ejection oracle case; rollback available |
| `SHARED_ROUTE_FAILURE` | Checkout fails on all instances with similar signature/dependency evidence; other routes healthy | Complete-route policy: suppress retry, bounded fail-fast/rate/concurrency; do not eject all instances | Retry amplification ≤1.05 for non-retryable requests and ≤policy bound otherwise; other routes retain capacity; zero mass backend ejections |
| `TRAFFIC_OVERLOAD` | Offered load exceeds capacity, queue/connections rise broadly without localized error support | Route admission/concurrency/rate action; no fault-based instance removal | Queue reaches policy bound/recovery trend; retry amplification bounded; no instance quarantine solely from saturation; success/latency result reported |
| `VERSION_SPECIFIC_FAILURE` | v2 cohort regresses on supported route(s), v1 controls healthy, adequate samples | Affected version membership/group only when residual control capacity safe | New affected-route traffic to v2 falls to target; v1 and v2 unaffected-route memberships preserved; cohort/traffic-mix evidence stored |
| `UNKNOWN` | Mixed sparse/conflicting fault plus missing source | Abstain/no destructive automatic action; incident `NEEDS_REVIEW`; optional safe retry suppression only if hard retry rule independently fires | Zero automatic weight/drain/disable/version/route action; confidence/completeness/conflicts visible; operator workflow and audit succeed |

For any class, insufficient residual capacity, unsafe retry semantics, active conflict, stale generation, or missing rollback may downgrade/block the nominal action; that is a pass when it matches the safety policy.

## 20. Healing-action acceptance criteria

| Action | Preconditions | Acceptance oracle |
|---|---|---|
| `NO_CHANGE / REQUIRE_REVIEW` | Unknown/low evidence/conflict or operator policy | No HAProxy mutation; incident/evidence/reason/audit visible; duplicate review event bounded |
| Reduce membership/instance weight | Evidence-supported target, capacity floor, previous state captured | Exact Runtime target reaches requested weight; unaffected targets bit-for-bit equivalent; verification commits or exact rollback |
| Drain route × instance | Scoped support and logical membership exists | Only selected pool member enters drain/weight 0; existing connections follow declared drain semantics; physical instance serves other pools |
| Drain/disable complete instance | Cross-route/down support; residual physical capacity safe | Every logical membership for physical ID reaches requested state as one durable saga; partial apply detected/compensated/reviewed |
| Suppress cross-instance retry | Unsafe/ambiguous method, shared failure, overload, or budget exhausted | Backend attempts/request obey route policy and max one; ML/LLM cannot override; effect measured |
| Route rate limit | Predeclared map/policy and overload/shared protection | Admitted/rejected rate matches tolerance; response semantics/headers correct; other routes not throttled; policy expires/rolls back |
| Route concurrency protection | Predeclared route control and safe bound | Active connections/queue remain within bound; no deadlock/leak; unaffected routes retain their limits |
| Fail fast for shared route | Strong shared failure and route policy permits | Bounded error response without cross-peer amplification; action expiry and recovery probes work; no fabricated success |
| Remove deployment version | Version evidence and residual capacity/control cohort | All and only intended version memberships change; capacity counted physically; partial target set cannot be committed as full success |
| Begin/advance reintegration | Fresh probes/traffic evidence, min samples/window, no conflict/flap | Observed weight reaches stage; verification window starts after confirmation; no auto skip; affected/unaffected criteria pass |
| Pause reintegration | Insufficient evidence/operator/flap | No stage advance while paused; current safe weight remains; reason/expiry/audit visible |
| Roll back reintegration/action | Harmful/ineffective criteria or operator | Exact prior safe stage/state observed within deadline; failure enters `NEEDS_REVIEW` and safe alarm, never false committed |
| Manual override | Authorized role/approval, reason, expiry, impact preview | Higher desired version blocks conflicting automation; observed confirmation/audit; expiry follows explicit reviewed policy |

## 21. Release gates

### MVP release

- all safety, retry, state-machine, adapter, idempotency, recovery, RBAC, and class/action acceptance tests pass;
- no critical/high unresolved security finding in the exposed profile;
- compact Compose works from a clean supported host and backup restore is demonstrated;
- request stream survives every declared control/optional component loss;
- rules-only system handles all hard cases and UNKNOWN safely; ML, LLM, frontend loss does not block core control;
- route-instance quarantine proves unaffected memberships continue serving;
- every diagram/API/state transition agrees with the frozen specification.

### Research result release

- experiment exit criteria in `17_RESEARCH_AND_EVALUATION_PLAN.md` pass;
- data/scripts reproduce figures; exclusions and negative results are present;
- IP cell/professional review decides what may be publicly disclosed before paper/demo/repository publication.

### Stop-ship conditions

- two actuator writers can reach HAProxy;
- an action can be marked committed without observed confirmation/verification;
- UNKNOWN or incomplete evidence can trigger broad automatic removal;
- unsafe method can be retried by classifier/model choice;
- public/fault/SSRF/cross-project/control credential boundary fails;
- invalid HAProxy config can replace running valid config;
- action rollback state or audit attribution can be absent;
- the data plane stops when only control/intelligence/reporting/frontend fails.


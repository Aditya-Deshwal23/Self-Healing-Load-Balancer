# Failure Fingerprint and Hybrid Classification

## 1. Design goal

The fingerprint represents *where and how traffic is failing*, not why source code is wrong. It must be stable enough for classification and repeated-failure grouping, low-cardinality enough for student hardware, privacy-minimized, and explicit about missing/conflicting evidence.

## 2. Observation cell and fingerprint schema

### Identity and scope fields

| Field | Type/meaning | Privacy/cardinality rule |
|---|---|---|
| `schema_version` | semantic feature schema version | required for comparison/model compatibility |
| `project_id`, `environment_id`, `service_id` | opaque UUIDs | never free-form labels in metrics |
| `route_group_id` | configured low-cardinality route ID | no raw URL/query/path parameters |
| `instance_id` | stable physical identity | independent of IP/container ID |
| `deployment_version_id` | immutable build/release cohort | sanitized label; no Git credential/URL |
| `method_category` | `SAFE`, `IDEMPOTENT_DECLARED`, `CONDITIONAL`, `UNSAFE` | exact method retained in request logs only if allowed |
| `window_start`, `window_end`, `window_lengths_s` | aligned UTC windows | source skew recorded |

### Outcome and timing fields

| Field | Representation |
|---|---|
| request/sample count | total and per evidence source |
| response status | 2xx/3xx/4xx/5xx counts and selected configured codes such as 429/502/503/504 |
| response signature | HMAC of allowlisted sanitized application error code + status family + termination class; never body hash by default |
| timeout class | connect, queue, response-header, response-body/stream, client abort, unknown |
| connection failure class | refused, reset-before-send, reset-after-send, TLS/backend handshake, DNS/resolve, no route, unknown |
| HAProxy termination class | normalized allowlisted code from HAProxy logs |
| latency | p50/p95/p99 where sample count supports it; otherwise robust median/MAD and `insufficient_quantile=true` |
| latency deviation | robust z-like score versus same-route peer median/MAD and historical baseline |
| error-rate deviation | absolute difference and peer-relative ratio with interval bounds |
| response-loss ambiguity | whether request may have executed before response loss |

### Load, capacity, and action fields

| Field | Representation |
|---|---|
| request rate/change | current RPS, baseline ratio, robust deviation |
| retries | attempts, redispatches, retries/original request ratio |
| active connections/requests | current and configured max |
| queue depth/time | current/max and deviation |
| CPU/memory | optional host/container saturation and missing flags |
| desired/observed weight/state | before/current, drift flag |
| physical capacity/headroom | configured capacity, allocated/observed demand, confidence |
| prior action | action type, target scope, age, reintegration stage, cooldown |

### Cross-control and evidence fields

| Field | Representation |
|---|---|
| `affected_instance_set` | sorted stable IDs whose cell evidence crosses incident threshold |
| `affected_route_set` | sorted route IDs |
| `affected_version_set` | sorted version IDs |
| same-route peer support | target deviation, peer count, healthy-peer proportion |
| same-instance cross-route support | number/proportion of other routes healthy/degraded |
| version cohort support | suspect/control counts, comparable load indicator, cohort delta |
| direct probe support | consecutive pass/fail, result class, freshness |
| source provenance | Prometheus series IDs/query hash, HAProxy log aggregate, probe IDs, app metric refs |
| conflict flags | probe-vs-traffic, metrics-vs-logs, instance-vs-route scope, clock skew |
| data completeness | 0–1 score plus missing required fields; never a single unexplained number |
| out-of-distribution score | distance/novel-category flags relative to training support |

## 3. Data-completeness score

Completeness is policy-weighted and class-specific. A generic example:

```text
completeness =
  0.25 * request_outcome_coverage
+ 0.20 * route_and_member_identity_coverage
+ 0.20 * peer_control_coverage
+ 0.15 * direct_probe_freshness
+ 0.10 * capacity_signal_coverage
+ 0.10 * source_time_alignment
- conflict_penalties
```

For `ROUTE_INSTANCE_FAILURE`, same-route peers and same-instance other routes are required; missing either makes its certificate insufficient regardless of the aggregate score. For `INSTANCE_DOWN`, repeated direct reachability and HAProxy connection failures can justify a hard result without CPU metrics. For overload, queue/demand/saturation signals are required. Thus the scalar aids ranking/UI but never replaces required-field gates.

## 4. Canonicalization and fingerprint identity

Canonicalization procedure:

1. Resolve all raw observations to registry IDs.
2. Drop query strings, bodies, disallowed headers, and unregistered path fragments.
3. Convert timestamps to UTC and fixed window boundaries.
4. Normalize units to seconds, bytes, counts, and ratios.
5. Round derived floats to schema-defined precision only after decision statistics are calculated.
6. Sort sets and categorical maps lexicographically by opaque ID.
7. Represent missing as explicit `null + missing_reason`, never numeric zero.
8. Serialize canonical JSON with sorted keys and no insignificant whitespace.
9. Compute `fingerprint_id = HMAC-SHA-256(project_rotation_key, canonical_bytes)`.

The HMAC key is project-scoped and rotated. The ID proves stable equality within the permitted retention domain; it does not make sensitive raw input safe. Raw sensitive input is not collected.

## 5. Privacy treatment

- NGINX strips or redacts `Authorization`, `Cookie`, `Set-Cookie`, tokens, API keys, and query strings before telemetry.
- Request/response bodies are never ingested by the controller, ELK pipeline, or LLM.
- Raw URL paths are mapped to configured route IDs at HAProxy; unexpected paths use an `unmapped` bucket with strict cardinality.
- IP addresses are operational secrets: encrypted/limited in PostgreSQL, not exposed to ordinary viewers, and not metric labels.
- A response signature uses only an application-provided allowlisted error code. Hashing arbitrary response bodies is prohibited because hashes preserve equality and may permit dictionary recovery.
- User IDs/session IDs are not features. Request IDs are random correlation tokens with bounded retention.
- Log processors cap length, encode control characters, reject invalid JSON, and apply redaction again as defense in depth.
- Reports expose aggregate evidence, not individual requests.

## 6. Robust feature calculation

For target cell `(route r, instance i)` and window `w`:

```text
peer_cells = same route r, other eligible instances, comparable window/load
peer_center = median(peer metric)
peer_scale  = max(1.4826 * MAD(peer metric), configured epsilon)
peer_deviation = (target metric - peer_center) / peer_scale

cross_route_cells = other registered routes on physical instance i
version_controls  = same route/load on stable version cohorts
```

Robust median/MAD is preferred over mean/standard deviation for small fleets with one outlier. If fewer than two peers exist, peer-based automatic localization is unavailable. Quantile comparisons include sample count and uncertainty; a p99 from ten requests is not treated as precise.

## 7. Failure-support matrix algorithm

```text
build_support_matrix(environment, window):
  cells = fetch_complete_route_instance_cells(window)
  for each cell c:
      c.absolute = evaluate_absolute_probe_and_error_evidence(c)
      c.route_peer = compare_with_same_route_other_instances(c)
      c.instance_cross_route = compare_other_routes_on_same_instance(c)
      c.version_peer = compare_version_cohorts(c)
      c.overload = correlate_rate_queue_concurrency_and_resource_signals(c)
      c.conflicts = compare_source_conclusions(c)
      c.completeness = score_and_list_missing_requirements(c)
  derive affected route/instance/version sets using stable thresholds
  return matrix with every comparison's samples, intervals, and provenance
```

Thresholds come from a versioned policy and validation experiments. They are not silently learned online.

## 8. Similarity, clustering, and repeated failures

### Similarity

Only fingerprints with the same service and compatible schema are compared. Weighted mixed-type similarity uses:

- normalized absolute difference for numeric rates/deviations;
- exact/Jaccard similarity for categorical and affected sets;
- exact equality for response signature when present;
- time decay so old patterns contribute less;
- missing-pair exclusion with a penalty when too few dimensions overlap.

Conceptually:

```text
similarity = 1 - weighted_Gower_distance(comparable_fields)
similarity *= evidence_overlap_ratio
similarity *= exp(-age / policy_half_life)
```

Weights and threshold are stored by schema version. Similarity is explainable as per-field contributions.

### Online incident grouping

During a bounded active window, a new fingerprint joins an active incident if service/scope keys are compatible and similarity exceeds the policy threshold. Otherwise it creates a new incident. Union is deterministic; incidents are not split automatically during active mitigation because doing so could orphan actions. An operator or post-incident job may correct grouping with an audit event.

### Offline clustering

DBSCAN is permitted only for retrospective research/repeated-pattern discovery because it handles noise and does not require a fixed cluster count. It never controls HAProxy. Cluster parameters, feature schema, and dataset hash are recorded.

### Expiration

- raw working cells in Redis: 15 minutes default;
- active fingerprint similarity cache: 1 hour;
- compact incident fingerprints in PostgreSQL: 90 days local/lab, 1 year pilot unless policy changes;
- response-signature HMAC rotation bounds cross-period linkability;
- expired fingerprints remain referentially represented by a hash/schema in audit/action records, not full feature content.

## 9. Conflicting evidence resolution

Evidence is not assigned a universal “truth rank”; reliability depends on the question. The resolver applies explicit patterns:

| Conflict | Interpretation | Result |
|---|---|---|
| direct probe fails, real traffic succeeds recently | probe path/auth may be wrong | lower probe reliability; do not declare down |
| direct probe succeeds, connection failures affect real traffic | gray/path/load failure possible | retain traffic evidence; not `HEALTHY` |
| logs show errors, Prometheus counter missing | telemetry gap | classification may proceed from logs with lower completeness if identity coverage is adequate |
| CPU high but queue/error normal | resource metric alone is not overload | no overload action |
| one route/instance bad but same version cohort also bad | overlapping hypotheses | require more controls or choose version scope only if cohort support dominates; otherwise `UNKNOWN` |
| HAProxy observed state differs from telemetry labels | stale mapping/config drift | freeze action; registry/drift incident |

Hard connection-refused evidence can establish reachability failure, but safety still checks capacity. Conflicts reduce confidence and can invalidate an evidence certificate. The UI lists them rather than hiding them in a score.

## 10. Final feature vector

The ML vector contains fixed-order numeric/one-hot/binary features, not high-cardinality IDs:

```text
log1p(request_count), rps_ratio_to_baseline,
2xx_rate, 4xx_rate, 5xx_rate, 429_rate,
connect_failure_rate, timeout_rate_by_class,
p50/p95 robust deviation, peer latency deviation,
peer error absolute_delta and ratio,
healthy_peer_fraction, affected_instance_fraction,
same_instance_other_route_healthy_fraction,
affected_route_fraction,
version_cohort_error_delta, version_cohort_latency_delta,
queue_utilization, active_utilization, retry_amplification,
CPU/memory saturation with missing indicators,
direct_probe_failure_streak and freshness,
load_change, prior_action category/age,
data_completeness, source_conflict count,
route criticality category, method safety category
```

Route, instance, and version IDs are not predictive features; otherwise the model memorizes the demo topology. Method and criticality influence abstention/safety but may be excluded from scope prediction if experiments show leakage. Feature selection is frozen before the held-out test.

## 11. Deterministic rule layer

Rules have three outputs: a hard class, a candidate-class support/block, and a hard safety flag.

### Hard cases

- repeated direct connection failure plus HAProxy connection failures across route memberships → candidate/hard `INSTANCE_DOWN`;
- low remaining capacity → block/downgrade action, not a failure class;
- unsafe retry method/ambiguous response loss → retry block;
- completeness below class-required minimum → block that class/action;
- conflicting active action/operator override → action block;
- reintegration stage fails its evidence threshold → roll back stage;
- stale registry/config identity → `UNKNOWN` plus drift incident.

### Scope templates

```text
ROUTE_INSTANCE_FAILURE requires:
  target route/member error or latency evidence
  AND same-route peers predominantly healthy
  AND same physical instance's other routes predominantly healthy
  AND not overload-correlated

SHARED_ROUTE_FAILURE requires:
  route abnormal on configured quorum and at least two instances
  AND those instances' other routes predominantly healthy
  AND retry amplification/shared signature supports common behavior

INSTANCE_DEGRADED requires:
  one physical instance abnormal on multiple sufficiently sampled routes
  AND peers on those routes healthy
  AND endpoint remains reachable

VERSION_SPECIFIC_FAILURE requires:
  suspect cohort abnormal against stable cohort on comparable traffic
  AND sufficient instances/requests
  AND pattern is not explained by a single down instance

TRAFFIC_OVERLOAD requires:
  demand or concurrency rise
  AND queue/saturation alignment
  AND degradation is not isolated to a single cell without saturation
```

Policies define “predominantly,” sample minimums, and deviations; lab defaults are validated, not universal.

---

> **📍 IMPLEMENTATION STATUS (2026-09-17):** Sections 11 (deterministic rule layer) and 12–20 (ML candidates through acceptance gate) describe the design intent. As of Phase 1 (complete): the deterministic rule layer (Section 11) is **implemented and generalized** — `classify()` in `worker_policy.py` evaluates every cell in the full route×instance topology with no hardcoded flagship scenario. The HYBRID_SHADOW fast-path signal is **wired in** as a purely advisory EWMA passthrough (`FastPathController` output, recorded as `shadow_statistical_signal` in `Classification.evidence_support`), verified by a dedicated safety test. A trained ML classifier (Logistic Regression, Random Forest — Sections 12–19) is **not yet started**; the full feature-extraction pipeline, training dataset, calibration, and model versioning described below remain future phases. The HYBRID_SHADOW → HYBRID_ACTIVE promotion gate (Section 20) is also future.

---

## 12. ML candidates

| Approach | Strength | Weakness | Decision |
|---|---|---|---|
| Rules only | deterministic, explainable, safe with small data | threshold interactions; weaker on mixed degradation | operational baseline and fallback |
| Logistic Regression | interpretable coefficients, fast, probability baseline | linear boundary, needs careful interactions/scaling | mandatory ML baseline |
| Random Forest | handles nonlinear interactions/missing indicators; robust on tabular fault data | raw probabilities often uncalibrated; can overfit topology; larger explanations | preferred candidate, not preselected winner |
| Additional model | gradient boosting could improve tabular accuracy | adds tuning/comparison scope and calibration work | **not justified in MVP**; add only if both baselines demonstrably fail |

Deep learning and reinforcement learning have no demonstrated need for this dataset size, latency, or explainability requirement.

## 13. Training dataset and labels

### Label source

Primary training labels come from the Experiment Manager’s ground-truth fault specification, not from the controller’s own rules. Each record links to experiment run, random seed, topology, versions, load phase, injected fault start/stop, and affected ground-truth cells. Transition windows are labeled separately/excluded according to a preregistered rule to avoid ambiguous leakage.

Natural incidents may be added only after two-person adjudication with an explicit uncertainty label. Reports/operator guesses are never automatic labels.

### Dataset units

One example is a fingerprint window, but splitting occurs by **experiment run**, not by window. Adjacent windows from the same injected incident cannot appear across train and test.

### Split

- 60% experiment runs train;
- 20% validation/calibration;
- 20% final held-out test;
- group by run and, where possible, reserve unseen load seeds/topology permutations for test;
- publish the run IDs and hash of each split;
- use nested group cross-validation inside train/validation for limited tuning;
- the final test is opened once per frozen candidate.

Time-ordered secondary validation checks drift/generalization; random window splits are prohibited.

## 14. Class imbalance and missing telemetry

- generate balanced *fault-run counts* without making every time window artificially balanced;
- use class weights for Logistic Regression/Random Forest, selected on validation macro-F1 and calibration;
- report real-prevalence evaluation separately because false positives dominate normal operation;
- never use blind oversampling across adjacent windows; synthetic SMOTE-like points are unnecessary and may be unrealistic;
- missing numeric sources have value plus missing indicator; models are trained on planned dropout scenarios;
- if a class-required source is absent, the hybrid resolver may abstain regardless of ML probability.

## 15. Calibration, confidence, and unknown handling

### Calibration

- calibrate on held-out calibration runs, never training rows;
- prefer sigmoid/Platt calibration for smaller samples; permit isotonic only when each class has enough independent runs;
- measure multiclass Brier score and expected calibration error (ECE), with reliability plots;
- store calibration object as part of the model artifact/version.

### Final confidence

```text
final_confidence = calibrated_class_probability
                 * evidence_support_factor
                 * completeness_factor
                 * temporal_stability_factor
                 * OOD_factor
```

This value is capped by rule-defined maxima when peers/samples are sparse. It is not presented as a causal probability.

### Unknown conditions

Resolve to `UNKNOWN` when any applicable condition holds:

- maximum calibrated probability below the validation-selected threshold (initial study value 0.65);
- top-two probability margin below the validation-selected threshold (initial 0.15);
- class-required evidence absent;
- OOD distance/category outside training support;
- conflict severity above policy;
- time instability/flapping within the classification window;
- model/schema/checksum failure;
- multiple hard rule templates conflict.

The numeric initial values are experiment starting points, not production constants.

## 16. Explainability

Every classification record contains:

- final class and confidence;
- rule path and thresholds, with observed values;
- top positive and negative feature contributions;
- peer/control cells and their summary values;
- missing/conflicting sources;
- ML model/calibrator/feature schema versions;
- alternative class probabilities;
- reason for abstention or override;
- evidence certificate link.

For Logistic Regression, standardized coefficient contributions are shown. For Random Forest, constrained permutation importance is global; a stable local explanation method may be used offline, but the MVP Decision Trace can show rule/feature comparisons rather than adding a heavy SHAP runtime. Explanations never state a source-code root cause.

## 17. Model versioning and reproducibility

Each `model_version` stores:

- algorithm and hyperparameters;
- serialized artifact and SHA-256;
- feature/canonicalization/label schema versions;
- dataset manifest and checksum;
- train/validation/test run IDs;
- dependency lockfile/image digest;
- random seeds and training command metadata;
- class distribution;
- macro-F1, per-class precision/recall, confusion matrix, ECE/Brier, false-action shadow result;
- approval status, approvers, activation and rollback links.

Artifacts are immutable/read-only at inference. Activation is an audited `PROJECT_ADMIN` operation and may require an `APPROVER` under pilot policy. Automatic retraining and automatic champion promotion are prohibited.

## 18. Model failure and drift

- Inference deadline: 200 ms hard, target p95 under 50 ms on lab CPU.
- Timeout, exception, NaN, unknown category, checksum mismatch, or schema mismatch: discard ML result and run rules-only.
- Drift monitors: unknown rate, population stability index for selected features, calibration on newly labeled lab runs, and class/feature distribution changes.
- Drift creates a model review incident; it does not retrain automatically.
- Retraining is manual, reproducible, and must beat the active model on the frozen test protocol without degrading safety-critical class recall or false-action rate.
- Rollback changes the active model pointer; rules remain unchanged.

## 19. Defensible “90%” result

The project may state “90%” only in a complete sentence such as:

> On the preregistered held-out set of independent fault-injection runs, model X achieved macro-F1 ≥0.90, with each actionable class recall ≥0.85, ECE ≤0.05, and shadow false-action rate ≤1%; 95% confidence intervals and the full confusion matrix are reported.

These are target criteria, not promised results. Raw accuracy, training-set performance, or a random window split cannot support the claim. If criteria are missed, the honest result and error analysis are reported and rules-only remains the product baseline.

## 20. Classification acceptance gate for actuation

ML may enter `HYBRID_ACTIVE` only after:

1. all artifact/schema/checksum tests pass;
2. held-out metrics and intervals meet the approved thresholds;
3. shadow mode runs through every fault class and no-fault soak;
4. safety engine blocks injected high-confidence unsafe recommendations;
5. model failure demonstrably falls back to rules;
6. two reviewers approve activation;
7. rollback to rules-only is exercised.

Research success does not require turning on ML actuation. Demonstrating that rules are safer is a valid result.

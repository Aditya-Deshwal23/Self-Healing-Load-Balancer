# Observability and Incident Design

## 1. Observability principles

- Metrics answer “how much/how often”; logs answer “which event and why”; durable action records answer “what state changed.”
- The product never requires a trace to route traffic in MVP.
- Route and member identities are bounded registry IDs. Raw paths, users, request IDs, and error text are not metric labels.
- Missing, delayed, or contradictory telemetry is a first-class state and lowers action authority.
- Product screens query FastAPI; browsers never connect directly to Prometheus or Elasticsearch.

## 2. Metric naming and label policy

Product-owned metrics use `shlb_`; native HAProxy/exporter metrics remain native and are mapped through recording rules. Histograms define documented buckets appropriate to lab timeouts. Common bounded labels: `project`, `environment`, `service`, `route`, `instance`, `version`, `class`, `action_type`, `result`, `stage`, and `mode`. Labels use opaque/stable short identifiers; human names are joined in the UI.

Cardinality budget is reviewed before adding a label. `request_id`, raw URL, client IP, exception text, action ID, incident ID, and fingerprint hash are log fields, not metric labels.

## 3. Traffic and capacity metrics

| Metric/recording rule | Type | Core labels | Meaning |
|---|---|---|---|
| `shlb_http_requests_total` | counter | env/service/route/instance/version/status_family/method_category | original client requests by selected member |
| `shlb_http_request_duration_seconds` | histogram | env/service/route/instance/version | end-to-end HAProxy upstream duration |
| `shlb_http_success_ratio` | recording rule | env/service/route/instance/version | 2xx/3xx or route-defined success over request count |
| `shlb_http_errors_total` | counter | route/instance/error_class | normalized 4xx/5xx/timeout/connect/termination |
| `shlb_http_timeouts_total` | counter | route/instance/timeout_class | timeout location/class |
| `shlb_active_requests` | gauge | route/instance | current admitted work |
| `shlb_backend_connections` | gauge | route/instance/state | active/idle as available |
| `shlb_backend_queue_depth` | gauge | route/instance | queued work |
| `shlb_backend_queue_wait_seconds` | histogram | route/instance | wait before backend dispatch |
| `shlb_backend_weight` | gauge | route/instance | observed dynamic weight |
| `shlb_backend_state` | gauge | route/instance/state | one-hot administrative/health state |
| `shlb_route_eligible_capacity` | gauge | route | configured capacity currently eligible |
| `shlb_route_healthy_capacity_preserved_ratio` | gauge/research rule | route/scenario/baseline only in lab | ground-truth research metric; not available as truth in production |
| `shlb_instance_physical_utilization_ratio` | gauge | instance | summed cross-route demand / configured physical capacity |

p50/p95/p99 are Prometheus recording rules over histograms. The UI displays sample count and window with every percentile.

## 4. Retry and protection metrics

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `shlb_backend_attempts_total` | counter | route/instance/attempt_kind | original, same-member connection retry, redispatch |
| `shlb_cross_instance_retries_total` | counter | route/method_category/result | cross-member attempts |
| `shlb_retry_suppressed_total` | counter | route/reason | method/shared/overload/budget/ambiguity suppression |
| `shlb_retry_amplification_factor` | recording rule | route | backend attempts / original requests |
| `shlb_rate_limited_requests_total` | counter | route/policy/result | admitted/shed counts |
| `shlb_concurrency_rejected_total` | counter | route | concurrency protection |
| `shlb_fail_fast_responses_total` | counter | route/reason | predeclared fail-fast behavior |

## 5. Classification and evidence metrics

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `shlb_classifications_total` | counter | class/source/mode | final decisions; source rules/hybrid |
| `shlb_classification_confidence` | histogram | class/mode | final bounded confidence distribution |
| `shlb_data_completeness` | histogram | service/class_candidate | evidence coverage |
| `shlb_unknown_total` | counter | reason | low probability/margin, missing, conflict, OOD, model failure |
| `shlb_unknown_ratio` | recording rule | service | unknown / total classifications |
| `shlb_evidence_conflicts_total` | counter | conflict_type | source/scope conflicts |
| `shlb_fingerprint_build_seconds` | histogram | schema | build latency |
| `shlb_model_inference_seconds` | histogram | model/algorithm | inference latency |
| `shlb_model_inference_failures_total` | counter | model/reason | timeout/schema/checksum/exception |
| `shlb_model_fallback_total` | counter | reason | rules-only fallbacks |

Model IDs are bounded active/version short labels, not artifact hashes.

## 6. Action, control-loop, and recovery metrics

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `shlb_actions_total` | counter | action_type/target_unit/result/actor | planned/applied/committed/rolled_back/review |
| `shlb_action_apply_seconds` | histogram | action_type | prepared to state-confirmed |
| `shlb_action_success_ratio` | recording rule | action_type | effective committed / applied |
| `shlb_action_rollbacks_total` | counter | action_type/reason | rollback/compensation |
| `shlb_action_false_total` | counter | class/action_type | lab ground-truth false actions only |
| `shlb_control_loop_duration_seconds` | histogram | phase | reconcile/evidence/verification iteration latency |
| `shlb_control_loop_lag_seconds` | gauge | environment | scheduled time to completion/start lag |
| `shlb_desired_observed_drift` | gauge | environment/drift_type | current drift count |
| `shlb_haproxy_command_total` | counter | operation/result | adapter attempts/readback outcome |
| `shlb_haproxy_command_seconds` | histogram | operation | API/socket duration |
| `shlb_verification_seconds` | histogram | action_type/result | post-action verification time |
| `shlb_verification_insufficient_total` | counter | reason | no samples/source/conflict/deadline |
| `shlb_reintegration_stage_total` | counter | stage/result | advances/rollback/pause |
| `shlb_reintegration_failures_total` | counter | stage/reason | recovery failure |
| `shlb_reintegration_flaps_total` | counter | target_unit | recurrence |
| `shlb_healthy_capacity_preservation_estimate` | gauge | route/action | controller’s predicted value; clearly labeled estimate |

## 7. Dependency and reporting metrics

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `shlb_dependency_up` | gauge | dependency | postgres/redis/prometheus/elasticsearch/haproxy_api/ollama/frontend |
| `shlb_dependency_request_seconds` | histogram | dependency/operation | bounded call latency |
| `shlb_safe_mode` | gauge | environment/reason | environment automation state |
| `shlb_event_outbox_pending` | gauge | project | unpublished events |
| `shlb_sse_connections` | gauge | project | live streams |
| `shlb_sse_reconnects_total` | counter | reason | stream reliability |
| `shlb_report_generation_seconds` | histogram | generator/model/result | deterministic and LLM report time |
| `shlb_report_validation_failures_total` | counter | reason | schema/entity/unsupported claim |
| `shlb_llm_fallback_total` | counter | reason | template fallback |

## 8. Structured log envelope

Every product-owned log event includes:

```text
@timestamp, schema_version, event_type, severity
project_id, environment_id, service_id
request_id/correlation_id where applicable
incident_id, fingerprint_id, classification_id, action_id, attempt_id where applicable
actor_type, actor_id (pseudonymous), source_component, source_instance
message_code, outcome, duration_ms
details: bounded schema for the event type
```

Human message text is secondary to `message_code` and structured details. Control characters are encoded; values are length-capped; secrets/raw bodies are forbidden.

## 9. Required log schemas

### Request log

```text
event_type=request_completed
request_id, traceparent_if_present
route_id, method_category
backend_id, route_membership_id, version_id
status_code/status_family, bytes_bucket
queue_ms, connect_ms, response_ms, total_ms
retry_count, redispatch_count
timeout_class, connection_failure_class, termination_class
sanitized_response_signature optional
```

No query string, authorization/cookie, payload, user ID, or client IP by default. A privacy policy may retain truncated/pseudonymized network metadata in edge security logs, not classifier features.

### Classification log

```text
event_type=classification_completed
fingerprint/classification IDs, window IDs
rule_result/reasons, model_version/probabilities
final_class/confidence/completeness/OOD
missing_sources, conflicts, alternative classes
```

### Safety-decision log

```text
event_type=safety_decision
certificate_id, candidate target/unit
decision allow/downgrade/block/review
capacity before/after/reserve
retry decision, conflicts/cooldown/override
candidate cost and reason codes
```

### HAProxy action log

```text
event_type=haproxy_action_attempt
action/attempt/generation/sequence
operation type and opaque target IDs
previous/requested/observed typed values
adapter result class, ack_lost flag, duration
HAProxy process/config IDs
```

Raw command text is excluded or sanitized because it may contain addresses; only allowlisted operation/target IDs are needed.

### Verification log

```text
event_type=verification_result
action/stage, window IDs, sample counts/duration
affected metrics/bounds/pass
preservation metrics/bounds/pass
state/capacity/retry pass
outcome/reasons
```

### Rollback log

```text
event_type=rollback_transition
original/rollback action IDs, reason
last_verified/prior/requested/observed state refs
attempt/outcome/manual_review flag
```

### Operator override log

```text
event_type=operator_override
override ID, opaque actor, target, reason/ticket
requested state, capacity preview, approvals
activation/expiry/release and outcome
```

### Experiment log

```text
event_type=experiment_transition
experiment/run ID, baseline/scenario/load/seed
ground_truth target, injection parameters hash
image/config/model/policy hashes
phase start/fault/mitigation/recovery/cleanup
outcome/artifact manifest
```

## 10. Correlation model

```text
client request_id
  -> HAProxy request log route_membership_id
  -> observation_window_id (aggregate reference, not one-to-one row)
  -> fingerprint_id
  -> incident_id
  -> classification_id
  -> evidence_certificate_id
  -> action_id / attempt_id
  -> verification_result_id
  -> reintegration_run/stage IDs
  -> report_id
```

`X-Request-ID` is propagated for request debugging. Control workflows use a distinct `X-Correlation-ID` and durable IDs. Aggregate evidence stores query hashes and time bounds rather than millions of request foreign keys. The Decision Trace links these references and displays gaps explicitly.

## 11. Dashboards

### Data-plane health

- request/success/error/timeout rate by route and member;
- p50/p95/p99 with sample counts;
- queue, active work, connection failures;
- desired/observed state and weight;
- eligible and physical headroom;
- retry amplification and protection state.

### Scope and decision quality

- class distribution, unknown and completeness;
- route × instance matrix;
- confidence/calibration in research mode;
- scope disagreement rules versus ML;
- blocked/downgraded candidate reasons;
- estimated versus ground-truth scope in lab only.

### Control-loop safety

- reconcile lag/duration and writer generation;
- desired/observed drift;
- actions by lifecycle/result;
- rollback/harm/insufficient evidence;
- active overrides/cooldowns/quarantine caps;
- HAProxy API latency/rejection/ack loss.

### Recovery

- stage distribution/duration;
- target versus peer metrics at each exposure;
- flap and maximum-attempt review;
- preserved unaffected-route capacity;
- retry restoration order.

### Research

- baseline/scenario run matrix;
- healthy-capacity preservation with success guardrail;
- successful requests, retry amplification, UFIR, false action;
- MTTD/MTTI/MTTR and classifier metrics;
- resource/control overhead.

Kibana provides deep raw-log investigation; the product UI provides curated evidence and control state.

## 12. Alerts

| Alert | Initial condition | Severity/action |
|---|---|---|
| critical route below reserve | observed eligible/headroom below configured reserve for 2 windows | critical; freeze further removals |
| retry amplification | factor exceeds route threshold and rising | high; hard retry suppression candidate |
| shared route failure | route errors across quorum with completeness | high; incident, route protection evaluation |
| action harmful | verification harmful | critical; compensate/freeze overlap |
| rollback failed | target not at safe requested state after bounded attempts | critical/manual review |
| desired/observed drift | drift persists >2 reconciliations | high; reconcile or unmanaged-drift freeze |
| control-loop lag | p95 exceeds 2× scheduled interval for 5 min | high |
| unknown/completeness degradation | unknown or missing ratio above baseline | warning/high depending duration |
| model failure/fallback | checksum/schema/inference failures | warning; rules-only; high if rules also fail |
| verification deadline | insufficient at max deadline | warning/review |
| reintegration flap/max attempts | recurrent stage failure or 3 attempts | high/manual review |
| PostgreSQL/Redis unavailable | > one check interval | critical safe mode; traffic continues |
| Prometheus unavailable/stale | > two scrape windows | high; suppress evidence actions |
| HAProxy API unavailable | requests still serving but control unreadable | critical control alert; LKG |
| Elasticsearch/Ollama unavailable | optional service health | warning only; fallback |

Production-like alert thresholds are tuned during soak; alert tests are part of fault injection.

## 13. Tracing and OpenTelemetry decision

OpenTelemetry is **later**, not MVP. Reasons:

- NGINX/HAProxy request logs and explicit correlation IDs provide the evidence required for route/member classification;
- end-to-end tracing requires customer backend/dependency instrumentation and increases storage/cardinality/privacy scope;
- the initial topology has one proxy hop and controlled demo applications, so traces add limited causal value;
- tracing must not become a prerequisite for healing.

MVP propagates a valid W3C `traceparent` if supplied and may log it, but does not trust or require it. A later OTel Collector can be added to the observability plane, with sampled traces used only as supplementary evidence and never raw payloads.

## 14. Incident grouping and severity

- Fingerprints join an active incident by compatible service/scope and versioned similarity rule.
- One incident may evolve from `UNKNOWN` to a supported class; old classifications remain immutable.
- Severity is based on route criticality, affected success/latency, capacity, and breadth—not ML confidence alone.
- A shared route incident absorbs matching per-member symptoms before independent actions are allowed.
- Operator acknowledgment changes notification state, not technical incident state.
- Resolution requires verified recovery or an explicit evidence-backed/manual outcome.

## 15. Observability failure posture

- No Prometheus evidence: classification/action pause; HAProxy health checks continue.
- No Elasticsearch: metric/rule control continues; request-log-only features become missing; reports omit log evidence.
- Exporter stale: suppress actions requiring HAProxy traffic metrics; direct observed-state socket may still show config/state.
- Log pipeline lag: expose lag and lower completeness; never treat missing errors as zero.
- cAdvisor/Node Exporter absent: overload confidence falls; they are supplementary, not mandatory for hard reachability.


# Safety, Retry, and Healing Transactions

## 1. Safety-engine contract

The safety engine is deterministic, versioned, and evaluated after classification and immediately before every mutation. Its output is one of:

- `ALLOW`: candidate may proceed exactly as proposed;
- `DOWNGRADE`: replace it with a smaller-magnitude, more reversible, or narrower safe action;
- `BLOCK`: no automatic mutation;
- `REQUIRE_HUMAN_REVIEW`: evidence may justify action, but policy/criticality/risk requires approval.

The engine returns machine-readable reasons, before/after capacity, retry decision, conflicts, and policy versions. ML and LLM output are not inputs to hard retry semantics except that the classifier’s class/confidence is one bounded signal.

## 2. Safety inputs

| Input | Required interpretation |
|---|---|
| failure class/scope | final hybrid result plus alternatives, not raw ML label |
| confidence | calibrated/capped and stable; never substitutes for required controls |
| data completeness/conflicts | class-specific requirements and source freshness |
| request idempotency | per-route/per-operation hard policy, method, key, ambiguity |
| remaining healthy capacity | physical and route allocation after concrete target set |
| active quarantine count | per route/service/environment caps |
| current queue/headroom | prevents shifting load onto saturated peers |
| previous action/reintegration | avoids conflicting or oscillating changes |
| current incident conflicts | concrete membership/route/version overlap |
| cooldown/flapping | policy timer and recurrence count |
| deployment version | target/control cohort and stable capacity |
| route criticality | raises evidence/reserve/approval requirements |
| rollback availability | exact snapshot plus action-specific safe compensation |
| HAProxy expressibility | target exists in predeclared structure and command supported |
| controller/config generation | rejects stale plans and unmanaged state |
| operator override | higher-priority intent and expiry |

## 3. Concrete routing-unit representation

Routing units are not merely ordinal names. Each candidate resolves to a concrete target set and policy delta:

| Unit | Concrete target |
|---|---|
| `NO_CHANGE` | empty set |
| `INSTANCE_WEIGHT` | all logical memberships sharing one physical `instance_id`, absolute new weights |
| `COMPLETE_INSTANCE` | all memberships sharing `instance_id`, requested drain/maint state |
| `ROUTE_INSTANCE` | one `(route_group_id, instance_id)` membership |
| `COMPLETE_ROUTE` | route policy plus, only if needed, all route memberships |
| `VERSION_GROUP` | union of memberships whose instances carry one `deployment_version_id` |
| `GLOBAL_TRAFFIC_POLICY` | named predeclared environment policy; never an arbitrary config edit |

Some units are incomparable: a small whole-instance weight reduction can remove less capacity than a complete route-instance drain under a particular traffic mix. Selection therefore uses concrete lost-capacity/action-risk cost rather than a fixed enum ranking.

## 4. Evidence certificate templates

| Candidate | Evidence required before automatic action |
|---|---|
| route × instance | target abnormal; same-route peer controls healthy; same-instance other-route controls healthy; overload/shared/version alternative rejected or weaker |
| instance weight/drain | multi-route abnormality or hard reachability; same routes on peers healthy; physical capacity accounting complete |
| complete route policy | route abnormal across quorum; other routes/instances healthy enough; retries/load behavior known; no useful member-local target |
| version group | suspect cohort abnormal against control cohort under comparable traffic; membership/version mapping current; stable capacity sufficient |
| global policy | widespread overload or operator-declared emergency; critical approval; no narrower admissible target | 

Any required contrast marked `INSUFFICIENT` makes the automatic candidate inadmissible.

## 5. Safety invariants and initial policy defaults

Defaults are lab starting values, not universal production limits.

| Invariant | Initial lab policy |
|---|---|
| critical route reserve after action | at least 50% of configured nominal route capacity and at least 2 eligible instances where topology permits |
| noncritical route reserve | at least 30% and at least 1 eligible instance |
| max automatically quarantined memberships per route | min(1, 33% rounded down/up by explicit policy); with three instances, one |
| max automatic complete-instance drains | one at a time; blocked if any critical route loses reserve |
| max version removal | only if a control version retains reserve and one live representative per critical route |
| high-criticality completeness | ≥0.85 plus all required controls |
| other automatic completeness | ≥0.70 plus all required controls |
| class-confidence starting threshold | route/action-specific, initially 0.80 for destructive action; hard-down rules separate |
| action plan expiry | 15 seconds incident action |
| verification/rollback snapshot | mandatory |
| concurrent actions | one per environment MVP |

Policies must be calibrated against real capacity. A count/percentage guard is insufficient when all remaining targets are saturated, so queue and headroom gates also apply.

## 6. Selection algorithm

```text
select_action(classification, certificate_matrix, policy, desired, observed):
  if stale inputs, unmanaged config, writer ambiguity, or operator freeze:
      return BLOCK or REVIEW

  candidates = enumerate_HAProxy_expressible_target_sets(classification)
  admissible = []

  for candidate in candidates:
      certificate = build_scope_certificate(candidate)
      if required evidence not PASS:
          reject(candidate, "unsupported scope")
          continue
      requested = choose_bounded_magnitude(candidate, confidence, hard_failure)
      capacity = calculate_physical_and_route_capacity_after(requested)
      retry = evaluate_retry_policy(classification, route, methods, ambiguity)
      conflicts = resolve_overlapping_actions_and_overrides(candidate)
      rollback = validate_snapshot_and_action_specific_compensation(candidate)
      if any hard invariant fails:
          consider deterministic downgrade; otherwise reject
          continue
      cost = lost_ground_truth_predicted_healthy_capacity
           + criticality_weighted_scope
           + changed_membership_count
           + retry_amplification_risk
           + uncertainty_and_conflict_penalty
           + structural/reload_penalty
           + rollback_difficulty
      admissible.append(candidate, requested, certificate, cost)

  if none: return NO_CHANGE or REVIEW with reasons
  choose minimum cost
  ties -> more reversible, runtime-only, smaller magnitude
  unresolved tie -> REVIEW
```

The engine does not know ground truth in production; `predicted_healthy` comes from certificate controls and is marked as such. Research evaluation later compares it to injected ground truth.

## 7. Failure-class mapping

| Class | Preferred minimum action | Why not smaller? | When broadened/downgraded |
|---|---|---|---|
| `HEALTHY` | `NO_CHANGE` | no supported fault | manual maintenance only |
| `INSTANCE_DOWN` | `COMPLETE_INSTANCE` drain across all memberships | one membership would continue sending other routes to unreachable endpoint | block/review if capacity reserve fails; `maint` only for confirmed hard down/admin policy |
| `INSTANCE_DEGRADED` | `INSTANCE_WEIGHT` bounded reduction | evidence spans routes but endpoint still serves; full drain is unnecessarily irreversible | broaden to drain if bounded reduction verifies strongly and capacity permits; downgrade/review if peers saturated |
| `ROUTE_INSTANCE_FAILURE` | `ROUTE_INSTANCE` weight reduction or drain | cell-level certificate supports exact membership | broaden only if later evidence shows instance/version scope; downgrade to small weight if confidence near threshold |
| `SHARED_ROUTE_FAILURE` | `COMPLETE_ROUTE` retry suppression, then rate/concurrency or fail-fast | member ejection only moves the same failure and can remove all route capacity | global only if other routes/whole service overload; review if no safe route failure response configured |
| `TRAFFIC_OVERLOAD` | affected route policy; service/global named policy only for corresponding scope | ejecting healthy busy members concentrates load | downgrade to retry suppression alone if load-shed policy/semantics absent |
| `VERSION_SPECIFIC_FAILURE` | `VERSION_GROUP` weight/drain | single member leaves other faulty cohort members active | downgrade to bounded cohort weight/review if control capacity insufficient |
| `UNKNOWN` | `NO_CHANGE` + evidence collection/review | no scope is safely supported | a separate hard overload/retry rule may suppress retries, but that action is justified by the hard rule, not `UNKNOWN` ML output |

### When the smallest unit cannot be expressed

If route × instance control is not predeclared in HAProxy, the controller must not automatically generate/reload structure during the incident. It chooses:

1. a safe bounded broader existing unit if its own evidence certificate passes and capacity permits;
2. a non-destructive route retry/load policy if applicable;
3. otherwise `NO_CHANGE`/review.

It never pretends a broader action is equivalent to the unsupported smaller unit.

## 8. Retry safety is independent

### Definitions

- **Safe retry:** method/operation semantics and failure phase permit replay without changing intended server state; policy permits one different-instance attempt.
- **Unsafe retry:** operation can duplicate/alter effects, idempotency is unproven, or a response may have been lost after execution.
- **Conditional retry:** allowed only when a valid idempotency key and backend deduplication contract are configured and the failure phase is permitted.
- **Suppressed retry:** effective retry count is zero because shared failure, overload, budget, method, ambiguity, or operator policy blocks replay.

HTTP semantics follow [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html): GET/HEAD are safe; PUT and DELETE are idempotent at the protocol semantics level, but application conformance still must be declared. The `Idempotency-Key` header remains an IETF work item rather than a final universal guarantee; a key is useful only if the application validates uniqueness and deduplicates the operation. See the [IETF draft](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header).

### Method matrix

| Method | Default cross-instance retry | Conditions |
|---|---|---|
| `GET` | max one | only configured transient connection/pre-response/selected gateway failures; no retry during shared route failure/overload; streaming/range policies explicit |
| `HEAD` | max one | same as GET |
| `PUT` | none until route declares RFC-conformant idempotency | max one when declared, request body replayable, and failure class not shared/overload |
| `DELETE` | none until route declares application idempotency | max one only when repeated delete has equivalent intended effect and response-loss policy permits |
| `POST` | none | conditional max one only with valid key + backend durable dedup contract + route allowlist; payment/order remains none by default |
| `PATCH` | none | only if operation-specific conditional/idempotent contract is proven; default prohibited |
| other/custom | none | explicit reviewed route policy required |

### Failure-phase matrix

| Failure phase | Safe-method posture | Conditional/unsafe posture |
|---|---|---|
| connect failed before any backend connection/body | one retry if budget/class permits | conditional route policy may allow if definitely not sent |
| backend reset before request bytes sent | one retry | same conditional rule |
| failure while sending body | only if operation is replay-safe and body buffered within cap | no retry by default |
| response timeout after complete request sent | GET/HEAD may retry once only if policy accepts duplicate execution/load | unsafe/conditional requires durable dedup; checkout default no |
| response lost after headers/body began | no proxy retry | no retry; client receives failure/partial semantics |
| 502/503/504 response | route allowlist, max one | only conditional contract; never blindly retry payment POST |
| 429 | do not immediately retry at proxy | respect/load-shed; client may follow documented `Retry-After` |

### Shared failure and overload

`SHARED_ROUTE_FAILURE` and `TRAFFIC_OVERLOAD` force cross-instance retry suppression because another attempt is unlikely to find an independent healthy member and increases work. The hard retry engine can suppress before the scope classifier is fully resolved if queue/retry amplification crosses a deterministic emergency rule.

### Budget and measurement

MVP enforces:

- maximum one cross-instance retry per original request;
- zero for unapproved operations;
- zero during shared/overload policy state;
- bounded total HAProxy attempts so connection retries plus redispatch cannot accidentally exceed the contract;
- per-route `retry_amplification_factor = total_backend_attempts / original_requests` measurement and alert.

A proportional concurrent retry budget is later work unless HAProxy’s tested configuration can enforce it without unsafe complexity. The project does not claim a budget it only observes.

### Deduplication expectation

For a conditional POST/PATCH retry, the customer must store `(route, idempotency_key, canonical_request_hash, result/status)` durably for longer than the retry horizon, reject key reuse with a different payload, and return the original result for duplicates. The load balancer only checks presence/format and policy; it cannot prove correct backend deduplication.

## 9. Durable healing action schema

Every action includes:

```text
action_id, incident_id, project/environment/service IDs
controller_generation, action_sequence, idempotency_key
classification/fingerprint/certificate IDs and versions
target_routing_unit, concrete target memberships/policy keys
previous_desired_state, previous_observed_state
bounded_requested_state, final_requested_state
confidence, completeness, conflicts, safety_result/reasons
expected_technical_effect and unaffected_preservation_set
verification criteria, rollback criteria/strategy
policy/model/config versions and observed HAProxy process ID
expiry, actor type/ID, approval IDs
created/prepared/applied/confirmed/verified/completed timestamps
HAProxy attempt/result/readback references
```

State snapshots are structured typed values, not raw configuration text alone.

## 10. Action lifecycle

```text
PLANNED
 -> SAFETY_CHECKED
 -> PREPARED
 -> APPLIED
 -> STATE_CONFIRMED
 -> VERIFYING
 -> COMMITTED

Terminal alternatives:
  ROLLED_BACK
  SUPERSEDED
  EXPIRED
  CANCELLED_BEFORE_APPLY
  NEEDS_REVIEW
```

`ROLLING_BACK` is a nonterminal compensation state. `COMMITTED` means the incident mitigation is retained, not that the backend is healthy. Reintegration is a linked state machine.

### Transition rules

- lifecycle can advance only by compare-and-swap from the expected state/version;
- every transition has an audit/outbox event;
- cancellation after `APPLIED` is compensation, not a state deletion;
- action cannot be edited after `PREPARED`; replanning creates a superseding action;
- terminal history is never reused for another attempt.

## 11. PREPARE, bounded apply, commit, and abort

### `PLANNED -> SAFETY_CHECKED`

Re-evaluate evidence/safety against current desired/observed snapshots. Store all candidate rejection reasons and the selected cost. A plan that expires or changes version ends before mutation.

### `SAFETY_CHECKED -> PREPARED`

- acquire environment execution lock;
- capture all target and unaffected-control states;
- compute physical/route capacity after each ordered step;
- persist absolute requested values and rollback strategy;
- ensure no structural change/reload is required;
- write the durable transition before any HAProxy command.

### `PREPARED -> APPLIED`

Issue ordered absolute commands. For high-confidence hard down, bounded state may equal final drain. For ambiguous degradation, bounded state is a weight reduction. Persist each attempt and readback.

### `APPLIED -> STATE_CONFIRMED`

Require complete observed match for the intended bounded state and expected non-target unchanged state. Partial match invokes recovery.

### `STATE_CONFIRMED -> VERIFYING -> COMMITTED`

Verification must return `EFFECTIVE` and no safety invariant may have become false. Expanding from bounded to final state repeats prepare/capacity/readback for that step.

### Abort/rollback

An un-applied action is cancelled/expired without HAProxy mutation. An applied action enters `ROLLING_BACK` only if the rollback strategy is safe. It sets exact previous values, reads back, and ends `ROLLED_BACK`. If restoring suspected traffic is unsafe, the policy may hold the current safer state and enter `NEEDS_REVIEW`; this is not mislabeled rollback.

## 12. Healing transaction sequence

```mermaid
sequenceDiagram
    participant D as Decision/safety engine
    participant DB as PostgreSQL
    participant W as Single writer
    participant H as HAProxy
    participant V as Verification engine

    D->>DB: PLANNED with evidence certificate and pinned versions
    W->>DB: Lock/re-read; SAFETY_CHECKED
    W->>H: Read complete current state
    H-->>W: Observed snapshot/process/config IDs
    W->>DB: PREPARED with prior, bounded, final and rollback states
    W->>H: Absolute bounded set operation(s)
    H-->>W: Command result
    W->>H: Read exact targets and preservation controls
    H-->>W: Observed state
    W->>DB: APPLIED then STATE_CONFIRMED
    W->>V: Begin bounded verification
    V-->>W: EFFECTIVE / INEFFECTIVE / HARMFUL / INSUFFICIENT
    alt Effective and final state equals bounded
        W->>DB: COMMITTED
    else Effective and safe expansion needed
        W->>H: Apply final absolute state; read back
        W->>V: Verify expanded state
        V-->>W: Outcome
        W->>DB: COMMITTED or compensation state
    else Safe rollback required
        W->>DB: ROLLING_BACK
        W->>H: Restore exact safe prior state
        H-->>W: Readback
        W->>DB: ROLLED_BACK
    else Ambiguous or rollback unsafe/failed
        W->>DB: NEEDS_REVIEW; freeze overlapping automation
    end
```

**Explanation:** persistence precedes mutation, HAProxy state is always read back, and “abort” after apply is an explicit compensated transition rather than pretending the command never happened.

## 13. Edge-case handling

| Case | Required behavior |
|---|---|
| duplicate API/action request | return original resource for same key/hash; 409 for key reused with different request |
| overlapping automatic actions | later plan blocked/superseded; environment serialized |
| controller restart | observe first, adopt matching state, resume or compensate; never assume command outcome |
| HAProxy restart | detect process ID, read config/state, replay current desired absolute values |
| timeout during apply | read target; match means ack lost; mismatch may retry once; ambiguity → review |
| apply succeeded, acknowledgment lost | record `APPLIED_ACK_LOST` after matching readback |
| verification unavailable | `INSUFFICIENT_EVIDENCE`; no commit; hold/restore per policy |
| load rises after prepare | recheck before every command; block remaining steps if reserve fails |
| rollback fails | critical alert, `NEEDS_REVIEW`, freeze overlap, preserve least-risk known observed state; no infinite toggling |
| operator override arrives | stop before next mutation; resolve priority; applied state compensated only if operator target requires it |
| action expires before apply | `EXPIRED`; no command |
| action expires while verifying | complete current evidence window only if policy permits; do not expand; hold/restore/review |
| unmanaged configuration change | freeze writes; drift incident; adopt or reapply only through operator workflow |

## 14. Proof and audit reconstruction

An investigator can reconstruct:

```text
incident -> observation windows -> fingerprint -> rules/ML outputs
-> conflicts/completeness -> evidence certificate -> rejected candidates
-> selected safety result/cost -> prior state -> each HAProxy attempt/readback
-> verification windows -> commit/rollback/review -> reintegration stages
```

If any link is missing, the UI marks the Decision Trace incomplete. An LLM report cannot fill missing evidence.


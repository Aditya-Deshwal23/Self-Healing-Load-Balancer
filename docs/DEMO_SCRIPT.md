# EBMSH Live Demo Script

## Start Clean

From the repository root:

```sh
./local-reset
```

This removes this Compose project's PostgreSQL, Redis, Prometheus, and HAProxy state volumes, rebuilds the default stack, and starts the lab. The measured clean run printed:

```text
Local LAB is ready: https://192.168.0.101:8443
```

The default Compose profile contains 11 services. Elasticsearch, Logstash, and Kibana are excluded unless the `observability-full` profile is enabled.

For a normal cold start that preserves state:

```sh
./local-up
```

Sign in at the URL printed by `./local-up` as `researcher@shlb.local`. Read the password from `.secrets/bootstrap_password`; it is not printed by the startup script. The traffic generator runs continuously at the measured demo load of 40 requests per second and emits 10-second outcome windows.

## Scenario 1: Checkout x inst-b

Create `CHECKOUT_INST_B_FAILURE` in Lab. This is the flagship route-instance fault.

Observed proof:

- MTTD query row: `ROUTE_INSTANCE_FAILURE`, `3.679867` seconds from fault application to rule detection.
- Smoke proof: the worker persisted the incident, planned and committed `ROUTE_MEMBERSHIP_QUARANTINE`, and targeted `be_checkout/srv_inst_b`.
- `inst-b` remained ready for public, auth, and catalog; checkout traffic was excluded from inst-b while peers served it.
- Clearing the fault completed `PROBING -> 5% -> 20% -> 50% -> 100% -> HEALTHY` reintegration.
- The incident resolved and checkout/inst-b returned to ready weight 100.

Run the complete flagship proof:

```sh
./local-smoke
```

## Scenario 2: Auth x inst-a

Create `AUTH_INST_A_FAILURE` in Lab. This scenario was added to exercise a different route-instance cell.

Observed proof:

- Request-to-active: `2.118` seconds.
- Active-to-incident: `6.074` seconds.
- Request-to-incident: `8.192` seconds.
- Decision Trace class: `ROUTE_INSTANCE_FAILURE`, confidence `0.98`, completeness `1`.
- Rule evidence: auth/inst-a had 36 samples and 23 errors (`0.6389`); auth peers were healthy; public, catalog, and checkout on inst-a were healthy; the endpoint was reachable and its direct probe failed.
- Capacity gate: total physical capacity `300`, remaining physical capacity `200`, remaining `66.7%`, minimum reserve `50%`, peer queues `0`; the gate allowed the action.
- Selected target: `be_auth/srv_inst_a`; the action committed as `ROUTE_MEMBERSHIP_QUARANTINE`.
- Other inst-a routes remained preserved.
- Clearing the fault completed reintegration at `HEALTHY`.

During this run, the traffic generator produced real 10-second windows including `auth:5xx` outcomes, followed by normal 2xx windows after recovery.

## Scenario 3: All Checkout Instances

Create `SHARED_CHECKOUT_FAILURE` in Lab. This tests the non-actionable shared-route branch.

Observed proof:

- Request-to-active: `2.033` seconds.
- Active-to-incident: `6.050` seconds.
- Request-to-incident: `8.083` seconds.
- Decision Trace class: `SHARED_ROUTE_FAILURE`, confidence `0.97`, completeness `1`.
- All checkout cells failed: inst-a, inst-b, and inst-c each reported 40 samples and 40 errors (`1.0` error rate) in the live matrix.
- Capacity gate: `safety_inputs.evaluated=false` because this class is not actionable.
- Candidate action: `NO_ACTION`.
- New HAProxy actions: none.
- All checkout memberships remained ready at weight 100.
- Clearing the fault resolved the incident without quarantine.

The traffic generator captured checkout 5xx windows during the fault and normal checkout 2xx windows afterward.

## MTTD Query Results

Run the existing query against the live Postgres instance with the seeded environment ID:

```sh
sed "s/:environment_id/'40000000-0000-4000-8000-000000000001'/g; s/:after_applied_at/NULL/g" \
  benchmarks/extract_mttd_shadow_vs_rules.sql \
  | docker compose exec -T postgres sh -lc \
    'PGPASSWORD="$POSTGRES_PASSWORD" psql -v ON_ERROR_STOP=1 -U shlb_api -d shlb'
```

The measured rows were:

| Scenario | Classification | Rule MTTD |
|---|---|---:|
| `CHECKOUT_INST_B_FAILURE` pre-fix attempt | `UNKNOWN` | `20.202928` seconds |
| `CHECKOUT_INST_B_FAILURE` corrected run | `ROUTE_INSTANCE_FAILURE` | `3.679867` seconds |

Both rows had null shadow timing/signal columns in that query output.

## Reset Between Scenarios

Clear the active Lab fault through the Lab UI or the authenticated fault-control API, then wait for the incident to resolve and the staged reintegration to reach `HEALTHY`. For a guaranteed clean baseline between demonstrations, run:

```sh
./local-reset
```

Do not run a second scenario while a previous Lab fault is active. The API rejects overlapping active faults.

## Final Proof Bundle

Run these commands in order from the repository root:

```sh
docker compose exec -T control-api pytest
python3 scripts/test_safety_scenarios.py
./local-smoke
```

The measured clean-state result was:

- Control API: `40 passed`, with one read-only pytest-cache warning.
- Safety scenarios: UNKNOWN, SHARED_ROUTE_FAILURE, and INSTANCE_DOWN detection, non-actionability/action safety, quarantine, and recovery passed.
- Smoke: flagship incident persistence, route-local action, unaffected-route preservation, staged reintegration, and resolution passed.

## End

```sh
./local-down
```

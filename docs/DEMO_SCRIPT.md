# EBMSH Golden Demo Runbook

This runbook records the measured Part 2 Golden Demo path. The physical
instances are the repository's `inst-a`, `inst-b`, and `inst-c` identities;
the demo labels them node-a, node-b, and node-c. No result below is estimated.

## Start Clean
Start a disposable stack with topology seed rows disabled so the registry API
is the only topology writer:

```sh
SHLB_SEED_TOPOLOGY=false ./local-reset

The measured stack became ready at:
```text
https://192.168.0.101:8443
```

The seeded `admin@shlb.local` account has the `PROJECT_ADMIN` role. The
password is stored in `.secrets/bootstrap_password`.

## Step A: Provision Topology
Through the authenticated registry API, create these route groups:

| Route | Priority | Criticality |
|---|---:|---|
| `auth` | 10 | `HIGH` |
| `catalog` | 20 | `STANDARD` |
| `inventory` | 30 | `STANDARD` |
| `checkout` | 40 | `CRITICAL` |

Create `inst-a`, `inst-b`, and `inst-c` as active backends with port `8080`,
capacity `100`, and probe profile `phase1-http-healthz`. Pair every backend
with each route using its `be_` backend name, its `srv_inst_` server name, and baseline weight
`100`.
Measured API checkpoint:

- 12 matrix cells were present.
- Routes were `auth`, `catalog`, `checkout`, and `inventory`.
- Instances were `inst-a`, `inst-b`, and `inst-c`.
- Every desired cell was `ready/100`.

## Step B: Generate and Start HAProxy
Render `RouteGroup`, `BackendInstance`, and `RouteMembership` rows with
`control-api/src/shlb_api/haproxy_config.py`. The generated configuration
contained two inventory ACL lines, one `be_inventory` block, and twelve
inventory backend server lines across the four route blocks. HAProxy syntax
validation passed, and the temporary generated-config stack returned HTTP 200
from the edge health endpoint.
The checked-in `haproxy/haproxy.cfg` remains unchanged. Deployment-time config
generation is separate from Runtime API actuation.

## Step C: Prove Baseline Traffic
Run traffic across the Golden routes:

```sh
docker compose run --rm --no-deps \
  -e TRAFFIC_ROUTES=auth,catalog,inventory,checkout \
  -e TRAFFIC_PROFILE_JSON='[{"routes":"all","requests_per_second":40,"duration_seconds":20}]' \
  traffic-generator
```

Measured 10-second window:

```json
{"event":"traffic_window","seconds":10,"outcomes":{"auth:2xx":100,"catalog:2xx":100,"inventory:2xx":100,"checkout:2xx":100}}
```

## Step D: Inject and Observe a Real Fault

Keep the four-route traffic stream active and inject `AUTH_INST_A_FAILURE`
through the authenticated LAB API. The measured request-to-active time was
`2.043` seconds.

The inventory-inclusive run then produced:

- Incident classification: `UNKNOWN`.
- Request-to-incident time: `22.216` seconds.
- Decision Trace final class: `UNKNOWN`.
- Evidence certificate: present.
- Action: absent; no HAProxy mutation occurred.
- `auth/inst-a`: desired `ready/100`, observed `ready/100`.

This is a measured Golden Demo limitation, not a successful route-instance
healing result. The current evidence collector still enumerates only the
original four-route fixture contract in `worker_io.py`, so inventory is not
included in the mandatory comparison set. The fault was cleared through the
API and no active fault remained.

## Step E: Shadow Signal Evidence

Run the fixed `GRAY_FAILURE_INST_A` for at least 60 seconds under background
traffic, then execute:

```sh
sed "s/:environment_id/'40000000-0000-4000-8000-000000000001'/g; s/:after_applied_at/NULL/g" \
  benchmarks/extract_mttd_shadow_vs_rules.sql \
  | docker compose exec -T postgres psql -U shlb_api -d shlb
```

Measured result from the fixed gray run:

- `shadow_mttd_seconds`: `5.427392`.
- `mttd_rules_seconds`: `NULL`.
- No rule incident or quarantine was created.
- The fault was cleared through the authenticated API.

## Step F: Benchmark Review

Run the four-condition benchmark and plotting post-processing:

```sh
python3 benchmarks/run_experiments.py
python3 benchmarks/plot_results.py
```

Measured `benchmarks/results.csv` rows:

| Condition | Requests | Failure rate | Mean ms | P95 ms | P99 ms |
|---|---:|---:|---:|---:|---:|
| `baseline_round_robin` | 21682 | 1.0 | 1.38 | 2.03 | 4.15 |
| `gray_failure_without_shlb` | 20374 | 1.0 | 1.47 | 2.26 | 3.68 |
| `gray_failure_shlb_active` | 13504 | 1.0 | 2.21 | 4.12 | 7.99 |
| `traditional_proxy_ejection` | 18864 | 1.0 | 1.58 | 2.34 | 3.40 |

The generated chart files were measured at `85592` bytes for
`benchmarks/latency_percentiles.png` and `50281` bytes for
`benchmarks/failure_rate.png`.

The benchmark runner's HTTPS client did not disable verification for the
self-signed local certificate, so its recorded failure rates are the measured
results of that run and are not presented as application-failure claims.

## Cleanup

Clear any active LAB fault through the authenticated API and confirm that no
fault has status `REQUESTED`, `ACTIVE`, or `CLEAR_REQUESTED`. For a disposable
clean stack:

```sh
./local-down
```

The current Golden inventory walkthrough is pending the earlier evidence
collector generalization; no successful inventory incident MTTD or recovery
timing is claimed here.

## Regression Proof

For the original seeded 4x3 topology, the measured regression bundle passed:

```sh
git log -1 --oneline
docker compose exec -T control-api pytest
python3 scripts/test_safety_scenarios.py
./local-smoke
```

The control API suite reported `40 passed`; the safety suite and flagship
smoke completed successfully.
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

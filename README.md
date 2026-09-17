# Self Healing Load Balancer

This repository is a compact local-network prototype of Evidence-Bounded Minimum-Scope Healing (EBMSH). It demonstrates a deliberately narrow claim: when checkout fails only on one physical backend, the controller can prove the scope, quarantine only that route membership in HAProxy, verify both symptom relief and unaffected-route preservation, then restore traffic through evidence-gated stages.

The flagship path is real. It uses generated traffic, backend request metrics, direct probes, PostgreSQL records, a sole-writer worker, HAProxy Runtime commands and Runtime readback. The local Compose profile also includes an internal Elasticsearch/Logstash/Kibana forensic stream: NGINX and HAProxy emit structured syslog events to Logstash, which indexes them in Elasticsearch for correlation and investigation. ML, Ollama and LLM-generated recommendations are intentionally not required for operation.

## Start the local LAB

Prerequisites are Docker Desktop, OpenSSL, and a Mac or Linux host on the target LAN.

```sh
./local-up
```

The command safely creates ignored local secrets, detects the current LAN IPv4 address, generates a 30-day development certificate, builds the compact Compose profile, waits for semantic health, and prints the HTTPS URL. Only NGINX publishes host ports:

- `0.0.0.0:8081` redirects to HTTPS;
- `0.0.0.0:8443` serves the console, REST/SSE API and demo application traffic.

Sign in as `researcher@shlb.local`. The generated password is stored at `.secrets/bootstrap_password` and is intentionally never printed by the lifecycle scripts.

Useful lifecycle commands:

```sh
./local-status             # service health, LAN URL and published ports
./local-smoke              # complete checkout/B healing and recovery journey
./local-down               # stop containers; retain volumes and certificate
./local-reset              # remove only this Compose project's volumes, then rebuild
./local-cert-regenerate    # regenerate for the current LAN address and reload NGINX
```

If automatic address detection is unsuitable, provide an address without committing it:

```sh
SHLB_LAN_IP=192.168.1.25 ./local-up
```

The ignored `.env` then supplies the matching allowed Origins to the API. Browser REST and SSE requests use same-origin relative `/api/...` paths; no browser bundle contains a localhost API base URL.

## Certificate use on the LAN

The certificate contains SAN entries for `localhost`, `edge-nginx`, `127.0.0.1`, and the selected LAN IPv4 address. It is self-signed and intended only for this local LAB.

For a quick demonstration, open the printed `https://<LAN-IP>:8443` address and accept the browser's development-certificate warning. For a warning-free device, transfer only `.local-certs/lab.crt`—never `lab.key`—to that device and trust it for local TLS:

- macOS: add the certificate in Keychain Access and set its trust policy for this LAB;
- iOS/iPadOS: install the profile, then enable trust under Settings → General → About → Certificate Trust Settings;
- Android/Windows: import it into the user trusted-certificate store following the device's local-certificate procedure.

Regenerate after a DHCP address change. Never distribute or commit the private key.

## Flagship operator journey

1. Open **Lab** and select **Checkout fails on Backend B**.
2. The authenticated mutation is accepted only in the LAB environment for a Researcher, Project Admin or System Admin and requires the session CSRF token plus an idempotency key.
3. The worker applies independent, auto-expiring ground truth to the private Backend B fault endpoint.
4. Real request outcomes and direct probes establish:
   - `checkout × inst-b` is failing;
   - checkout on A and C is healthy;
   - public, auth and catalog on B are healthy;
   - B is reachable, so the scope is not instance-wide;
   - remaining physical capacity and peer queues pass policy.
5. PostgreSQL receives an incident, observation window, fingerprint, deterministic classification, evidence certificate and candidate actions/rejection reasons.
6. The worker commits a `PREPARED` action and desired state before sending absolute HAProxy Runtime operations for `be_checkout/srv_inst_b`.
7. Runtime readback must confirm drain/weight zero and unchanged B siblings before the action can enter verification.
8. Verification requires real checkout samples, low checkout error rate, healthy B siblings, safe peer queues and aligned desired/observed state. Zero samples are never success.
9. Clearing the fault starts `PROBING → 5% → 20% → 50% → 100% → HEALTHY`. Every transition is sample-, probe- and readback-gated.
10. REST polling and a single environment SSE connection update the console throughout the lifecycle.

Run the same journey without the UI:

```sh
./local-smoke
```

Additional deterministic safety coverage is available with:

```sh
python3 scripts/test_safety_scenarios.py
```

It proves that conflicting `UNKNOWN` and shared-checkout failures create no destructive action, while a supported `INSTANCE_DOWN` drains exactly B's four memberships after counting B's physical capacity once.

## Architecture and authority

The request path is independent of the control plane:

```text
LAN client
  → NGINX :8443
    → HAProxy :8080
      → be_public | be_auth | be_catalog | be_checkout
        → inst-a | inst-b | inst-c
```

The control path is separate:

```text
traffic + probes + HAProxy Runtime readback
  → sole-writer rules worker
    → PostgreSQL durable records
    → HAProxy Runtime absolute mutation
    → Runtime readback
    → verification / rollback / reintegration
    → PostgreSQL outbox → Redis stream → authorized SSE
```

Network boundaries are intentional:

- `edge-nginx` is the only service with published ports;
- `control-api` joins `api_edge_net` and `control_data_net`, but has no data-plane, observability, backend, or Runtime access;
- NGINX alone bridges `api_edge_net` to `data_edge_net`; containers on those networks cannot route through it;
- `control-worker` alone joins the private backend/observability networks and mounts the Runtime socket;
- Prometheus, PostgreSQL, Redis, HAProxy stats, the Runtime socket and backend management/fault paths are not published;
- the structural HAProxy Data Plane API is not started in this Runtime-only prototype;
- PostgreSQL is durable truth; Redis is coordination, session and event-stream infrastructure only;
- a PostgreSQL advisory lock and a bounded Redis lease prevent two workers from holding write authority;
- all automatic targets are predeclared HAProxy backend/server objects. Structural reconfiguration is not automated.

Default memory limits total roughly 2.1 GiB across the eleven containers. Prometheus retention is capped at two hours/256 MB, JSON logs rotate, the worker is single-threaded and non-overlapping, database pools and probe/request timeouts are bounded, and the traffic source is capped at 40 requests per second.

All accelerated demonstration thresholds and timings—including evidence windows, leases, verification timeouts, queue bounds, action expiry, stage cooldowns, stage samples and retry limits—live in the single immutable `LAB_POLICY` in `worker_policy.py`; the control loop does not scatter sleep constants across workflows.

## Durable operational model

Alembic migration `20260802_0002_vertical_slice.py` adds:

- incidents, observation windows, fingerprints and classifications;
- evidence certificates and desired route states;
- actions, action attempts and observed-state snapshots;
- verification results;
- reintegration runs and stages;
- LAB faults and controller generations.

An action stores its generation, exact target, previous desired/observed state, requested absolute state, expected effect, preservation set, verification obligations, rollback plan, expiry and attempt sequence before mutation. A lost acknowledgment is reconciled through readback and is never blindly retried. An ambiguous result enters `RESULT_UNKNOWN`/`NEEDS_REVIEW`.

## Real API surface

Authenticated reads include:

- `GET /api/v1/system/status`
- `GET /api/v1/system/capabilities`
- `GET /api/v1/environments/{id}/operational-summary`
- `GET /api/v1/environments/{id}/matrix`
- `GET /api/v1/environments/{id}/incidents`
- `GET /api/v1/incidents/{id}`
- `GET /api/v1/incidents/{id}/decision-trace`
- `GET /api/v1/environments/{id}/actions`
- `GET /api/v1/actions/{id}`
- `GET /api/v1/environments/{id}/reintegration`
- `GET /api/v1/reintegration/{id}`
- `GET /api/v1/environments/{id}/lab/faults`
- `GET /api/v1/environments/{id}/worker/status`
- `GET /api/v1/events`

LAB fault create/clear mutations require authentication, an authorized role, CSRF, an allowed Origin and an idempotency key; clear also requires `If-Match`. Errors use `application/problem+json`, writes create structured audit/outbox records, and project-scope denials intentionally look like `404`.

SSE publishes incident, classification, action, verification, reintegration, rollback, resolution and drift transitions. `Last-Event-ID` is mapped through bounded Redis cursor keys; an expired cursor produces `resync_required` so the client can refetch authorized REST state. `safe_mode_changed` remains reserved until an operator Safe Mode mutation is implemented; the prototype does not emit a decorative event for a transition it cannot perform.

## Operator console

The primary rail has seven destinations: Overview, Traffic, Incidents, Actions, Recovery, Lab and System. Existing contextual export routes are preserved, but unsupported Phase-2 pages are capability-gated and do not compete with the working workflow.

Ordinary LAB mode uses real REST/SSE data for:

- Command Center;
- route × instance matrix;
- incidents and Decision Trace;
- actions and attempts;
- recovery/reintegration;
- Fault Lab;
- system status.

The old bounded design snapshot remains available only with `/app?demo=1`. It displays a persistent **Simulated data** notice and has no HAProxy authority. Live API failure never silently falls back to fixtures.

The matrix uses a desired-state outer boundary and an observed-state interior, has an explicit drift pattern, supports roving arrow-key navigation, includes a semantic table/cell description, and opens a focus-managed detail dialog. Mobile is intentionally read-only for the critical incident surface; fault injection and routing controls are hidden or disabled.

## Verification commands

```sh
# Frontend strict check, contracts, production export and internal links
cd frontend && npm run verify

# API, persistence and deterministic worker-policy tests in the running image
docker compose exec -T control-api pytest -q

# Migration has no pending model changes
docker compose exec -T control-api alembic check

# Real HAProxy route-isolation invariant
python3 scripts/test_phase1_isolation.py

# Flagship and safety journeys
./local-smoke
python3 scripts/test_safety_scenarios.py

# Auth/RBAC/CSRF/idempotency/SSE/network boundaries and restart recovery
python3 scripts/test_phase2_foundation.py
python3 scripts/test_worker_restart.py
```

The OpenAPI document is at `/api/v1/openapi.json`, with local interactive documentation at `/api/v1/docs`.

## Repository layout

```text
control-api/       FastAPI API plus the separately launched sole-writer worker
demo-backend/      deterministic application, bounded metrics and private fault surface
frontend/          statically exported Next.js/React operator console
haproxy/           four logical pools × three predeclared physical instances
nginx/             sole published TLS edge and static console server
prometheus/        compact bounded evidence profile
traffic-generator/ bounded real evidence source
scripts/           secrets, lifecycle acceptance and isolation checks
docs/design/       frozen architecture/specification dossier
```

## Explicit limits

The current prototype genuinely supports `HEALTHY`, `INSTANCE_DOWN`, `ROUTE_INSTANCE_FAILURE`, `SHARED_ROUTE_FAILURE` and `UNKNOWN` with deterministic rules. Statistical instance degradation, traffic overload control, version-specific classification, ML, ELK, local LLM assistance, multi-node HA, production autoscaling and the full research protocol remain planned and are labelled as unsupported rather than simulated as live capability.

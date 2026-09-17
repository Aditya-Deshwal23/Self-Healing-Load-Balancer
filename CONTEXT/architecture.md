# Architecture Context

## Stack

| Layer                  | Technology                                                              | Role |
| ----------------------- | ------------------------------------------------------------------------ | ---- |
| Frontend Framework      | Next.js 16 / React 19 / TypeScript                                       | Operator and research console |
| | Frontend Data/UI | Hand-authored CSS (semantic classes + custom-property tokens, no framework) + TanStack Query, Recharts, lucide-react icons | Styling, data fetching, charts, icons |
| Control API              | FastAPI (Python)                                                          | REST surface: environments, incidents, actions, decision traces, auth |
| Control Worker           | Python (`shlb_api.worker.ControlWorker`)                                  | Sole HAProxy-mutating process; single-writer via Redis lease |
| Database                 | PostgreSQL + Alembic (`control-api/alembic/`)                             | System of record: topology, incidents, evidence, actions |
| Coordination / Sessions  | Redis                                                                      | Worker leader-election lease, login session store, login rate limiting |
| Data Plane               | HAProxy (Runtime + Stats socket), edge-nginx                              | Traffic routing, weight/admin-state enforcement, TLS edge |
| Observability             | Prometheus                                                                 | Latency/error-rate evidence source consumed by `classify()` |
| Lab fleet                 | `demo-backend-a/b/c`, `traffic-generator`                                 | Reproducible topology and synthetic load for experiments |
| Log stack (present, not on decision path) | Elasticsearch, Logstash, Kibana                          | Available in `docker-compose.yml`; not currently read by the control loop — verify before citing as load-bearing in the paper |

## System Boundaries

- `control-api/src/shlb_api/routers/` — FastAPI request handlers only (auth, projects, registry, operations, system, events); never runs the classify/actuation loop
- `control-api/src/shlb_api/` (worker.py, worker_policy.py, fastpath.py, worker_io.py, models.py, contracts.py, security.py, seed.py, audit.py) — domain logic and the single-writer control loop
- `control-api/alembic/` — schema migrations; the only sanctioned way to change the Postgres schema
- `frontend/app`, `frontend/features/{overview,actions,incidents,lab,traffic,system,recovery}`, `frontend/lib/api` — Next.js app router pages, feature-scoped UI, typed API client
- `haproxy/` — `haproxy.cfg` and the data-plane's runtime socket configuration
- `docs/design/`, `docs/research/` — frozen architecture dossier (00–21) and the IEEE paper draft; authoritative for anything not covered here — do not silently contradict an existing ADR
- `benchmarks/`, `scripts/`, `experiments/` — baseline (B1–B4) runner, safety-scenario tests, experiment manifest — the empirical evidence path for the paper

## Storage Model

- **PostgreSQL**: the only system of record. Structural topology
  (`Environment`, `Project`, `RoutingPolicy`, `DesiredRouteState`,
  `RouteMembership`, `BackendInstance`); the evidence/incident chain
  (`Incident`, `Fingerprint`, `Classification.evidence_support` JSON
  — now carries `shadow_statistical_signal` — `EvidenceCertificate`);
  the action lifecycle (`Action`, `ActionAttempt`, `VerificationResult`,
  `ReintegrationRun`/`Stage`); and raw per-tick telemetry
  (`ObservationWindow.metrics` JSON — includes
  `fast_path_recommendations` with onset timestamps —,
  `ObservedStateSnapshot`).
- **Redis**: ephemeral coordination only — the worker's authority
  lease and login sessions/rate limits. Never treated as durable
  history; losing Redis loses coordination state, not incident data.
- No blob/file storage layer exists yet. Open question: does the
  IEEE reproducibility package need one for raw benchmark artifacts
  larger than fits comfortably in a Postgres JSON column?

## Auth and Access Model

- Self-hosted email/password login (`routers/auth.py`): Redis-backed
  session cookie with idle and absolute expiry, server-side login
  rate limiting, a `bootstrap_password` secret provisions the first
  account. No third-party identity provider is in this repo.
- Ownership scoping is Project → Environment; access is scoped
  per-user in `auth.py`.
- Only the control-worker process holding the Redis authority lease
  may write to the HAProxy Runtime socket. The API and frontend are
  read/intent-only and never touch the socket directly.

## Invariants

1. **Single-writer**: only the control-worker holding
   `worker:authority:lease` in Redis may mutate HAProxy Runtime
   state; no API route or background job touches the admin socket.
2. **Rules-first authority**: `classify()`'s deterministic branches
   are the sole source of `final_class`/`actionable`. The
   HYBRID_SHADOW statistical signal is passed in as annotation only
   (`shadow_statistical_signal`) and cannot change either — enforced
   by a dedicated test, not just convention.
3. **Capacity floor before actuation**: every action must pass
   `route_instance_capacity()`/`instance_capacity()` first;
   `SHARED_ROUTE_FAILURE` is explicitly non-actionable because
   quarantining every peer would violate this floor.
4. **Minimum defensible scope**: a failure is actioned at the
   narrowest scope the evidence supports; instance-wide or
   route-wide scope requires every peer/sibling on that axis to be
   independently failing.
5. **No unverified commit**: every Action moves
   PREPARED → APPLIED → VERIFYING and only reaches COMMITTED after
   dual verification (symptom relief and preserved capacity) passes.
6. **Inference stays out of the request path**: `classify()` and the
   shadow signal run once per worker tick against already-collected
   evidence — never inline with a live HTTP request.
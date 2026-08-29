# Implementation Details

## Docker Compose

**Purpose.** Docker Compose starts the local lab as a repeatable set of containers, networks, volumes, secrets, resource limits, and health checks.

**Why it exists.** The project needs a controlled environment where request traffic, monitoring, the controller, and the three backend instances can interact without exposing internal services to the host network.

**How it works.** `docker-compose.yml` defines NGINX, HAProxy, three demo backends, Prometheus, a traffic generator, the API, the control worker, PostgreSQL, and Redis. Most services use `restart: unless-stopped`; this is Docker's container restart behavior, not a controller action.

**Interaction.** Compose connects the public edge, data plane, control data, backend, and observability networks. Only NGINX publishes host ports.

## NGINX Reverse Proxy

**Purpose.** NGINX is the only public entry point and terminates the local HTTPS connection.

**Why it exists.** It keeps internal services unexposed and provides one URL for the console, API, and demo application routes.

**How it works.** HTTP on port 8080 redirects to HTTPS on port 8443. `/api/` goes to the control API, `/api/v1/events` keeps server-sent events unbuffered, and `/public`, `/auth`, `/catalog`, and `/checkout` go to HAProxy.

**Interaction.** NGINX does not choose a backend. It forwards application traffic to HAProxy and control-plane requests to the API.

## HAProxy Load Balancer

**Purpose.** HAProxy is the application traffic load balancer.

**Why it exists.** It distributes each supported route across the three predeclared backend instances and supplies the routing point the controller can adjust.

**How it works.** HAProxy has four round-robin pools: `be_public`, `be_auth`, `be_catalog`, and `be_checkout`. Each contains instances A, B, and C. It uses HTTP health checks against `/healthz` and exposes internal statistics and Prometheus metrics.

**Interaction.** The control worker reads HAProxy Runtime state through a private Unix socket and can set a server's weight and drain state. The worker never changes HAProxy's structural configuration.

## Health Checks and Monitoring

**Purpose.** Health signals determine whether traffic can safely use a backend and whether an action achieved the intended result.

**Why it exists.** A simple container-up signal is not enough for a route-specific failure. The controller needs request outcomes, direct route probes, and current route membership state.

**How it works.** Compose health checks verify containers. HAProxy checks `/healthz`. Prometheus scrapes HAProxy and backend `/metrics` every two seconds. The worker also makes authenticated direct probes to private backend endpoints.

**Interaction.** The worker combines the metrics, probe results, and HAProxy readback into an observation window before classification or verification.

## Rule Engine

**Purpose.** The rule engine makes deterministic classification and action decisions.

**Why it exists.** The project needs explainable recovery behavior that can be tested without relying on prediction models.

**How it works.** The policy in `worker_policy.py` evaluates evidence against fixed lab thresholds. It supports `HEALTHY`, `INSTANCE_DOWN`, `ROUTE_INSTANCE_FAILURE`, `SHARED_ROUTE_FAILURE`, and `UNKNOWN`. Only supported, sufficiently evidenced cases can lead to an action.

**Interaction.** For a checkout failure limited to backend B, it selects `ROUTE_MEMBERSHIP_QUARANTINE` for `be_checkout/srv_inst_b`. Conflicting or insufficient evidence does not trigger a destructive change.

## Control Worker and Recovery

**Purpose.** The single control worker performs observation, decision making, HAProxy actuation, verification, and recovery progression.

**Why it exists.** Restricting write authority prevents two workers from applying conflicting routing changes.

**How it works.** PostgreSQL advisory locking and a Redis lease give one worker write authority. Before a change, it records the desired state, previous state, target, preservation set, verification criteria, rollback plan, and expiry. It sends an absolute HAProxy Runtime command and reads the state back.

**Interaction.** It writes durable records to PostgreSQL, publishes changes through the outbox/Redis event path, and drives the console updates. The worker routes around a failed service; it does not restart containers or use a Docker socket.

## Supervisor and Container Lifecycle

**Purpose.** There is no separate supervisor component that restarts unhealthy application services in the current codebase. Container lifecycle is handled by Docker Compose.

**Why it exists.** Compose uses `restart: unless-stopped` so a container that exits unexpectedly can be restarted by Docker. This is basic container availability behavior and is distinct from the route-level recovery design.

**How it works.** Compose health checks report service health, while the restart policy reacts to a stopped container process. HAProxy health checks independently remove unavailable backends from its eligible set.

**Interaction.** The control worker observes failures and changes HAProxy membership when its rules permit it. It cannot restart a backend container, call Docker, or act as a general-purpose process supervisor.

## Logging

**Purpose.** Logs support local troubleshooting and test evidence.

**Why it exists.** Operators need to inspect container output, request activity, and worker failures while running the lab.

**How it works.** Services emit structured or JSON-friendly logs to stdout. Docker uses the `json-file` log driver with size and file-count limits. NGINX uses a structured JSON access log and the worker emits JSON event/error records.

**Interaction.** Logs are available with Docker commands such as `docker compose logs`. ELK is not implemented in the current repository, so logs do not flow to Elasticsearch, Logstash, Kibana, or an ELK dashboard.

## Metrics

**Purpose.** Metrics provide the evidence used for classification and post-action verification.

**Why it exists.** The controller must confirm actual request outcomes instead of relying only on configuration state.

**How it works.** Backends export request counts, status-family counts, latency histograms, and active-fault gauges. HAProxy exports its metrics. Prometheus stores a bounded two-hour local history and answers worker queries.

**Interaction.** The traffic generator creates bounded real requests through HAProxy. The worker queries Prometheus as part of each observation and verification cycle.

## Dashboard

**Purpose.** The dashboard gives the operator a live view of the lab state.

**Why it exists.** It makes the recovery process inspectable during a demonstration.

**How it works.** The Next.js/React console reads the control API through REST and receives updates from one server-sent event connection. It includes the command center, route-by-instance matrix, incidents, actions, recovery, lab fault controls, and system status.

**Interaction.** The dashboard displays the persisted control-plane state. It does not directly issue HAProxy Runtime commands.

## Communication Flow

1. A client reaches NGINX over HTTPS.
2. NGINX forwards application requests to HAProxy.
3. HAProxy selects a healthy backend within the requested route pool.
4. Prometheus collects backend and HAProxy metrics while the traffic generator provides real request evidence.
5. The worker reads metrics, direct probes, and HAProxy Runtime state.
6. The rule engine classifies supported failures; the worker persists and applies a narrowly scoped route change when safe.
7. Verification and staged reintegration results are stored and sent to the dashboard through the API event path.

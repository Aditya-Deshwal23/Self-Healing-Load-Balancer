# Viva Questions and Answers

## 1. What is the main purpose of this project?

The project demonstrates a local self-healing load-balancing flow.
It detects supported backend failures using evidence.
It changes HAProxy routing at a limited scope.
It verifies the result before restoring normal traffic.

## 2. What does self-healing mean in this prototype?

It means the system can apply a defined recovery action automatically.
The main action is routing traffic away from an affected membership.
It does not mean that every failure is fixed automatically.
The controller does not restart application containers itself.

## 3. Why is Docker Compose used?

Docker Compose defines the local lab in one configuration.
It starts services, networks, volumes, secrets, and health checks.
This makes the demonstration repeatable on a development machine.
It is not a Kubernetes or cloud deployment.

## 4. Which services run in the Compose stack?

The stack includes NGINX, HAProxy, and three demo backends.
It also includes Prometheus, a traffic generator, API, and worker.
PostgreSQL stores records and Redis supports coordination and events.
The frontend is served through the NGINX edge container.

## 5. What is HAProxy's role?

HAProxy is the application load balancer in the data plane.
It has a separate backend pool for each supported route.
It chooses a server using round-robin balancing.
The worker changes server drain state and weight through Runtime commands.

## 6. What is a reverse proxy in this project?

NGINX is the reverse proxy at the public edge.
It terminates local HTTPS and forwards requests internally.
Application routes go to HAProxy and API routes go to the control API.
This keeps internal services from being directly published.

## 7. How is a load balancer different from a reverse proxy here?

NGINX receives external requests and forwards by URL path.
HAProxy selects one backend among several members of a route pool.
NGINX provides the single edge entry point.
HAProxy provides per-route distribution and health-aware membership.

## 8. How many backend instances are present?

There are three demo backend instances: A, B, and C.
Each is predeclared in all four HAProxy route pools.
The routes are public, auth, catalog, and checkout.
The lab does not create or remove backend instances dynamically.

## 9. What health checks are used?

Docker Compose checks whether key containers are healthy.
HAProxy checks each backend's `/healthz` endpoint.
Prometheus captures request and service metrics.
The worker also makes direct private route probes.

## 10. Why are health checks alone not enough?

An instance can pass `/healthz` while one application route fails.
That is the primary route-specific fault demonstrated by the project.
The controller therefore compares route metrics and direct probes.
It also checks HAProxy's actual runtime state.

## 11. What is the rule engine?

The rule engine is deterministic decision logic in `worker_policy.py`.
It evaluates evidence against fixed lab thresholds.
It classifies a small set of supported conditions.
It does not use machine learning or prediction.

## 12. Which failure classes are supported?

The prototype supports healthy, instance down, and route-instance failure.
It also records shared-route failure and unknown conditions.
Not every class leads to an automatic routing action.
Insufficient or conflicting evidence prevents destructive actions.

## 13. What happens in the main checkout failure scenario?

Checkout fails only on backend B in the lab.
The worker confirms checkout A and C remain healthy.
It also confirms other routes on B still work.
It drains only checkout's membership for B.

## 14. What does route membership quarantine mean?

It removes one server from one HAProxy backend pool.
For the main case, the target is `be_checkout/srv_inst_b`.
It does not remove B from public, auth, or catalog.
This preserves healthy capacity where it is still useful.

## 15. How does the worker change HAProxy state?

The worker has access to HAProxy's private Runtime Unix socket.
It sends an absolute state and weight command for an allowed target.
It then reads the state back from HAProxy.
The API and frontend do not have this Runtime access.

## 16. Why is HAProxy Runtime readback important?

A requested change is not treated as successful just because a command was sent.
Readback checks that HAProxy shows the expected drain state and weight.
The worker also checks that protected memberships stayed unchanged.
This prevents configuration intent from being confused with observed state.

## 17. Does the controller restart unhealthy services?

No. The implemented controller action is routing quarantine and recovery.
It has no Docker socket or host command path.
Docker Compose uses `restart: unless-stopped` for containers.
That Compose behavior is separate from the worker's recovery logic.

## 18. How does Docker restart behavior fit into the demo?

If a container process exits unexpectedly, Compose may restart it.
Stopping a container manually is not the primary route-failure demo.
HAProxy detects unavailable backends with its health check.
The control worker can classify a supported instance-down condition separately.

## 19. What is Prometheus used for?

Prometheus scrapes metrics from HAProxy and each backend every two seconds.
It stores a bounded local metrics history.
The worker queries it for observation and verification evidence.
It is not used for prediction or autoscaling in this project.

## 20. Which backend metrics are exposed?

The demo backends expose request totals by route and status family.
They also expose request latency histograms and an active-fault gauge.
These metrics are generated from actual traffic reaching the backend.
They help identify route-specific failures in the lab.

## 21. Why is there a traffic generator?

The traffic generator sends bounded real requests through HAProxy.
It covers public, auth, catalog, and checkout routes.
This produces evidence before and after a routing action.
Verification does not accept zero traffic samples as success.

## 22. What is the role of direct probes?

Direct probes check a specific route on a specific backend privately.
They distinguish an application-route failure from a general outage.
The probes are authenticated and not publicly exposed.
They complement the aggregate Prometheus metrics.

## 23. What information is stored in PostgreSQL?

PostgreSQL is the durable source of control-plane records.
It stores incidents, observation windows, classifications, and evidence.
It also stores desired state, actions, attempts, verification, and recovery stages.
This allows the console and tests to inspect what happened.

## 24. What is Redis used for?

Redis supports the bounded worker coordination lease.
It also supports sessions and event-stream infrastructure.
PostgreSQL remains the durable source of truth.
Redis is not treated as the authoritative incident store.

## 25. Why is there only one control worker writer?

One writer avoids conflicting HAProxy changes from multiple workers.
The worker holds a PostgreSQL advisory lock and Redis lease.
This is appropriate for the current local prototype.
A distributed rule engine is future work.

## 26. How are actions made safer?

The worker records action details before it mutates HAProxy.
The record includes target, previous state, desired state, and expiry.
It includes verification conditions and a rollback plan.
Readback prevents blind retries after an uncertain result.

## 27. What happens if the evidence is conflicting?

The rule engine can classify the condition as `UNKNOWN`.
The system records or waits for more evidence instead of draining traffic.
This is important because a wrong routing action can harm healthy traffic.
The safety tests cover cases where no destructive action should occur.

## 28. How is recovery verified?

The worker checks real route samples after a routing change.
It checks error bounds, peer queues, and desired versus observed state.
It checks preserved route memberships for the scoped action.
If these conditions do not pass, the action is not simply accepted.

## 29. What happens after the injected fault is cleared?

The worker observes healthy probes and evidence again.
For route quarantine, it begins a reintegration run.
Traffic weight returns in stages: 5, 20, 50, and 100 percent.
Each stage is gated by probes, samples, and HAProxy readback.

## 30. Why not restore all traffic immediately?

The original condition may return under real traffic.
Gradual restoration limits the impact of a recurring problem.
It gives the worker a chance to verify each step.
This is implemented for the route-specific recovery flow.

## 31. How does the dashboard receive updates?

The frontend reads state from REST endpoints in the control API.
It also uses a single server-sent event connection for updates.
The worker writes event records through the PostgreSQL outbox path.
The dashboard displays persisted state rather than controlling HAProxy directly.

## 32. What is shown in the route-by-instance matrix?

The matrix shows route memberships across the three backend instances.
It distinguishes desired state from observed HAProxy state.
It can show a membership such as checkout on B in drain state.
This makes the scope of a routing change visible during the demo.

## 33. Is ELK implemented for logging?

No. Elasticsearch, Logstash, and Kibana are not in the repository.
Services log to standard output and Docker uses the `json-file` driver.
NGINX uses a structured JSON access-log format.
Logs can be inspected with `docker compose logs`.

## 34. How are logs kept bounded?

The Compose logging configuration sets maximum file size and file count.
This prevents the local lab from keeping unlimited container logs.
Prometheus retention is also capped in the Compose configuration.
These are local resource boundaries, not a full logging platform.

## 35. How is the network divided?

The project separates public edge, data-plane, control-data, backend, and observability networks.
Only NGINX publishes host ports.
The worker alone joins the private networks needed for probes and Runtime access.
The API does not have a route to the actuation network.

## 36. Is this system horizontally scalable today?

No. Backend instances are statically declared in HAProxy configuration.
The project does not create new backend containers based on demand.
The current worker is deliberately a sole writer.
Horizontal autoscaling is listed only as future scope.

## 37. Is this a distributed cluster?

No. The project is a single-host local Docker Compose lab.
It uses three backend containers but not multiple control nodes.
There is no cross-node leader election or cluster replication design.
Multi-node clusters are future work.

## 38. What tests are available?

The repository includes a local smoke journey for the primary scenario.
It includes safety scenarios, route-isolation, worker-restart, and foundation tests.
The API has persistence, contracts, and policy tests.
The frontend has unit, accessibility, and end-to-end checks.

## 39. What are the main current limitations?

The recovery logic handles defined lab classifications only.
It does not use ML, cloud services, Kubernetes, or autoscaling.
It does not run ELK and does not restart backend containers itself.
The scope is a controlled local prototype, not a production deployment.

## 40. What are the planned next steps?

Future work includes prediction, predictive scaling, and horizontal autoscaling.
It also includes Kubernetes, cloud deployment, and multi-node clusters.
Advanced monitoring and a distributed rule engine are planned topics.
These areas need separate design, safety checks, and implementation.

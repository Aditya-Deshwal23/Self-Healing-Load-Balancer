# Presentation Script

## Slide 1 — Title

Good morning. Our project is called **Self-Healing Load Balancer**. This is a Phase 1 local prototype with an advisory HYBRID_SHADOW signal. We will show the part that currently works: detecting a supported backend failure, changing the affected HAProxy route membership, verifying the result, and restoring traffic after the failure is cleared.

## Slide 2 — Problem Statement

In a load-balanced application, a backend does not always fail completely. A service can still answer a health endpoint and serve some routes, while one important route is failing. In our example, backend B can fail only for checkout. If we continue sending checkout traffic to B, users see errors. If we remove B from every route, we also remove capacity that is still healthy.

The goal is to respond to the actual scope of the problem. We want the system to detect the difference between a route-level fault and a full backend outage, and then make a limited change that we can check afterward.

## Slide 3 — Existing Problems

Basic health checks are useful, but they are not enough for every application failure. A container can be running and its `/healthz` endpoint can be available while one route returns errors. In that case, a simple up-or-down status does not explain what users are experiencing.

Manual routing changes also take time, especially when someone first has to identify whether the problem is isolated. Restarting the backend is another common response, but it may not fix a route-specific issue and it can interrupt healthy requests. We therefore need evidence before changing traffic.

## Slide 4 — Proposed Solution

Our solution is a local Docker Compose lab with an independent request path and control path. The request path uses NGINX and HAProxy. The control path gathers metrics, direct probes, and HAProxy Runtime state.

The decision logic uses deterministic rules. It does not use machine learning or prediction. When the evidence matches a supported route-instance failure, the control worker drains only that membership from HAProxy. The worker then verifies that requests are healthy on the remaining backends and that unrelated route memberships stayed unchanged.

## Slide 5 — Architecture

Starting at the client, requests first reach NGINX over HTTPS. NGINX is our reverse proxy and only published edge service. It serves the web console, forwards API calls to the control API, and sends application routes to HAProxy.

HAProxy contains four backend pools: public, auth, catalog, and checkout. Each pool has the same three physical demo instances: A, B, and C. HAProxy balances requests in each pool using round robin and checks backend health.

Separately, Prometheus collects metrics from HAProxy and the three backends. The control worker reads those metrics, performs private direct probes, and reads HAProxy Runtime state. PostgreSQL stores the records. Redis supports coordination and event delivery. The web console receives the stored state through the API.

## Slide 6 — Working Flow

The lab includes a small traffic generator. It continuously sends bounded requests through HAProxy to all four application routes. This gives the controller actual request outcomes rather than synthetic status alone.

Prometheus scrapes HAProxy and backend metrics every two seconds. The worker combines those values with direct probes to each backend route and a readback of HAProxy's current configuration state. It creates an observation window and passes it to the rule engine.

If the evidence is incomplete or conflicting, the worker does not perform a destructive routing action. If it sees a supported and sufficiently evidenced condition, it records the incident and prepares the appropriate action.

This separation is useful during review. The request path can keep serving users while the worker observes the system. The worker does not sit in the normal request path, so it is not choosing a server for every client request. HAProxy continues to do that. The worker only changes the eligibility of a predeclared HAProxy member when the policy allows it.

## Slide 7 — Technologies Used

Docker Compose runs the local services with private networks, health checks, secrets, and resource limits. NGINX is the TLS edge reverse proxy. HAProxy is the load balancer and exposes its private Runtime socket to the control worker only.

The control API and worker are written in Python using FastAPI and SQLAlchemy. PostgreSQL is the durable record of incidents and actions. Redis is used for worker coordination and event infrastructure. Prometheus stores a bounded local metrics history. The operator console is built with Next.js and React.

For logging, services write to standard output and Docker stores JSON logs with rotation limits. The current prototype does not contain Elasticsearch, Logstash, Kibana, or an ELK dashboard.

## Slide 8 — Self-Healing Mechanism

Let us look at the main recovery case. We inject a fault where checkout fails on backend B. The worker first checks that checkout on B is failing in real traffic and direct probes. It also checks that checkout on A and C is healthy, and that public, auth, and catalog on B are still healthy.

When those checks pass, the rule engine classifies the condition as a route-instance failure. The worker stores the evidence and an action plan before it changes anything. It sends an absolute HAProxy Runtime command that drains `be_checkout/srv_inst_b` and sets its weight to zero.

Then the worker reads HAProxy back. It checks that the checkout membership for B changed as requested and that the preserved memberships did not change. It also verifies real checkout traffic and peer queues. Only after those checks does it treat the action as committed.

The action is stored before it is sent. The stored record includes the old desired and observed states, the requested state, the expected effect, the memberships that must be preserved, verification requirements, a rollback plan, and an expiry. If the worker restarts during an unfinished action, it reconciles from HAProxy readback instead of blindly sending the command again. This makes the control flow easier to inspect and safer to test.

After the fault is cleared, B is not returned to full checkout traffic immediately. The worker reintegrates it at 5, 20, 50, and 100 percent. Every stage needs probes, real samples, and runtime readback before the next stage can start.

One clarification is important. The controller does not restart backend containers. Its implemented healing action is route quarantine and staged routing recovery. Docker Compose has a restart policy for unexpected container exits, but that is separate from the worker.

## Slide 9 — Live Demo Flow

For the demonstration, we run `./local-up`. This creates local secrets and a development certificate, starts the Compose stack, waits for health, and prints an HTTPS address. We sign in to the console using the generated local password. The measured live proof also covers `AUTH_INST_A_FAILURE` and the advisory `GRAY_FAILURE_INST_A` path.

The first screen shows a normal route-by-instance matrix. Next, in the Lab screen, we select **Checkout fails on Backend B**. After the evidence window, an incident appears with its classification and decision trace.

In the Actions and matrix views, we can see the checkout membership for B drain while checkout traffic continues through A and C. B stays available for the other three routes. When we clear the fault, the Recovery screen shows the controlled return of B to checkout traffic.

If time is limited, the script `./local-smoke` runs the same primary journey without using the UI. The repository also includes deterministic safety tests for cases where the worker must not take a destructive action.

## Slide 10 — Current Achievements

The current implementation completes a focused vertical slice. It has a real request path, generated traffic, metrics collection, private probes, rule-based classification, HAProxy Runtime actuation, readback, verification, durable records, a live console, and staged recovery.

It supports defined states including healthy, instance down, route-instance failure, shared-route failure, and unknown. The supported automatic actions are deliberately limited. That limitation is useful because it keeps the behavior testable and the effect of an action clear.

There are also practical boundaries in the lab. Prometheus retention is limited, container logs are rotated, and traffic generation is capped. The application services, HAProxy Runtime socket, Prometheus, PostgreSQL, and Redis are not published directly to the host. These choices are meant to keep the demonstration contained and to separate the public edge from the controller's private capabilities.

## Slide 11 — Future Scope

The next items are future work, not claims about the current project. We may explore machine learning prediction, predictive scaling, Kubernetes, cloud deployment, multi-node clusters, advanced monitoring, horizontal autoscaling, and a distributed rule engine.

These would require separate design and validation. For example, prediction needs historical data and evaluation; autoscaling needs a controlled capacity mechanism; and multi-node operation needs stronger coordination and failure handling than the current sole-writer lab design.

## Slide 12 — Conclusion

To conclude, this project shows a practical local example of scoped recovery. Instead of treating every backend issue as a full outage, it gathers evidence, changes only the affected HAProxy membership, and verifies the effect using real traffic and runtime state.

The main contribution of the prototype is not a broad claim of autonomous operations. It is a complete, inspectable path for one defined failure class. Thank you. We are ready for questions.

# Speaker Notes

## Slide 1 — Title

Introduce the project as a Phase 1 local prototype with an advisory HYBRID_SHADOW signal. Say that the presentation focuses on one working recovery path rather than claiming a complete production platform.

## Slide 2 — Problem Statement

Explain that backend problems are not always complete outages. In this lab, checkout can fail on one backend while that same backend still serves other routes correctly. That makes a broad response wasteful.

## Slide 3 — Existing Problems

Point out that a basic health check can say a container is running without proving that every application route works. Manual changes are slow during an incident, and a restart is not automatically the right action.

## Slide 4 — Proposed Solution

Describe the project as a local system that collects evidence first, then applies the smallest routing change it supports. Emphasize that the rules are deterministic and that an action is verified afterward.

## Slide 5 — Architecture

Walk left to right through the request path: NGINX, HAProxy, then three backend instances. Then explain the separate control path: Prometheus, probes, the control worker, storage, API, and the console. Only the worker can use the HAProxy Runtime socket.

## Slide 6 — Working Flow

Explain that normal traffic is generated continuously so the project has real request evidence. The worker reads metrics, probes each backend route privately, and checks HAProxy's actual runtime state before it decides what to do.

## Slide 7 — Technologies Used

Keep this slide factual. Docker Compose supplies the local environment, NGINX and HAProxy handle the edge and load balancing, Python/FastAPI implement the control plane, and Prometheus, PostgreSQL, Redis, Next.js, and React support monitoring, records, events, and the user interface.

## Slide 8 — Self-Healing Mechanism

This is the key slide. For the main scenario, checkout on B fails but other routes on B do not. The worker drains only the checkout membership for B. It does not restart B and does not remove B from unrelated routes. The action is accepted only after readback and traffic verification.

## Slide 9 — Live Demo Flow

Tell the audience what they will see before starting: a normal matrix, a fault injection, an incident and action, traffic continuing through healthy checkout backends, and a gradual recovery after the fault is cleared. The measured proof set also includes auth/inst-a isolation and a gray-failure shadow signal without destructive action. Pause briefly at each UI state.

## Slide 10 — Current Achievements

Describe the complete vertical slice: traffic, evidence, decision, route change, verification, storage, event update, and recovery. Avoid saying that it can solve every backend problem; it supports defined classifications in a local lab.

## Slide 11 — Future Scope

State clearly that this slide is not implemented work. The present controller does not use machine learning, Kubernetes, cloud services, horizontal autoscaling, multi-node coordination, or a distributed rule engine.

## Slide 12 — Conclusion

Close with the engineering point: the project makes a narrow, observable, and verified routing adjustment. It shows why scoped recovery can be safer than treating every partial failure as a full service outage.

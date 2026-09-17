# Slide Content

## 1. Title

- Self-Healing Load Balancer
- Phase 2 local prototype
- University software engineering review
- Team presentation

## 2. Problem Statement

- A backend can fail for only one route
- Overall service health can hide that failure
- Sending traffic to it causes user-facing errors
- Broad recovery can remove healthy capacity

## 3. Existing Problems

- Container health alone misses route-level faults
- Manual routing changes take time
- Restarting a service can be unnecessary
- Recovery needs proof that other routes stay healthy
- Operators need a trace of what changed

## 4. Proposed Solution

- Local Compose-based load-balancing lab
- HAProxy balances four application routes
- Metrics, probes, and runtime readback form evidence
- Deterministic rules classify supported cases
- Controller changes only the affected route membership
- Verification and staged restoration follow

## 5. Architecture

- NGINX is the HTTPS reverse proxy
- HAProxy is the application load balancer
- Three predeclared demo backend instances
- Prometheus collects HAProxy and backend metrics
- Control worker uses private runtime access
- PostgreSQL, Redis, API, and web console support control flow

## 6. Working Flow

- Requests enter through NGINX
- HAProxy selects a backend for the route
- Traffic generator creates real test traffic
- Prometheus and direct probes provide observations
- Rule engine classifies the observed condition
- Worker verifies every routing action

## 7. Technologies Used

- Docker Compose
- NGINX
- HAProxy
- Python and FastAPI
- PostgreSQL and Redis
- Prometheus
- Next.js and React

## 8. Self-Healing Mechanism

- Detect checkout failure on backend B
- Confirm other checkout backends are healthy
- Confirm public, auth, and catalog on B are healthy
- Drain only `be_checkout/srv_inst_b`
- Read HAProxy Runtime state after the change
- Restore checkout traffic in guarded stages

## 9. Live Demo Flow

- Start the lab with `./local-up`
- Open the HTTPS console and sign in
- Inject Checkout fails on Backend B
- Observe incident and route isolation
- Clear the fault
- Watch staged reintegration to healthy state

## 10. Current Achievements

- Complete local request and control paths
- Route-specific and instance-down classifications
- Evidence records and action audit trail
- HAProxy Runtime readback and verification
- Live REST and server-sent event dashboard updates
- Deterministic safety tests included

## 11. Future Scope

- Machine Learning prediction
- Predictive scaling and horizontal autoscaling
- Kubernetes and cloud deployment
- Multi-node clusters
- Advanced monitoring
- Distributed rule engine

## 12. Conclusion

- Demonstrates a focused self-healing vertical slice
- Uses real local traffic and runtime state
- Makes the smallest supported routing change
- Verifies service recovery before reintegration
- Clearly separates implemented work from future work

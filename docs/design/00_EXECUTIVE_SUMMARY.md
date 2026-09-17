# Self Healing Load Balancer — Executive Summary

Status: **architecture frozen for review; implementation not started**  
Design date: 2026-07-18  
Audience: engineering team, faculty reviewers, research supervisors, and college IP cell  
Patent status: **preliminary exploration only; no patentability or freedom-to-operate conclusion**

## Repository audit

The workspace was empty at the start of this task. It was not a Git repository and contained no source files, manifests, environment examples, architecture documents, proxy configuration, Compose files, database schema, telemetry configuration, experiments, or tests. Consequently:

- there is no implemented or partially implemented behavior to preserve;
- there are no hidden repository constraints beyond the technology and scope fixed in the project brief;
- every architecture decision in this dossier is a first-principles design decision;
- these Markdown files are the first repository artifacts, and no application logic has been created or modified.

## Frozen product decision

**Self Healing Load Balancer** is an out-of-request-path controller that uses route-, instance-, and version-resolved evidence to choose the least disruptive safe HAProxy routing change, verifies the effect, and either commits, rolls back, or gradually reintegrates capacity.

The product remains a load balancer and traffic-reliability system. It does not restart containers, repair application code, replace an orchestrator, autoscale infrastructure, perform deployment rollback, act as a WAF, or let an LLM control traffic.

The request path is fixed:

```text
Client -> NGINX -> HAProxy -> route-specific logical pool
       -> physical backend instance -> application dependency -> response
```

The control plane is never in that path. If the controller, database, ML model, frontend, Elasticsearch, or Ollama fails, HAProxy continues using its last-known-good routing state.

## Critical novelty correction

The original signature, route × instance selective quarantine, is useful but cannot responsibly be presented as novel. Microsoft patent publication [US20110238733A1 / US9058252B2](https://patents.google.com/patent/US20110238733A1) expressly describes a load balancer maintaining server health for different request types or URL namespaces and discontinuing only those request types for an unhealthy server. F5 also documents pool-specific monitors where the same physical resource can be evaluated differently in different pools, and AWS permits a target to belong to multiple target groups.

The selected patent-exploration nucleus is therefore narrower:

> **Evidence-Bounded Minimum-Scope Healing (EBMSH):** build a cross-control failure-support matrix over route × instance × version; admit a routing unit only when an evidence certificate supports that scope and a capacity/retry safety envelope permits it; select the admissible unit with the lowest blast-radius cost; apply a bounded, single-writer, generation-checked reversible routing change; and commit only when verification shows both the predicted symptom change and preservation of unaffected-route capacity.

This is a **patent-exploration candidate**, subject to formal patent searching and professional legal review. The combined mechanism may still be considered obvious in light of request-based health modeling, confidence-based remediation, canary analysis, and automated routing prior art. Its research value is stronger than its presently demonstrated patent strength.

## Supporting mechanisms

Only three mechanisms support the nucleus:

1. A privacy-minimized multidimensional failure fingerprint with peer and cross-route controls, version cohorts, provenance, and data-completeness scoring.
2. A deterministic action safety envelope covering remaining capacity, route criticality, retry safety, conflicts, cooldown, rollback availability, and operator overrides.
3. Sequential effect verification and evidence-gated reintegration; missing evidence pauses recovery rather than being interpreted as success.

ML is an aid to scope classification, not the invention. HAProxy weights, health checks, logical pools, retries, circuit breaking, canary stages, dashboards, and LLM summaries are standard supporting features and are not claimed as novel.

## Final failure classes and actions

The classifier exposes exactly eight mutually exclusive top-level classes:

`HEALTHY`, `INSTANCE_DOWN`, `INSTANCE_DEGRADED`, `ROUTE_INSTANCE_FAILURE`, `SHARED_ROUTE_FAILURE`, `TRAFFIC_OVERLOAD`, `VERSION_SPECIFIC_FAILURE`, and `UNKNOWN`.

The action vocabulary is deliberately smaller than the observation vocabulary:

- no change / alert / require review;
- reduce a route-membership or instance weight;
- drain one route × instance membership;
- drain all memberships of one physical instance;
- suppress the preconfigured cross-instance retry policy for a route;
- activate preconfigured route rate or concurrency protection;
- activate a preconfigured fail-fast response for a shared failing route;
- drain memberships belonging to a faulty version, subject to stable-version capacity;
- pause, advance, or roll back staged reintegration.

No action is permitted merely because an ML probability is high. Hard safety rules can downgrade or block every recommendation.

## Data-plane strategy

Each route group has its own HAProxy backend. The same physical endpoint is represented as a separate logical server membership in `/public`, `/auth`, `/catalog`, and `/checkout` pools. Those memberships share an `instance_id` in PostgreSQL but have independent HAProxy state and weight.

- Fast, reversible state and weight changes use the HAProxy Runtime API over a Unix socket.
- Structural changes—new route groups, ACLs, or memberships—use a versioned HAProxy Data Plane API transaction, validation, and reload.
- Runtime changes are treated as volatile. PostgreSQL desired state is authoritative; observed state is read back and reconciled after restart.
- A controller transaction is a durable saga, not a false claim of multi-command atomicity inside HAProxy.
- MVP has exactly one socket-mounted control worker. Multi-writer control is out of scope because the Runtime API cannot enforce an external fencing token.

## Intelligence strategy

Rules are the production baseline. Logistic Regression is the interpretable ML baseline. A calibrated Random Forest is the preferred candidate only if held-out experiment runs show better macro-F1, per-class recall, calibration, and false-action rate. Low confidence, incomplete data, conflicting evidence, out-of-distribution input, inference failure, or schema mismatch yields `UNKNOWN` or rules-only operation.

A defensible “90%” result means a preregistered held-out-run macro-F1 target, not raw accuracy. The dossier sets additional per-class recall, calibration-error, and false-action requirements and requires confidence intervals.

## Primary research question

Does EBMSH preserve more ground-truth healthy route capacity during localized failures than round robin, standard HAProxy health checks, and static threshold healing, while meeting successful-request and false-action guardrails?

The primary metric is **ground-truth healthy route-capacity preserved**, evaluated only with the separately reported successful-request guardrail so a do-nothing policy cannot be declared superior. Thirty matched independent trials per baseline × fault scenario are recommended for the primary load level. The preregistered comparison uses a Friedman test followed by Holm-corrected paired Wilcoxon tests and effect sizes.

## Feasibility and zero-cost verdict

The core is feasible for four undergraduate students in 22 weeks if the team builds in this order: static data plane, telemetry, rules-only fingerprinting, safety, durable actions, reconciliation, verification, and fault tests. ML, the LLM, ELK, and the polished frontend must not be on the critical path.

- Low-resource local profile: 4 CPU cores, 8 GB RAM, 20 GB free disk; ELK and Ollama disabled.
- Public self-hosted demo: 4–8 cores, 12–16 GB RAM, 40–60 GB disk; ELK normally disabled.
- Full lab: 8 cores, 24–32 GB RAM, 100–150 GB disk; ELK, fault tooling, experiment runner, and Q4 local model enabled.
- A 16 GB laptop can run the full workflow sequentially, but should not run Elasticsearch and the 8B model concurrently.

There is no mandatory paid API, SaaS, cloud service, database, authentication provider, or LLM endpoint. “Zero mandatory recurring cost” is achievable on user-owned hardware; permanent public availability, a domain name, electricity, hardware, and Internet connectivity are not free guarantees.

## Review gates before implementation

Implementation should begin only after reviewers approve all of the following:

1. The narrow EBMSH definition and the explicit prior-art caveat.
2. Single-writer controller as an MVP production boundary.
3. Route grouping, criticality, capacity, and retry-policy inputs as customer responsibilities.
4. Rules-only behavior as the mandatory operational baseline.
5. The exact fault matrix and experiment protocol.
6. The resource-aware deployment profiles.

## Dossier map

| Document | Purpose |
|---|---|
| `01_CRITICAL_IDEA_REVIEW.md` | strict assessment of the original concept and product comparisons |
| `02_FINAL_PRODUCT_SPECIFICATION.md` | frozen scope, classes, actions, integration contract, and non-goals |
| `03_RESEARCH_GAP_AND_PRIOR_ART.md` | authoritative product, paper, and patent evidence plus search plan |
| `04_PATENT_EXPLORATION_CANDIDATES.md` | four candidates, scoring, and selection |
| `05_SELECTED_INVENTION_DISCLOSURE.md` | non-legal engineering disclosure for IP review |
| `06_SYSTEM_ARCHITECTURE.md` | planes, components, protocols, failures, resources, and core diagrams |
| `07_DATA_PLANE_AND_HAPROXY_DESIGN.md` | exact NGINX/HAProxy ownership and actuation semantics |
| `08_CONTROL_PLANE_AND_RECONCILIATION.md` | modular monolith, desired/observed state, controller safety |
| `09_FAILURE_FINGERPRINT_AND_CLASSIFICATION.md` | fingerprint schema, algorithms, rules, ML, and evaluation |
| `10_SAFETY_RETRY_AND_ACTION_TRANSACTIONS.md` | safety mapping, retry semantics, durable healing saga |
| `11_VERIFICATION_AND_REINTEGRATION.md` | effect tests, recovery stages, hysteresis, and low-traffic behavior |
| `12_DATA_MODEL_AND_API_CONTRACTS.md` | relational model, Redis keys, REST, SSE, retention, and consistency |
| `13_OBSERVABILITY_AND_INCIDENTS.md` | metrics, logs, alerts, correlation, and incident semantics |
| `14_SECURITY_AND_THREAT_MODEL.md` | threats, trust boundaries, authorization, and failure fallbacks |
| `15_FRONTEND_UX_SPECIFICATION.md` | visual system, 22 screens, Decision Trace, and matrix UX |
| `16_ZERO_COST_DEPLOYMENT_PLAN.md` | Compose profiles, resources, networks, backups, and public demo |
| `17_RESEARCH_AND_EVALUATION_PLAN.md` | questions, hypotheses, baselines, trials, statistics, validity |
| `18_TESTING_AND_ACCEPTANCE_CRITERIA.md` | test pyramid and class/action acceptance matrix |
| `19_IMPLEMENTATION_ROADMAP.md` | 22-week plan, ownership, dependencies, and exit gates |
| `20_RISK_REGISTER_AND_DECISION_LOG.md` | principal risks and frozen architecture decisions |
| `21_FINAL_FROZEN_SPECIFICATION.md` | self-contained decisive handoff specification |

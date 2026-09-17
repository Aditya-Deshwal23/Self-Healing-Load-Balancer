# Patent-Exploration Candidates

## Evaluation method

Scores are engineering judgments from 1 (weak) to 5 (strong), not legal opinions. “Prior-art headroom” scores higher when less close art was found. Weighted total is `sum(score × weight) / 5`, yielding 0–100.

| Criterion | Weight | Meaning |
|---|---:|---|
| Technical differentiation | 25 | specificity beyond a routine aggregation |
| Prior-art headroom | 20 | distance from confirmed close art |
| Experimental measurability | 15 | ability to demonstrate a causal technical effect |
| Four-student feasibility | 15 | fit within 22 weeks and fixed stack |
| Operational safety | 10 | ability to bound harm and reverse actions |
| Load-balancer centrality | 10 | remains directly about traffic routing |
| Explainability | 5 | comprehensible to operators, reviewers, and IP professionals |

## Candidate A — Route-Instance Failure Fingerprint and Selective Quarantine

1. **Technical problem:** a backend can fail for one URL group while serving others correctly; instance health checks cause excessive whole-host removal.
2. **Mechanism:** aggregate requests by route × instance, derive an error/latency fingerprint, classify a localized fault, and set only that HAProxy logical membership to drain.
3. **Existing approaches:** per-URL health tests, request-based server health, per-pool member monitors, L7 routing, logical target groups, and route-specific circuit breakers.
4. **Potential differentiator:** a standardized fingerprint combining passive requests, probes, and peer deviations; this is narrower than quarantine itself.
5. **Expected technical effect:** fewer healthy routes removed and more useful capacity during a localized route fault.
6. **Required telemetry:** route ID, instance ID, response/timing/termination, direct probe result, peer observations.
7. **Implementation complexity:** low-medium; logical pools and Runtime API are direct.
8. **Experimental measurability:** high; inject `/checkout` failure only on instance B and measure unaffected traffic.
9. **Feasibility for four students:** high.
10. **Prior-art risk:** **very high**; US20110238733A1/US9058252B2 closely discloses request-type health and selective suppression.
11. **Patent-exploration strength:** weak.
12. **Research-publication strength:** medium as an open reproducible implementation/baseline.
13. **Failure modes:** low-volume false localization, dynamic path cardinality, shared dependency mistaken for member-local, stale membership identity, sticky-session leakage.
14. **Fundamentally a load-balancer invention:** yes.

Decision: retain as an essential product capability, explicitly disclaim as the invention nucleus.

## Candidate B — Evidence-Bounded Minimum-Scope Healing Transaction

1. **Technical problem:** several routing scopes can explain the same symptoms. A controller may apply a needlessly broad action or a narrow action that shifts failure/retry load elsewhere.
2. **Mechanism:** construct a route × instance × version support matrix; create an evidence certificate using same-route peers, same-instance other routes, and version controls; enumerate expressible routing-unit target sets; reject scopes without evidence or capacity/retry safety; select minimum blast-radius cost; snapshot state; apply a bounded idempotent change; verify affected improvement plus unaffected preservation; commit or restore.
3. **Existing approaches:** request-type health models, host outlier detection, ejection caps, policy engines, canary analysis, confidence-gated remediation, desired-state controllers, and rollback.
4. **Potential differentiator:** coupling two-sided cross-control evidence to *admissibility of routing scopes* and to a dual verification invariant before scope commit, rather than mapping one detector directly to one action.
5. **Expected technical effect:** lower unnecessary healthy-capacity removal at a bounded false-action rate, with recoverable partial actuation.
6. **Required telemetry:** all Candidate A signals plus version cohort, capacity/headroom, retry state, criticality, action history, completeness/conflict provenance, and observed HAProxy state.
7. **Implementation complexity:** medium-high; requires careful data model, lattice/cost selection, durable state machine, and reconciliation.
8. **Experimental measurability:** high across localized, shared, version, overload, and mixed faults.
9. **Feasibility for four students:** medium-high if rules-only and single-writer are completed before ML/UI.
10. **Prior-art risk:** medium-high; individual elements are known, and the combination may be obvious. No exact match was confirmed in the limited search.
11. **Patent-exploration strength:** strongest of the candidates but preliminary.
12. **Research-publication strength:** high; scope error, capacity preservation, false action, and rollback are directly measurable.
13. **Failure modes:** correlated faults violate peer assumptions; wrong capacity metadata; action effect confounded by changing load; non-atomic multi-membership apply; insufficient control traffic; selection cost poorly calibrated.
14. **Fundamentally a load-balancer invention:** yes; its output is a routing-unit transaction.

Decision: **selected primary nucleus**.

## Candidate C — Information-Gain Route Diagnostic Probing

1. **Technical problem:** passive traffic may not distinguish route-instance, shared-route, and dependency faults quickly, especially at low volume.
2. **Mechanism:** maintain candidate scope probabilities, score allowable direct route × instance probes by expected entropy reduction divided by probe cost/risk, execute the best probe, update beliefs, and stop when a scope threshold or probe budget is reached.
3. **Existing approaches:** active fault localization, Bayesian diagnosis, test-cover selection, maximum information-gain probes, synthetic monitoring, and network tomography.
4. **Potential differentiator:** route-aware application probes whose value is measured by which HAProxy routing units they can disambiguate under a traffic safety budget.
5. **Expected technical effect:** fewer probes and faster abstention/localization at low traffic.
6. **Required telemetry:** candidate scopes, probe-to-route/instance coverage map, result likelihoods, probe cost, route side-effect classification.
7. **Implementation complexity:** high; likelihood modeling and safe non-mutating probes are application-specific.
8. **Experimental measurability:** medium-high; probe count, time to scope, and misclassification can be measured.
9. **Feasibility for four students:** medium-low within the core schedule.
10. **Prior-art risk:** **very high**; US8171130B2 and cited earlier work expressly use information-gain active probing.
11. **Patent-exploration strength:** weak unless a genuinely narrow routing-unit formulation survives formal search.
12. **Research-publication strength:** medium, but would distract from the primary traffic-action study.
13. **Failure modes:** probes mutate state, authenticated routes cannot be tested, synthetic/real mismatch, inaccurate likelihoods, added load during overload, probe endpoints leak.
14. **Fundamentally a load-balancer invention:** only if tightly constrained; otherwise generic diagnosis.

Decision: future research, not an MVP support mechanism.

## Candidate D — Outcome-Calibrated Reintegration and Intervention Memory

1. **Technical problem:** fixed cooldowns and fixed 5/20/50/100 stages either restore too slowly or cause flapping, while the same action can behave differently by route/load/version.
2. **Mechanism:** store action-context/outcome records, estimate context-specific success likelihood, adapt verification duration and next-stage size within hard bounds, and increase cooldown after recurrent rollback.
3. **Existing approaches:** slow start, adaptive hysteresis, canary analysis, multi-armed/online mitigation, historical remediation confidence, and reinforcement learning.
4. **Potential differentiator:** context key includes route-scope evidence and unaffected-capacity preservation, with no online policy learning outside fixed safety bounds.
5. **Expected technical effect:** lower recovery time at the same reintegration-failure rate.
6. **Required telemetry:** action context, stage exposure, verification outcomes, recurrence interval, route load and criticality.
7. **Implementation complexity:** medium-high; sparse contexts make estimates unstable.
8. **Experimental measurability:** high for repeated flapping and recovery faults.
9. **Feasibility for four students:** medium as a stretch goal.
10. **Prior-art risk:** high; US11943131B1, Narya, canary systems, and standard backoff are close.
11. **Patent-exploration strength:** weak-medium only as a dependent supporting embodiment.
12. **Research-publication strength:** medium-high as a follow-on experiment.
13. **Failure modes:** feedback loops, context overfitting, exploration harms production, old outcomes bias changed systems, sparse-sample confidence error.
14. **Fundamentally a load-balancer invention:** yes when restricted to routing reintegration.

Decision: fixed evidence-gated stages are MVP; learned intervention memory is future work and not a selected support mechanism.

## Weighted decision matrix

| Candidate | Differentiation 25 | Prior-art headroom 20 | Measurability 15 | Feasibility 15 | Safety 10 | LB centrality 10 | Explainability 5 | Weighted total /100 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A. Route-instance fingerprint/quarantine | 1 | 1 | 5 | 5 | 4 | 5 | 5 | **62** |
| B. Evidence-bounded minimum-scope transaction | 4 | 3 | 5 | 4 | 5 | 5 | 4 | **83** |
| C. Information-gain probing | 2 | 1 | 4 | 3 | 4 | 4 | 4 | **55** |
| D. Outcome-calibrated reintegration memory | 2 | 1 | 4 | 4 | 4 | 3 | 4 | **56** |

Scores do not imply legal novelty. Candidate B wins because it is the best balance of specificity, measurable traffic effect, safety, feasibility, and load-balancer centrality—not because prior art is absent.

## Selected configuration

### Primary patent-exploration nucleus

**Evidence-Bounded Minimum-Scope Healing (EBMSH)**, including its durable bounded-apply/dual-verification transaction. The transaction is part of the nucleus because without it the evidence certificate is only a recommendation, and without the certificate the transaction is ordinary canary control.

### Supporting mechanisms—maximum three

1. Multidimensional privacy-minimized failure fingerprint.
2. Deterministic capacity/retry/action safety envelope.
3. Evidence-gated verification and staged reintegration.

### Explicit exclusions from the nucleus

- route × instance logical pools or quarantine alone;
- rule/ML ensemble alone;
- Random Forest;
- HAProxy Runtime/Data Plane APIs;
- retry suppression/rate limiting/circuit breaking;
- canary percentages or slow start;
- dashboards, topology, Decision Trace;
- LLM reports;
- action history that merely updates a confidence score.

## Why the transaction is more than renamed canary behavior

It would be only renamed canary behavior if it simply changed 5% of traffic, watched error rate, and promoted/rolled back. EBMSH adds genuine engineering specificity through:

- a pre-action evidence certificate that determines which routing target sets are admissible;
- an exact desired/observed snapshot and controller-generation fence;
- action magnitude derived from action risk and failure evidence (hard-down may drain immediately; ambiguous degradation begins with a bounded reduction);
- state readback after each idempotent HAProxy set operation;
- two verification obligations: predicted improvement for the affected cohort and non-regression/preserved capacity for disjoint unaffected route cells;
- action-specific rollback logic—never blindly re-enable a confirmed-down member;
- recovery stages controlled by evidence sufficiency, not elapsed time alone.

Canary and declarative-control prior art still creates substantial obviousness risk. These differences make the design precise and researchable, not guaranteed patentable.

## Go/no-go conclusion

- **Engineering:** go.
- **Research paper:** go, with EBMSH and healthy-capacity preservation as the center.
- **College IP disclosure:** go, clearly marked preliminary and confidential until reviewed.
- **Patent filing claim:** no-go until a professional search and claim chart finds defensible headroom.
- **Public novelty statement:** no-go; use “patent-exploration candidate” and “potentially differentiated mechanism.”


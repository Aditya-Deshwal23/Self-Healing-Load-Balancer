# Research Gap and Prior Art

## 1. Scope and disclaimer

This is an engineering prior-art exploration performed on 2026-07-18, not a patentability opinion, legal-status opinion, claim construction, or freedom-to-operate search. Web-accessible official documentation, primary research pages/papers, and patent publications were reviewed. Keyword searching is inherently incomplete; patent families, translations, continuations, non-patent literature, unpublished applications, and commercial implementations may contain closer art.

Confirmed prior art below means that a cited source expressly discloses the stated feature. “Engineering inference” is labeled where the source does not disclose the complete proposed combination.

## 2. Decisive finding

The initial route × instance selective-quarantine concept has close, explicit patent prior art:

- [US20110238733A1, Request-based server health modeling](https://patents.google.com/patent/US20110238733A1) (grant family member US9058252B2; priority 2010-03-24) maintains a server health model for different request types, including URL namespaces, and states that routing may be modified to discontinue sending a server the request types for which it is unhealthy.

That disclosure maps closely to: “backend B remains eligible for `/public`, `/auth`, and `/catalog` while being excluded for `/checkout`.” The implementation technology (HAProxy logical pools) does not create novelty over that functional teaching.

## 3. Official product documentation review

| System | Confirmed capability relevant to this project | Design consequence |
|---|---|---|
| HAProxy Runtime API | Runtime state/weight changes are in memory and do not persist across restart; server state can be `ready`, `drain`, or `maint`; weight is dynamically changeable. [Runtime API overview](https://www.haproxy.com/documentation/haproxy-runtime-api/), [set server](https://www.haproxy.com/documentation/haproxy-runtime-api/reference/set-server/), [set weight](https://www.haproxy.com/documentation/haproxy-runtime-api/reference/set-weight/) | Desired state and restart reconciliation are mandatory. State/weight primitives are not novel. |
| HAProxy Data Plane API | Structural configuration uses a version parameter and optimistic concurrency; transactions, validation, backups, and reload integration are supported. [Manage backends](https://www.haproxy.com/documentation/haproxy-data-plane-api/tutorials/backends/), [configuration reference](https://www.haproxy.com/documentation/haproxy-data-plane-api/reference/configuration-file/) | Use it for structure, not high-frequency healing. Its version is not the controller’s safety fence. |
| HAProxy state files | `show servers state` can preserve address, weight, drain, and maintenance state across reload. [Official reference](https://www.haproxy.com/documentation/haproxy-runtime-api/reference/show-servers-state/) | Useful second recovery source; PostgreSQL remains authoritative. |
| HAProxy retries | Retry, redispatch, response-code conditions, and dynamic retry count are supported. [Official retry tutorial](https://www.haproxy.com/documentation/haproxy-configuration-tutorials/reliability/retries/) | Retry behavior is standard and must be constrained by method semantics. |
| NGINX OSS | Passive upstream health and next-upstream behavior are built in; active application health and live group reconfiguration are commercial capabilities. [Load balancing](https://nginx.org/en/docs/http/load_balancing.html), [proxy module](https://nginx.org/en/docs/http/ngx_http_proxy_module.html) | NGINX should not duplicate HAProxy healing/retry behavior. |
| AWS ELB | Targets are monitored/ejected/reintroduced; a target can be in multiple target groups, each with health checks; draining, health thresholds, and fail-open behaviors exist. [ELB operation](https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/how-elastic-load-balancing-works.html), [ALB target groups](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-target-groups.html) | Multiple logical pools and capacity thresholds are prior art. |
| Google Cloud Load Balancing | Backend health, outlier detection, balancing policies, per-instance weights in some products, and auto-capacity draining/undraining are documented. [Backend services](https://docs.cloud.google.com/load-balancing/docs/backend-service), [advanced optimizations](https://docs.cloud.google.com/load-balancing/docs/service-lb-policy) | Capacity-aware drain and hysteresis alone are not differentiators. |
| Azure Application Gateway | Per-backend-pool probes remove unhealthy servers and restore them on recovery; custom probes are supported. [Probe overview](https://learn.microsoft.com/en-us/azure/application-gateway/application-gateway-probe-overview) | Route-specific probes and reinsertion are standard. |
| Kubernetes | Liveness can restart containers; readiness removes them from traffic; startup gates other probes. [Probe documentation](https://kubernetes.io/docs/concepts/workloads/pods/probes/) | The project must not claim probe-state separation or container healing. |
| Envoy | Per-host outlier detection, ejection caps, circuit breakers, concurrency limits, retry budgets, and retry-overflow metrics are available. [Transient failures](https://www.envoyproxy.io/docs/envoy/latest/faq/load_balancing/transient_failures.html), [circuit breaking](https://www.envoyproxy.io/docs/envoy/latest/configuration/upstream/cluster_manager/cluster_circuit_breakers.html) | Peer outlier detection plus capacity caps is close prior art. |
| Istio | Destination rules expose subsets, connection pools, retry budgets, outlier detection, ejection limits, locality failover, and warmup. [Destination Rule](https://istio.io/latest/docs/reference/config/networking/destination-rule/) | Version groups, policy subsets, and warmup are standard mesh capabilities. |
| F5 BIG-IP | Nodes/pools/pool members can have health and performance monitors; the same resource can be in multiple pools and use different pool monitors; dynamic ratio and priority groups exist. [Monitor concepts](https://techdocs.f5.com/en-us/bigip-16-0-0/big-ip-local-traffic-manager-monitors-reference/monitors-concepts.html), [Pools](https://techdocs.f5.com/kb/en-us/products/big-ip_ltm/manuals/product/ltm-concepts-11-5-1/6.html) | Per-pool member health is established commercial ADC practice. |

HAProxy 3.4 was the latest LTS at the review date, while 3.2 remains an LTS through 2030 according to the [HAProxy release table](https://www2.haproxy.org/). The initial design chooses HAProxy 3.2.x with Data Plane API 3.2.x to reduce compatibility risk; this is an implementation pin, not a feature claim.

## 4. Primary research prior art

| Work | Confirmed contribution | Relationship to this project |
|---|---|---|
| Huang et al., **Panorama**, OSDI 2018 | Requester-perspective observations reveal gray failures missed by local detectors. [USENIX paper page](https://www.usenix.org/conference/osdi18/presentation/huang) | Supports cross-observer evidence; prevents claiming differential observation as novel. |
| Tan et al., **NetBouncer**, NSDI 2019 | Active probing plus inference localizes device/link gray failures despite inconsistent data. [USENIX paper page](https://www.usenix.org/conference/nsdi19/presentation/tan) | Active diagnosis and inconsistent-evidence handling are established research. |
| Li and Huang, **Gray Failure**, SREcon 2024 | Emphasizes differential observability in cloud-scale failures. [USENIX page](https://www.usenix.org/conference/srecon24americas/presentation/li) | Motivates client-visible cross-controls; not a novelty basis. |
| Levy et al., **Narya**, OSDI 2020 | Predicts host failures, chooses mitigation through online experimentation/RL, and measures outcomes. [USENIX paper page](https://www.usenix.org/conference/osdi20/presentation/levy) | Adaptive mitigation and outcome learning are prior-art-heavy; RL is unnecessary here. |
| Li et al., **Gandalf**, NSDI 2020 | Correlates signals to rollouts and stops unsafe deployments using classifiers. [Microsoft Research](https://www.microsoft.com/en-us/research/publication/an-intelligent-end-to-end-analytics-service-for-safe-deployment-in-large-scale-cloud-infrastructure/) | Version-regression classification and automated stop decisions are established. |
| Google **Canary Analysis Service**, 2018 | Partially applies changes, evaluates metrics, and rolls forward/back or alerts. [Google Research](https://research.google/pubs/canary-analysis-service/) | Bounded apply/verify/rollback must not be claimed merely as canarying. |
| Google **Prodspec and Annealing** | Declarative select-update-validate loops, preconditions, and rollback are production control patterns. [USENIX article](https://www.usenix.org/publications/loginonline/prodspec-and-annealing-intent-based-actuation-google-production) | Desired-state reconciliation and staged validation are standard control engineering. |

The research literature validates the problem but narrows the gap. EBMSH’s publication contribution should be an empirical comparison of *scope-preserving routing decisions* on an open HAProxy stack, not a sweeping new failure-detection theory.

## 5. Patent records reviewed

| Publication / family | Express teaching relevant here | Risk to candidate |
|---|---|---|
| [US20110238733A1 / US9058252B2](https://patents.google.com/patent/US20110238733A1), Microsoft, priority 2010 | Server health differs by request type/URL namespace; routing can discontinue those request types to a server. | **Very high** for route × instance health/quarantine. |
| [US8949658B1](https://patents.google.com/patent/US8949658B1), Amazon, priority 2012 | Load balancer compares service response behavior, ejects anomalous hosts despite passing health checks, and limits how many hosts can be disabled. | High for peer anomaly + safety cap + ejection. |
| [US20220038347A1 / US11711271B2](https://patents.google.com/patent/US20220038347A1/en), Cisco, priority 2019 | ML predicts SD-WAN tunnel failure from telemetry, reroutes, receives outcome feedback, and retrains. | High for generic ML prediction + rerouting + feedback. |
| [US11943131B1](https://patents.google.com/patent/US11943131B1/en), Cisco, priority 2023 | Historical confidence scores gate automated remediation; service tests after action update confidence. | High for intervention memory/confidence reinforcement. |
| [US8171130B2](https://patents.google.com/patent/US8171130B2/en), IBM, older active-probing family | Selects active diagnostic probes using maximum expected information gain and probabilistic inference. | Very high for information-gain probing as a standalone invention. |
| [US20240045739A1](https://patents.google.com/patent/US20240045739A1/en) | API gateway changes traffic proportions using backend dependency health metrics. | High for dependency telemetry driving weighted routing. |
| [US20200382414A1](https://patents.google.com/patent/US20200382414A1/en) | Predictive routing validates/maintains backup path performance. | Medium for capacity-aware predictive failover. |
| [EP2706731B1](https://patents.google.com/patent/EP2706731B1/en) | Predictive routing combines normalized cost/delay measurements to select servers. | Medium for metric-combined routing decisions. |
| [US20260037963A1, Adaptive request handling using a dynamic server health score](https://patents.google.com/patent/US20260037963A1/en), priority 2024 | Computes weighted health scores from multiple server factors and selects the server with the highest score for a request. | Medium for multidimensional score-based selection claims. |

Legal status displayed by Google Patents is not relied on. Expired or abandoned documents remain relevant to novelty/obviousness as publications.

## 6. Claim-element pressure test

| Proposed EBMSH element | Known close art | Remaining possible distinction |
|---|---|---|
| request/route-specific server health | US20110238733A1 | none by itself |
| peer-relative anomalous host detection | US8949658B1; Envoy outliers | none by itself |
| version cohort anomaly | Gandalf; canary systems; mesh subsets | none by itself |
| confidence-gated actuation | US11943131B1 | none generically |
| capacity/ejection safety cap | Envoy, AWS, Google, US8949658B1 | none generically |
| bounded apply and rollback | CAS/Kayenta/rollout systems | none generically |
| post-action service test | US11943131B1, Narya | none generically |
| route × instance × version support matrix with *two-sided cross-controls* | combination of known concepts | Potentially narrower distinction; requires formal search. |
| enumerate routing units and reject units lacking a machine-checkable evidence certificate | no exact match confirmed in this limited search | Potentially differentiated formulation; obviousness risk remains. |
| verify predicted affected-cohort effect **and** unaffected-route preservation before scope commit | canary/control comparisons are close | Potentially narrow technical distinction when coupled to minimum-scope selection. |
| exact prior-state snapshot + single-writer, generation-checked idempotent HAProxy saga | declarative controllers and transactional remediation are established | Engineering depth, probably weak standalone patent weight. |

The possible distinction is the constrained combination, not any row in isolation.

## 7. Exact research gap after review

The credible gap is:

1. Existing load balancers commonly react at a preconfigured pool/member scope.
2. Request-based server-health prior art establishes fine-grained health, but does not by itself provide this dossier’s explicit route-peer, cross-route, and version-control evidence certificate.
3. Outlier systems constrain ejection percentage, but do not necessarily select among the project’s complete routing-unit lattice using a common evidence certificate.
4. Canary/remediation systems verify changes, but the proposed experiment couples verification to a prediction that unaffected route capacity will be preserved.
5. An open HAProxy implementation and reproducible dataset can quantify scope error, capacity loss, retry amplification, and false action across common failure classes.

This gap is sufficient for an applied research proposal. It is not yet sufficient to assert patent novelty.

## 8. Formal follow-on patent search plan

### Databases

Search at minimum:

- USPTO Patent Public Search and Patent Center;
- EPO Espacenet and EPO Register;
- WIPO PATENTSCOPE;
- Google Patents for family/citation navigation;
- Lens.org;
- Indian Patent Advanced Search System (InPASS);
- J-PlatPat and CNIPA for important non-English families;
- IEEE Xplore, ACM Digital Library, USENIX, arXiv, IETF, vendor manuals, theses, and technical disclosures.

### Starting CPC/IPC areas

These are search starting points and must be confirmed/refined by a patent search professional:

- `H04L41/06`, fault/event/alarm management;
- `H04L41/0654`, network fault recovery;
- `H04L41/0659` and `H04L41/0661`, isolation/reconfiguration of faulty entities;
- `H04L43/50` and `H04L43/55`, network/service-level testing;
- `G06F11/07`, responding to faults/fault tolerance;
- `G06F11/30` and `G06F11/34`, monitoring/statistical evaluation;
- `G06F9/50`, workload allocation/resource scheduling;
- `G06N20/00`, machine learning, only in combination with network classes.

### Exact query families

Run title/abstract/claims and full-text variants, with stemming and proximity operators:

```text
(load balanc* OR reverse prox* OR application delivery controller)
AND (route OR endpoint OR URL OR request type OR namespace)
AND (health OR anomal* OR degrad* OR failure)
AND (quarant* OR eject* OR drain* OR weight*)

(route instance version OR endpoint cohort)
AND (failure fingerprint OR health matrix OR failure scope)
AND (minimum scope OR minimum blast radius OR smallest routing unit)

(automated remediation OR traffic remediation)
AND (confidence OR completeness OR conflicting evidence)
AND (capacity constraint OR safety envelope OR retry budget)

(routing transaction OR traffic transaction)
AND (prepare commit abort rollback OR snapshot)
AND (load balanc* OR proxy)

(verification window OR sequential evidence OR canary)
AND (routing action OR backend ejection)
AND (unaffected route OR preserved capacity OR control cohort)

(information gain OR active probe selection)
AND (route OR server OR application endpoint)
AND (fault localization)
```

Also search synonyms: member/pool/target/upstream/origin, service path/API operation/handler/URL prefix, isolation/suppression/withdrawal, brownout/fail-slow/gray failure, rollout cohort/release/build, and service-level test.

### Search process

1. Build a claim chart for US9058252B2, US8949658B1, US11943131B1, US8171130B2, and the closest new references.
2. Traverse backward/forward citations and all INPADOC family members.
3. Search each independent EBMSH element separately, then combinations.
4. Record priority date, publication date, family, assignee, status source, relevant passages, and reviewer.
5. Have two team members independently screen titles/abstracts; adjudicate disagreements.
6. Ask the IP professional to search both novelty and inventive-step/obviousness combinations.
7. Perform a separate freedom-to-operate review only if commercialization is planned.

## 9. Publication search plan

Use a preregistered systematic query across IEEE/ACM/USENIX/Scopus or Web of Science if college access exists. Inclusion: 2010–2026 systems that infer failure scope and modify live L7 routing; earlier seminal fault localization and active probing. Exclusion: pure WAN path selection, pure autoscaling, WAF, source-code debugging, and papers without a traffic intervention. Extract topology, signal granularity, action unit, safety constraints, verification, dataset, and metrics.

## 10. Preliminary conclusion

- **Confirmed:** route-specific server health and selective request suppression are old prior art.
- **Confirmed:** anomaly-based ejection, ejection caps, ML routing, confidence-gated remediation, active information-gain probing, and canary verification are prior-art-heavy.
- **Inference:** the exact EBMSH combination may be narrower than the reviewed sources, but combining known components could be considered obvious.
- **Recommendation:** pursue EBMSH as the research nucleus and an engineering disclosure; do not publicize it as patentable. Complete a professional search before public paper/demo disclosure if filing is seriously contemplated.

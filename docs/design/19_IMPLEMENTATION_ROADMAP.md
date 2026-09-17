# Four-Student Implementation Roadmap

## 1. Planning assumptions

- Duration: **22 teaching weeks**, with approximately 10–12 focused hours per member per week and additional unattended experiment runtime.
- Team: four students with named primary ownership and mandatory cross-review; no component has an unreviewed sole maintainer.
- Architecture is frozen before Week 1. Scope change requires a decision-record update and removal or schedule impact, not quiet addition.
- The first usable product is rules-only and API-operable. ML, local LLM, ELK, and polished frontend do not sit on the critical path.
- Work proceeds as a modular monolith with two process roles (`control-api`, `control-worker`), not separate services for each conceptual module.
- All external-facing claims wait for repeated evidence and IP/public-disclosure review.

## 2. Balanced ownership

| Member | Primary technical ownership | Frontend feature ownership | Secondary reviewer |
|---|---|---|---|
| **M1 — Data Plane & Actuation** | NGINX, HAProxy config/runtime/DPA, logical pools, HAProxy adapter, desired/observed reconciliation, action application/compensation | Live Topology, Route × Instance Matrix, Healing Actions, Reintegration | M3 reviews safety/routing semantics; M2 reviews deployment |
| **M2 — Platform, Telemetry & Verification** | Docker/CI environments, demo backend/dependency, Prometheus/exporters, bounded ELK, health scheduler/telemetry ingestion, fault harness, verification data collection, local report/LLM integration | Traffic Analysis, Metrics, Logs, Fault Lab, report view | M4 reviews interfaces/security; M3 reviews experiment validity |
| **M3 — Evidence, Models & Research** | Feature windows, fingerprints, rules, ML, confidence, safety/target selector with M1, dataset/experiment design, statistical analysis, model/research artifacts | Decision Trace, Deployment Version Health, Research Experiments, Baseline Comparison | M1 reviews action feasibility; M2 reviews telemetry/reproducibility |
| **M4 — Product Control & API** | FastAPI domain/API, authentication/RBAC, PostgreSQL/Alembic, Redis coordination, incident/audit stores, SSE, frontend design system/shell/data layer | Setup, Command Center, Inventory/Details, Incident List/Details, Policies, Settings | M2 reviews operations/security; M1 reviews control contracts |

This corrects the proposed overload on Member 4: every member implements the UI closest to their domain using the shared M4-owned shell/components. M2 owns report integration and operational infrastructure; M1 owns action/reconciliation; M3 owns research views. M4 owns cohesion, not every page.

### Shared responsibilities

- The primary owner writes design-to-test traceability and first implementation.
- The named reviewer approves interface, failure cases, tests, and documentation.
- A second person must be able to operate/restore every service by Week 19.
- Security, threat model, schema, API compatibility, and research validity are team review gates.
- No owner may merge a high-risk actuation, retry, migration, fault, or authorization change solely on their own review.

## 3. Critical path

```text
deterministic demo/request path
  → route/instance identity + telemetry
  → durable desired/observed model
  → single-writer HAProxy adapter/reconciliation
  → deterministic classification + safety selector
  → action saga + rollback
  → verification + reintegration
  → repeatable fault/baseline runner
  → confirmatory experiments
```

PostgreSQL domain identifiers, logical HAProxy membership naming, correlation IDs, and independent fault truth must stabilize early because nearly every later module consumes them.

Parallel but non-critical:

- UI can consume fixtures/contracts, but it cannot redefine domain semantics.
- ML is evaluated only after rules and the dataset pipeline work.
- ELK augments diagnostics; structured files/Prometheus suffice for the core.
- Ollama/report prose is the last optional feature and has a deterministic fallback.

## 4. Phase roadmap

### Phase 0 — Freeze and preflight (Week 1)

| Field | Plan |
|---|---|
| Owners | M1 architecture compatibility; M2 lab/resources; M3 research preregistration draft; M4 domain/API |
| Reviewers | Whole team and faculty/IP contact where available |
| Dependencies | Approved dossier |
| Work | Resolve open ADRs; pin supported host and candidate component families; translate security/acceptance invariants to tracked tests; create issue/dependency map; define public-disclosure hold |
| Exit | No competing architecture; MVP/stretch/non-goals signed; all identifiers/state machines/route semantics agreed; risk owners assigned |
| Required tests | Documentation link/fence/diagram check; threat/test traceability review |
| Deliverable | Frozen implementation charter and backlog |
| Main risk | Team begins attractive UI/ML work before the control invariants are understood |

### Phase 1 — Deterministic traffic laboratory (Weeks 2–3)

| Field | Plan |
|---|---|
| Owners | M1 HAProxy/NGINX; M2 demo application/dependency/Compose |
| Reviewers | M2 reviews M1 deployment; M1 reviews fault hooks; M3 reviews ground truth |
| Dependencies | Phase 0 names/route groups |
| Work | Compact network/volume design; client→NGINX→HAProxy→four route pools→three/four physical demo instances; version labels; deterministic route/dependency failure switches; correlation/access logs; Prometheus HAProxy/app basics |
| Exit | Same physical B serves multiple logical pools; a manually applied checkout-B membership change preserves B on other routes; configs validate; compact request path runs without control app |
| Required tests | Request routing, pool membership identity, TLS/dev ingress, config rejection, restart, baseline throughput smoke, fault truth timestamp/cleanup |
| Deliverable | Reproducible static traffic lab and compatibility record |
| Main risk | Treating duplicate logical members as duplicate physical capacity |

### Phase 2 — Domain, persistence, API foundations (Weeks 2–4, parallel)

| Field | Plan |
|---|---|
| Owners | M4 PG/Alembic/FastAPI/auth; M3 fingerprint/classification schemas |
| Reviewers | M2 security/deployment; M1 HAProxy naming/desired state |
| Dependencies | Phase 0 schema decisions |
| Work | Projects/environments/services/instances/routes/memberships/versions/policies; user/session/RBAC; standard errors/idempotency/entity versions/correlation; audit append path; Redis key contract; API fixtures/OpenAPI; frontend shell/tokens/auth routing only |
| Exit | Migrations from empty DB; scoped CRUD/contracts; cross-project denial; audit/idempotency; no HAProxy credential in API process |
| Required tests | PostgreSQL constraints/migrations, API auth/RBAC/idempotency/pagination/errors, Redis TTL/schema, secret/config startup validation |
| Deliverable | Versioned domain/API contract and fixture-driven console shell |
| Main risk | Schema churn propagates into telemetry/actions/UI |

### Phase 3 — Observability and evidence windows (Weeks 4–6)

| Field | Plan |
|---|---|
| Owners | M2 ingestion/scheduler/Prometheus; M3 windows/fingerprint primitives |
| Reviewers | M3 validates measurement; M4 validates project/correlation/privacy |
| Dependencies | Phases 1–2 stable IDs and metrics |
| Work | Health probes, exporter/app metrics, structured log schema, Prometheus queries, canonical outcome/latency/retry/queue windows, completeness/freshness/conflict flags, privacy redaction/hash, bounded Redis recent state and PostgreSQL summaries |
| Exit | Independent request/probe/resource sources create reproducible observation vectors and fingerprint golden fixtures; source loss lowers completeness |
| Required tests | Window boundaries, missing/stale data, redaction/cardinality, peer/version comparisons, correlation chain, metric query timeout/fallback |
| Deliverable | Evidence pipeline usable by rules and research artifacts |
| Main risk | High-cardinality telemetry or self-labelled ground truth |

### Phase 4 — Single-writer desired/observed reconciliation (Weeks 5–8)

| Field | Plan |
|---|---|
| Owners | M1 adapter/reconciler; M4 durable desired/action storage and Redis coordination |
| Reviewers | M3 safety invariants; M2 restart/network failure |
| Dependencies | Phases 1–2; Runtime/DPA compatibility |
| Work | Physical actuator isolation; controller generations; domain locks; Runtime read/write with read-after-write; DPA config version transactions for admin structure; desired/observed diff; idempotency; drift; restart recovery; safe mode; operator override skeleton |
| Exit | One API-requested lab weight/state change is durable, constrained to the physically isolated single writer and current generation, observed, audited, idempotent, restart-recoverable, and reversible; invalid config cannot replace running config |
| Required tests | Real HAProxy adapter matrix, ambiguous acknowledgment, stale generation, partial apply/crash points, drift, Redis/PG/HAProxy loss, config validation/reload/rollback |
| Deliverable | Safe generic routing actuator with no classifier dependency |
| Main risk | Mistaking Redis lease for enforceable HAProxy fencing or assuming multi-command atomicity |

### Phase 5 — Rules, incidents, and minimum-scope selector (Weeks 7–10)

| Field | Plan |
|---|---|
| Owners | M3 rules/confidence/evidence certificates/selector; M1 HAProxy-expressible targets/capacity; M4 incident lifecycle |
| Reviewers | M1 checks feasibility; M2 checks evidence; M4 checks audit/API |
| Dependencies | Phases 3–4 |
| Work | Eight-class taxonomy; hard rules; candidate target enumeration; support/counter-evidence; data completeness/confidence; capacity/retry/conflict/cooldown safety envelope; deterministic blast-radius cost; UNKNOWN; incident grouping/revisions/Decision Trace data |
| Exit | Offline fixtures and live route-instance/shared/down scenarios choose the documented unit or abstain; reasons and rejected candidates persist; no HAProxy call yet from classifier test |
| Required tests | Rule priority, property tests on selector, unique physical capacity, unsafe retry, incomplete/conflicting telemetry, incident dedupe/version, false-action fixtures |
| Deliverable | Rules-only EBMSH decision package |
| Main risk | Encoding scenario labels directly into handcrafted rules and overstating generalization |

### Phase 6 — Healing saga and retry safety (Weeks 9–12)

| Field | Plan |
|---|---|
| Owners | M1 action planner/apply/compensation; M4 action attempts/audit/API; M3 safety proof; M2 action observability |
| Reviewers | M3 reviews every scope/retry path; M2 reviews failure recovery |
| Dependencies | Phases 4–5 |
| Work | PLANNED→SAFETY_CHECKED→PREPARED→APPLIED→CONFIRMED→VERIFYING lifecycle; previous snapshots; exact target sets; overlaps; expiry; result-unknown; manual override/approval; method/idempotency/retry budget; predeclared route rate/concurrency/fail-fast controls |
| Exit | Rules-only route-instance, complete-instance, shared-route/retry, and overload-protection actions execute as durable sagas; every crash point recovers/compensates/reviews |
| Required tests | Action/retry matrices, duplicate/overlap, partial target, acknowledgment loss, HAProxy rejection/restart, stale actor, rollback snapshot/audit |
| Deliverable | Core self-healing actuator, still verification-gated |
| Main risk | Calling a compensatable saga an atomic transaction or retrying ambiguous side effects |

### Phase 7 — Verification and reintegration vertical slice (Weeks 11–14)

| Field | Plan |
|---|---|
| Owners | M2 verification evidence collection; M3 criteria/adaptive windows/flapping; M1 reintegration application; M4 persistence/events |
| Reviewers | M3 validates inference; M1 validates routing; M4 validates lifecycle |
| Dependencies | Phase 6 |
| Work | Probe/real-traffic verification; affected symptom and unaffected capacity criteria; effective/ineffective/harmful/insufficient verdict; QUARANTINED→PROBING→stages; sample/window gates; low traffic; hysteresis/cooldown/max attempts; rollback/review; SSE events |
| Exit | Complete rules-only incident runs from evidence through bounded action, confirmation, verification, staged recovery or rollback; control failures leave traffic on LKG |
| Required tests | Every class/action acceptance case, low traffic, flap, harmful/insufficient verdict, restart at every stage, Redis/Prometheus loss, rollback failure |
| Deliverable | **Core MVP vertical slice** independent of ML, LLM, ELK, and full frontend |
| Main risk | Verifying only that an error fell, while ignoring capacity displaced elsewhere |

### Phase 8 — Product console and operational workflows (Weeks 8–16, parallel integration)

| Field | Plan |
|---|---|
| Owners | M4 shell/setup/command/incidents/policies; M1 topology/matrix/actions/reintegration; M2 traffic/metrics/logs/fault UI; M3 Decision Trace/version/research UI |
| Reviewers | Cross-paired by ownership table; M4 reviews consistency/accessibility |
| Dependencies | API fixtures from Phase 2; real event contracts increasingly from Phases 4–7 |
| Work | Semantic themes, TanStack Query/SSE cursor/gap handling, core 22 screens in priority order, desired/observed visuals, stale/unknown/safe mode, authorization, responsive/keyboard/accessibility, action confirmations |
| Exit | Operator can observe and explain an end-to-end incident, authorize permitted overrides, and inspect audit without direct DB/HAProxy/Kibana use; lower-priority settings/research views may be read-only initially |
| Required tests | Component/visual states, Playwright journeys, SSE reconnect/gap, RBAC, keyboard/table/topology alternatives, WCAG 2.2 AA review |
| Deliverable | Cohesive infrastructure console, not four unrelated feature styles |
| Main risk | UI claims `applied/healthy` from desired state before observed confirmation |

### Phase 9 — Experiment automation and model selection (Weeks 13–17)

| Field | Plan |
|---|---|
| Owners | M2 fault/load/manifest runner; M3 dataset/models/calibration/statistics; M1 baseline HAProxy configs; M4 experiment persistence/API |
| Reviewers | M3 reviews ground truth; M2 reproducibility; whole team reviews baseline fairness |
| Dependencies | Rules-only vertical slice; stable telemetry |
| Work | Four baseline profiles; eight faults; independent truth ledger; clean reset/validity; grouped dataset; rules/LR/RF; held-out evaluation/calibration; artifact digests; research UI; pilot variance/power |
| Exit | One command/API-controlled isolated run produces a complete reproducible bundle; 5–10 pilot blocks/scenario establish frozen thresholds/intensities; model selected by gates or rules-only retained |
| Required tests | Injector expiry/cleanup, baseline parity, manifest/schema/hash, grouped leakage, model metrics/reproduction/fallback, figure regeneration |
| Deliverable | Frozen confirmatory experiment protocol and selected inference artifact |
| Main risk | Data leakage, non-independent windows, baseline misconfiguration, host contention |

### Phase 10 — Reporting, full observability, and optional features (Weeks 15–18)

| Field | Plan |
|---|---|
| Owners | M2 ELK/Ollama/report pipeline; M4 report API/export; M3 grounded fact schema/checklists; M1 topology/action references |
| Reviewers | M4 security; M3 unsupported claims; M2 operations |
| Dependencies | Stable incident/action/report facts |
| Work | Bounded Filebeat/Logstash/Elasticsearch/Kibana profile; curated logs; deterministic report; optional Qwen 8B Q4 Ollama; schema/fact/entity validators; one repair then fallback; audit/export; resource profile |
| Exit | Complete report is generated with Ollama absent; adversarial/invalid generative output is rejected; ELK/Ollama can stop without traffic/control impact |
| Required tests | Retention/disk, log redaction/injection, LLM grounding/OOM/timeout/wrong digest/no control access, deterministic export |
| Deliverable | Optional diagnostic/reporting layer with hard isolation |
| Main risk | Spending scarce weeks on prose quality or running ELK+LLM beyond laptop capacity |

### Phase 11 — Hardening, freeze, and full rehearsal (Weeks 17–19)

| Field | Plan |
|---|---|
| Owners | M1 actuation/load; M2 deployment/failure/security ops; M3 model/safety; M4 API/UI/security |
| Reviewers | Cross-team; faculty demonstration review |
| Dependencies | Core and optional profiles feature-complete |
| Work | Threat-model tests; 24 h soak; performance/resource caps; backup/restore; upgrade/rollback; clean-host install; public profile exposure; complete class/action acceptance; operator runbooks; freeze code/config/model |
| Exit | No stop-ship condition; release candidate hashes frozen; every service has owner+backup operator; known deviations in risk register |
| Required tests | Full `18_TESTING...` MVP gates, port/mount scan, chaos/recovery, accessibility, fresh host, demo fallback |
| Deliverable | Frozen research/demo release candidate and recovery kit |
| Main risk | Late architectural bug in reconciliation or insufficient experiment time |

### Phase 12 — Confirmatory experiments, analysis, and handoff (Weeks 19–22)

| Field | Plan |
|---|---|
| Owners | M3 statistical lead; M2 run operations; M1 baseline/data-plane integrity; M4 artifact/report/UI/demo |
| Reviewers | Whole team verifies exclusions/results; external faculty/IP review if available |
| Dependencies | Frozen Week 19 build/protocol; pilot complete |
| Work | Randomized 30-block main trials; daily artifact integrity/rig checks without outcome tuning; pre-registered analysis; figures/tables; limitations/negative results; professor demo; implementation and operations documentation; IP disclosure update before publication |
| Exit | Research exit criteria met; results independently regenerated; demo survives fallback/offline/control-failure rehearsal; no confidential mechanism published before review decision |
| Required tests | Artifact checksums, paired-block completeness, statistical script regression, clean reproduction, final smoke/security/backup |
| Deliverable | Evaluated project, paper proposal/results package, college IP-cell engineering disclosure, final demonstration |
| Main risk | 960 runs exceed available rig time; mitigation is early automation, overnight schedule, qualified second rig/blocking—not fabricated replication |

## 5. Week-by-week integration milestones

| Week | Integrated demonstrable outcome |
|---:|---|
| 1 | Frozen scope, contracts, invariants, risks, disclosure rule |
| 2 | Static NGINX→HAProxy→logical pools request path; DB/API skeleton |
| 3 | Route-instance manual isolation; deterministic fault truth; auth/domain migration |
| 4 | Prometheus/correlation evidence; API contracts and shell fixtures |
| 5 | Canonical windows/fingerprints; Runtime state reader |
| 6 | Completeness/conflict evidence; DPA structural transaction validation |
| 7 | Desired/observed diff and sole writer; rules fixtures |
| 8 | Idempotent observed-confirmed weight change; incident/matrix fixture UI |
| 9 | Evidence certificate and candidate units; drift/restart recovery |
| 10 | Rules-only classification/UNKNOWN; Decision Trace data |
| 11 | Durable route-instance action; hard retry policy |
| 12 | Complete-instance/shared/overload action paths; compensation |
| 13 | Effective/ineffective/harmful verification; SSE integration |
| 14 | Staged reintegration/flapping; rules-only vertical MVP |
| 15 | Four baselines and experiment bundle; core operator E2E |
| 16 | Pilot faults; grouped dataset; accessible core console |
| 17 | LR/RF selection or rules-only decision; public profile draft |
| 18 | Deterministic/validated LLM report and optional ELK; first full rehearsal |
| 19 | Release/protocol freeze after security/recovery/acceptance gates |
| 20 | Confirmatory trial tranche 1; no tuning |
| 21 | Trial tranche 2; pre-registered analysis and reproduction |
| 22 | Results, limitations, professor/IP handoff, offline/public demo rehearsal |

## 6. What must work without ML, LLM, or frontend

This is the non-negotiable headless core by the end of Week 14:

1. NGINX/HAProxy serve all four route groups from logical memberships.
2. Prometheus/probes produce bounded, privacy-safe evidence and source completeness.
3. Deterministic rules distinguish hard down, scoped/shared/overload patterns when support is sufficient and otherwise return UNKNOWN.
4. Safety enumerates evidence-supported, capacity-safe HAProxy target sets and enforces hard retry semantics.
5. One worker durably applies/observes/rolls back route-instance and instance actions with generations, idempotency, audit, drift, and restart recovery.
6. Verification checks the affected symptom **and** preserved unaffected capacity; reintegration is staged and can pause/roll back.
7. REST/API or an authenticated administrative test client exposes incidents/actions/status; the experiment runner needs no browser.
8. Independent fault truth can reproduce every required class/action acceptance test.
9. Deterministic structured reports remain available without Ollama.

If this core is incomplete, stop ML/LLM/visual polish and move all members to the critical path.

## 7. Scope triage rules

### Preserve first

- route-instance logical pool representation;
- desired/observed single-writer reconciliation;
- evidence completeness/conflict and UNKNOWN;
- capacity/retry safety;
- durable snapshot/apply/confirm/verify/rollback;
- independent fault truth and four baselines;
- security isolation and data-plane continuity.

### Cut in this order if behind

1. generative LLM path (keep template report);
2. Kibana/ELK product integration (keep JSON logs and Prometheus);
3. advanced animations/custom dashboard features;
4. optional notebook UI and nonessential exports;
5. ML model deployment (keep rules and offline comparison);
6. non-core screens beyond read-only contract-complete views;
7. adaptive verification tuning (keep conservative fixed evidence windows, still verify both objectives).

Never cut rollback, UNKNOWN abstention, retry safety, project authorization, audit, ground truth, or observed-state confirmation to save schedule.

## 8. Risk-triggered checkpoints

| Trigger | Deadline | Required response |
|---|---:|---|
| DPA/HAProxy pinned versions incompatible | End W2 | Freeze compatible 3.2 patch pair; if DPA remains blocking, pre-generate structure and restrict MVP to Runtime healing while documenting admin limitation |
| Stable membership identity/capacity unresolved | End W3 | Stop feature work; architecture review—later evidence is invalid without it |
| Sole-writer ambiguous apply not recoverable | End W8 | Block classifier/UI integration and simplify action set until invariant passes |
| Rules-only vertical slice incomplete | End W14 | Cut LLM/ELK/ML deployment and non-core UI; swarm on core |
| Pilot cannot distinguish scenarios | End W16 | Adjust controlled fault/telemetry during pilot, document gap; do not tune final data |
| RF fails gates | End W17 | Select calibrated logistic or rules-only; no deadline-driven model claim |
| Security/restore stop-ship open | End W19 | Do not expose public demo or start confirmatory results on unstable build |
| Confirmatory runtime forecast exceeds W22 | W16 onward | Start night runs early, use second qualified rig with rig blocks, or predeclare a narrower confirmatory family; never lower independence post hoc |

## 9. Review and quality cadence

- **Daily asynchronous:** owners post interface changes, failures, artifact hashes, and blockers—not percent complete.
- **Twice weekly:** 30-minute integration demonstration against the current request path; fixture-only UI does not count after its API exists.
- **Weekly:** risk register/ADR change, resource footprint, test failure trend, and research artifact review.
- **At every phase exit:** owner demonstrates negative/failure paths; reviewer signs test evidence and recovery procedure.
- **Weeks 8, 14, 19:** architecture/safety gates. Scope or protocol cannot pass by majority vote if a stop-ship invariant fails.
- **Before any public disclosure:** IP/confidentiality check of paper, poster, repository, screenshots, and demo narrative.

## 10. Definition of done per work item

A feature is done only when:

- its input/output/ownership/failure/timeout/security semantics match the dossier;
- implementation and migration/config changes are reviewed by the named secondary;
- unit/component/integration/failure tests appropriate to risk pass;
- metrics, structured logs, correlation, audit, and safe error behaviour exist;
- resource/retention impact is measured;
- restart, duplicate, stale, partial, unauthorized, and dependency-loss cases are resolved;
- UI states include loading/empty/stale/error/permission/accessibility where applicable;
- operator/recovery and research documentation are updated;
- it introduces no undeclared recurring dependency or hidden request-path coupling.

## 11. Student feasibility verdict

The frozen MVP is difficult but feasible for four students in 22 weeks **only** with the rules-only vertical slice and safety invariants prioritized. The full 22-screen surface can be contract-complete, but polish must concentrate on Command Center, matrix, incident/Decision Trace, actions, reintegration, and Fault/Research views. ELK and the 8B LLM are optional profiles. Multi-node HA, autonomous structural rewrites, production customer onboarding, and model auto-training are excluded. Early automation makes the large experiment matrix possible; manual trial operation does not.

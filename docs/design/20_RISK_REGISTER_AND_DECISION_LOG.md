# Risk Register and Architecture Decision Log

## 1. Governance

This document records risks and frozen technical choices. It prevents implementation convenience from silently changing the research mechanism or safety model.

- Likelihood (`L`) and impact (`I`) use 1–5; exposure is `L × I`.
- 15–25 is critical, 8–14 high, 4–7 medium, 1–3 low.
- “Residual” is expected exposure after the planned mitigation, not a guarantee.
- The assigned owner maintains evidence and triggers the contingency. Architecture/safety/IP risks require team review.
- A decision changes only through a new superseding ADR with migration, test, research-comparability, and disclosure consequences.

## 2. Risk register

| ID | Risk and technical effect | L | I | Exposure | Leading indicator | Preventive mitigation | Contingency | Owner | Residual |
|---|---|---:|---:|---:|---|---|---|---|---:|
| R01 | **Primary mechanism is anticipated/obvious over prior art.** Patent application effort or novelty claim is unsupportable. | 4 | 5 | 20 | Search finds claims covering evidence-supported minimum target plus verification | Treat as exploration only; professional claim-chart search across cited patents/CPC families/non-patent literature; preserve narrow mechanism and ablations; confidentiality review | Frame outcome as research/engineering contribution; do not file or claim novelty without counsel | M3/team | 15 |
| R02 | Route × instance quarantine is presented as the invention despite direct request-type/target-group prior art. | 3 | 4 | 12 | Abstract/demo leads with selective quarantine alone | Explicit “standard/not claimed” list; always describe EBMSH evidence/optimization/verification nucleus | Remove patent wording; retain useful product feature | M3/M4 | 4 |
| R03 | Duplicate logical memberships are counted as duplicate physical capacity, allowing unsafe drain. | 3 | 5 | 15 | Residual capacity increases when another route membership is added | Capacity ledger keyed by physical instance/resource limit; property tests and independent oracle | Block action and enter review until capacity model reconciled | M1 | 5 |
| R04 | Route matching differs between NGINX, HAProxy, telemetry, and policy, corrupting evidence/action scope. | 3 | 5 | 15 | Same request receives different route-group IDs across logs | NGINX does not own application routing; one canonical HAProxy map/order and route registry; golden path tests | Safe mode; freeze mutations; validate/adopt one mapping and rebuild windows | M1/M4 | 5 |
| R05 | False route/instance/version classification quarantines healthy traffic. | 3 | 5 | 15 | Actionable-class precision/calibration below gate; rising rollbacks | Rules-first hard gates, completeness/conflict, calibrated probabilities, safety envelope, bounded target and verification | Rules-only/recommendation mode; rollback and manual review | M3 | 8 |
| R06 | Shared dependency/route failure is mistaken for many bad instances, causing mass ejection. | 3 | 5 | 15 | Similar fingerprint appears across peers while ejection count rises | Cross-instance support/counter-evidence, shared-route class, max quarantine/capacity floor, retry suppression | Stop automation; restore instance memberships; fail-fast/rate/concurrency route policy | M3/M1 | 5 |
| R07 | Missing/stale/poisoned telemetry appears confident and actuates. | 4 | 5 | 20 | Source age/conflicts/cardinality change without confidence reduction | Source-specific completeness/freshness, independent probes/metrics, bounded schemas, disagreement penalty, UNKNOWN | Safe mode/no stage advance; use hard connectivity rules only; operator review | M2/M3 | 8 |
| R08 | Two controllers write HAProxy after Redis lease partition (“split brain”). | 2 | 5 | 10 | Two generations/processes can open Runtime/DPA path | One physical worker mount/network credential; one replica; generation/version checks; Redis lock only auxiliary | Revoke sockets/credentials, safe mode, read full state, manually reconcile | M1/M4 | 5 |
| R09 | HAProxy apply succeeds but acknowledgment is lost; blind retry causes inconsistent action. | 3 | 5 | 15 | Socket timeout with observed state changed | Durable attempt/idempotency, result-unknown, full read-after-timeout, exact target/value comparison, no blind mutation retry | Adopt confirmed observed result or compensate; otherwise needs review | M1 | 5 |
| R10 | Multi-member action partially applies, leaving inconsistent scope. | 3 | 5 | 15 | Some target members changed before error | Exact previous/requested sets, deterministic order, per-step attempts, compensation, observed set comparison; call it a saga | Restore changed subset; block overlapping action; manual review on compensation failure | M1 | 8 |
| R11 | Structural DPA/reload action rejects config or drops connections. | 2 | 5 | 10 | Config version conflict/native validation failure/reload errors | Structural changes are admin-only in MVP; OCC transaction; native `haproxy -c`; graceful reload and prior config | Abort transaction; keep running config; restore exact validated version | M1/M2 | 4 |
| R12 | HAProxy restart loses Runtime state and re-enables quarantined traffic. | 3 | 5 | 15 | Runtime observed generation resets/state file missing | PostgreSQL desired is authoritative; state-file restart aid; startup reconciliation before automation; config/policy defaults safe | Enter safe mode; read full state; reapply known desired state after capacity check | M1 | 5 |
| R13 | Unsafe retry duplicates payment/order side effects or amplifies failure. | 3 | 5 | 15 | POST/PATCH backend attempts >1; response-loss ambiguity | Hard method/idempotency/route matrix, max one cross-instance retry, application dedup contract, model/LLM cannot override | Disable cross-instance retry; fail original request; incident/audit | M1/M3 | 4 |
| R14 | Healing transfers traffic onto insufficient peers and causes overload cascade. | 3 | 5 | 15 | Residual capacity/queue crosses floor immediately after drain | Projected physical capacity, active quarantine/queue/concurrency limits, canary-bounded weight reduction, verification | Roll back/reduce scope; admission control/fail fast; review | M3/M1 | 8 |
| R15 | Recovery flaps and repeatedly admits/removes bad capacity. | 4 | 4 | 16 | Frequent stage reversions or alternating evidence | Hysteresis, adaptive cooldown, minimum samples/window, max attempts, intervention memory | Keep quarantined, stop attempts, manual review | M3/M2 | 6 |
| R16 | PostgreSQL/Redis/Prometheus loss allows stale action or stalls normal traffic. | 3 | 5 | 15 | Dependency health/freshness fails | Control plane out of request path; suppress mutation/stage advancement; LKG HAProxy; rules-only where valid | Safe mode; restore dependency; full reconciliation/fresh windows | M2/M4 | 5 |
| R17 | Backend registration/probe becomes SSRF/config injection. | 3 | 5 | 15 | Private/metadata/redirect/dynamic DNS target accepted | CIDR/port/route allowlists; canonical resolution at connect; redirect off; no raw directives; isolated probe network | Disable registry/probes; rotate access; security review/audit | M4/M2 | 5 |
| R18 | Compromised telemetry/backend poisons classification and induces false quarantine. | 3 | 4 | 12 | One source diverges from independent exporter/probe/peer evidence | Multi-source trust weights, source identity, bounds/cardinality, conflicts, safety cap, audit | Exclude source; rules-only/UNKNOWN; restore membership if harmful | M2/M3 | 6 |
| R19 | Public demo exposes fault APIs, stores, HAProxy control, logs, or addresses. | 2 | 5 | 10 | Port scan/path enumeration reveals internal surface | Only NGINX 443; lab profile absent; VPN/local operator; Viewer demo; firewall/network/mount tests | Kill public ingress, rotate credentials, restore sanitized demo | M2/M4 | 4 |
| R20 | LLM hallucinates root cause/action or leaks a secret. | 4 | 4 | 16 | Unreferenced entity/number/action passes to report | Allowlisted redacted facts, fact IDs, JSON validator, forbidden claims, no control path, one retry then template | Disable Ollama; invalidate report version; template regeneration and audit | M2/M4 | 4 |
| R21 | ELK plus Ollama exhausts student laptop memory/disk and invalidates trials. | 5 | 3 | 15 | Swap/OOM/disk watermark/controller lag | Profiles/resource caps; never concurrent on 16 GB; short retention; separate generator/analysis | Stop optional services; compact logs/template reports; rerun invalid trial | M2 | 4 |
| R22 | Dataset leakage/pseudoreplication creates misleading ≥90% result. | 4 | 5 | 20 | Random window split, repeated run IDs across folds, accuracy-only reporting | Group by run/injection; held-out intensity/mix; pipeline-only fit; macro/per-class/calibration/false-action; audit split | Withdraw result, rebuild split, rerun evaluation/model selection | M3 | 5 |
| R23 | Baselines are unfair or tuned differently, invalidating research comparison. | 3 | 5 | 15 | Timeouts/retries/capacity/workload differ beyond declared policy | Common manifest/images/config; matched seeds; baseline diff review; exact artifact capture | Mark trial invalid; correct before confirmatory freeze; report limitation | M3/M1 | 5 |
| R24 | Confirmatory run matrix cannot finish in semester. | 4 | 4 | 16 | Pilot runtime/invalid rate projects beyond Week 22 | Automate by Week 15; night runs; qualified second rig as block; 30-block power review early | Predeclare narrower primary scoped-fault family, keep others exploratory; never fabricate independence | M2/M3 | 8 |
| R25 | UI renders desired state/action acceptance as observed success. | 3 | 4 | 12 | User sees healthy/applied before Runtime confirmation | Separate desired/observed/entity versions; `RESULT UNKNOWN`; SSE gap refresh; state fixture/E2E tests | Disable mutations in UI; rely on API/audit until corrected | M4/M1 | 4 |
| R26 | Audit “immutability” is overstated or operator can silently alter history. | 3 | 4 | 12 | Application DB role can update/delete audit rows; hash gaps | Append-only DB permissions/triggers, actor/time/entity version, hash chain, off-host backup/export | Safe mode/security incident; restore/compare backup; disclose assurance limit | M4 | 6 |
| R27 | Backup exists but cannot restore desired/action/config consistency. | 3 | 5 | 15 | No clean-host restore or config generation mismatch | Weekly restore; PostgreSQL + exact validated configs/generation/artifact manifest; pre-migration backup | Preserve LKG HAProxy; restore to new volumes; manual adopt/reconcile | M2/M4 | 5 |
| R28 | NGINX/HAProxy host is a single point of failure mistaken for a self-healing guarantee. | 4 | 5 | 20 | Demo narrative claims availability through proxy host crash | Explicit boundary; supervisor restart only; multi-host customer HA is future; monitor data-plane process | Recover/restart data plane; disclose outage; future redundant pair design | M1/M4 | 12 |
| R29 | Component/version/license drift breaks reproducibility or redistribution. | 3 | 4 | 12 | Floating tag/model changes/API mismatch/license unclear | Pin digests; compatibility matrix; SBOM/license/model review; archive allowed artifacts or download manifest | Freeze last validated set; replace optional model; rerun affected tests | M2 | 5 |
| R30 | Team scope/UI burden leaves core transaction unsafe. | 4 | 5 | 20 | Core Week 14 gate slips while optional feature work continues | Critical-path gates; distributed UI; cut order; rules-only core; cross-review | Stop LLM/ELK/ML/full UX and swarm on reconciliation/safety/tests | Team lead | 5 |
| R31 | Fingerprint cardinality/storage growth destabilizes Prometheus/Redis/PG/ES. | 3 | 4 | 12 | Series/key/index growth superlinear with requests/signatures | Enumerated route/instance/version labels, bounded signatures, no request IDs in metric labels, TTL/retention, budgets | Drop/quarantine high-cardinality source; aggregate offline; safe mode if evidence incomplete | M2/M3 | 4 |
| R32 | Low-traffic routes cannot gather verification samples and remain stuck or are prematurely restored. | 4 | 3 | 12 | Windows expire below minimum samples | Synthetic probes, maximum wall window, insufficient-evidence state, manual approval—not automatic success | Maintain quarantine/limited probe stage; review/extended scheduled test | M2/M3 | 6 |

## 3. Assumption register

| ID | Frozen assumption | Evidence/validation required | If false |
|---|---|---|---|
| A01 | HTTP(S) request routing is the MVP protocol; routes can be mapped to a finite ordered group set. | Customer/demo route manifest and HAProxy match tests | Unsupported protocols/routes remain static/non-healed |
| A02 | Each physical instance has stable ID, service, deployment version, and conservative capacity metadata. | Registration/inventory source; duplicate/restart tests | Version/scoped automation blocked; use instance-only standard checks |
| A03 | The same instance can be represented as separate HAProxy server entries in multiple predeclared pools. | Supported-version compatibility test | Route-instance action cannot ship; fall back to larger safe unit and disclose lost nucleus |
| A04 | Prometheus evidence is available within the selected window and cardinality budget. | Pilot scrape/query delay and missingness tests | Hard rules only or UNKNOWN/safe mode |
| A05 | Demo/customer application declares retry/idempotency semantics per route. | Policy onboarding review and synthetic dedup tests | Cross-instance retry disabled |
| A06 | One actuator writer is operationally acceptable for student MVP. | Failure rehearsal and project requirements | A local per-HAProxy fencing actuator/consensus design is required; schedule expands |
| A07 | HAProxy Runtime/DPA versions support required reads/writes and config OCC. | Pinned compatibility matrix | Restrict action/structure set to verified operations |
| A08 | Fault lab uses only controlled synthetic targets/data. | Environment allowlist and public exposure test | Fault capability is disabled |
| A09 | Four students can access 16 GB laptops and one ≥24 GB/separate generator rig for full trials. | Week 1 resource inventory | Sequential optional services, college lab/second machines, narrower predeclared trials |
| A10 | Patent-sensitive disclosure can be reviewed before public release. | College IP process/timeline | Keep mechanism private and delay public paper/repo details or waive filing exploration knowingly |

## 4. Architecture decision records

### ADR-001 — Keep NGINX and HAProxy roles non-overlapping

- **Status:** Accepted.
- **Decision:** NGINX terminates public TLS, applies edge headers/limits, serves/proxies UI/API/SSE, and forwards application traffic. HAProxy alone matches route groups, balances logical pools, owns health/queue/retry/weights/runtime state.
- **Rationale:** one authoritative application routing policy and one dynamic actuator; avoids conflicting health/retry semantics.
- **Rejected:** dynamic upstream healing in both proxies; removing NGINX despite fixed stack.
- **Revisit:** only if a measured request-path or protocol limitation makes the two-hop edge unacceptable.

### ADR-002 — Represent physical instances as independent logical route memberships

- **Status:** Accepted.
- **Decision:** Predeclare a pool per route group; create a stable member for every eligible `(route_group, physical_instance)`. Membership has independent weight/state while physical identity/capacity is shared.
- **Rationale:** HAProxy Runtime API acts on server entries, enabling checkout-B exclusion without disabling public-B.
- **Risk:** configuration growth and duplicate capacity accounting.
- **Rejected:** runtime structural pool creation per incident; path-specific logic only in control plane.

### ADR-003 — Select Evidence-Bounded Minimum-Scope Healing as the nucleus

- **Status:** Accepted for research and patent exploration; legal novelty unresolved.
- **Decision:** Construct failure-support/counter-evidence across route×instance×version, enumerate expressible target sets, reject unsupported/unsafe scopes, minimize blast-radius cost, apply a durable bounded set, then verify symptom relief and unaffected-capacity preservation.
- **Rationale:** technically specific, measurable, implementable, and stronger than selective quarantine alone.
- **Rejected:** route-instance quarantine as the invention; generic “AI self healing”; combining every ideated mechanism.

### ADR-004 — Limit supporting mechanisms to three

- **Status:** Accepted.
- **Decision:** privacy-minimized multidimensional fingerprint; deterministic action safety envelope; evidence-gated verification/reintegration.
- **Rationale:** each is necessary to execute/test the nucleus; more mechanisms would dilute feasibility and disclosure clarity.

### ADR-005 — Use a modular monolith with two process roles

- **Status:** Accepted.
- **Decision:** one Python codebase/domain with FastAPI API process and a worker process. The API has no HAProxy actuation access; worker is sole writer.
- **Rationale:** clear privilege boundary without microservice operational overhead.
- **Rejected:** per-module microservices, Celery/RabbitMQ/Kafka, control logic in request path.

### ADR-006 — PostgreSQL is durable truth; Redis is disposable coordination

- **Status:** Accepted.
- **Decision:** desired state, actions/snapshots, incidents, policies, audit, models/experiments live in PostgreSQL. Redis stores leases, windows, cursors, cooldowns, dedupe/rate state and can be rebuilt.
- **Rationale:** one authoritative relational store and one fit-for-purpose ephemeral store.
- **Rejected:** Redis as durable desired state; Elasticsearch/Prometheus as business database; redundant databases.

### ADR-007 — Enforce a physical single actuator writer

- **Status:** Accepted for MVP.
- **Decision:** exactly one worker replica/container can reach the Runtime Unix socket and DPA credential/network. Redis lease/generation/domain locks coordinate but are not treated as HAProxy fencing.
- **Rationale:** HAProxy Runtime writes cannot validate an external fencing token; physical capability containment is the enforceable boundary.
- **Rejected:** multiple workers relying solely on Redis Redlock/lease; exposing the socket to API.
- **Revisit:** multi-HAProxy/HA controller requires a narrow local actuator that enforces generations or another qualified consensus/ownership design.

### ADR-008 — Desired state with observed-state confirmation

- **Status:** Accepted.
- **Decision:** PostgreSQL desired generation is authoritative intent; full HAProxy state/config read is observed truth. No action is `APPLIED/COMMITTED` based solely on a command response.
- **Rationale:** handles restart, lost acknowledgment, manual drift, and audit reconstruction.
- **Rejected:** fire-and-forget Runtime commands; treating state file as durable truth.

### ADR-009 — Runtime API for healing, Data Plane API for structure

- **Status:** Accepted.
- **Decision:** Runtime handles predeclared state/weight/drain operations. DPA with config version/OCC and native validation handles administrator-approved structural changes. No structural rewrite during automatic incident healing in MVP.
- **Rationale:** Runtime is fast but volatile; structural reloads have larger failure/connection risk.
- **Version:** start with a qualified HAProxy 3.2 LTS/DPA 3.2 pair; pin exact patches after test.

### ADR-010 — A healing “transaction” is a durable saga

- **Status:** Accepted.
- **Decision:** prepare snapshots, apply deterministic target steps, confirm observed state, verify, commit or compensate/rollback/review. Do not claim atomicity across HAProxy and PostgreSQL.
- **Rationale:** Runtime multi-command sequences and external DB writes do not share a transaction coordinator.
- **Rejected:** renaming a canary as an atomic commit protocol; blind retry.

### ADR-011 — Rules first; Random Forest is conditional

- **Status:** Accepted.
- **Decision:** hard rules own down/retry/capacity/completeness/conflict/reintegration safety. Compare rules, Logistic Regression, and calibrated Random Forest on run-grouped data. Select the simplest artifact meeting predeclared gates; rules-only remains deployable.
- **Rationale:** structured modest data, explainability, safe fallback; model preference is not evidence.
- **Rejected:** deep learning, reinforcement learning, automatic retraining/deployment, LLM classification.

### ADR-012 — UNKNOWN is a safety outcome

- **Status:** Accepted.
- **Decision:** low support/completeness, conflict, OOD, or low calibrated confidence maps to UNKNOWN and no destructive automatic routing action. Independently hard retry suppression may still apply.
- **Rationale:** forced classification converts uncertainty into outages.

### ADR-013 — Retry safety is independent and non-ML

- **Status:** Accepted.
- **Decision:** per-route method/idempotency/dedup/ambiguity/budget rules; maximum one cross-instance retry in MVP; shared failure/overload suppression. Neither ML nor LLM can override.
- **Rationale:** retry can duplicate side effects or amplify load even with a correct failure class.

### ADR-014 — Verification has two objectives

- **Status:** Accepted.
- **Decision:** require affected symptom improvement and unaffected route/capacity preservation, plus observed routing confirmation. Evidence-gated stages use samples and bounded time; 5/20/50/100 are defaults.
- **Rationale:** an action can lower errors by rejecting/ejecting too much healthy capacity.
- **Rejected:** fixed delay then automatic restore; error-rate-only canary success.

### ADR-015 — SSE, not WebSockets, for console updates

- **Status:** Accepted.
- **Decision:** REST for authenticated commands; one-way ordered SSE with cursors for events; snapshot+gap recovery.
- **Rationale:** client does not need bidirectional streaming; SSE is simpler through NGINX.
- **Revisit:** only if a future interactive streaming protocol cannot be expressed as REST plus SSE.

### ADR-016 — Prometheus metrics and bounded ELK logs; OpenTelemetry later

- **Status:** Accepted.
- **Decision:** Prometheus/exporters are MVP numeric evidence; structured correlation logs work with bounded file logging and optional ELK. OpenTelemetry traces are later, initially limited to control-plane profiling if needed.
- **Rationale:** request correlation and HAProxy metrics satisfy MVP; a trace backend adds resource/operational burden and cannot see dependencies without customer instrumentation.
- **Rejected:** inventing “distributed traces” from logs; mandatory ELK on 8 GB.

### ADR-017 — The local LLM is a validated report renderer only

- **Status:** Accepted.
- **Decision:** optional Ollama Qwen3 8B Q4_K_M consumes redacted allowlisted fact bundles and emits schema/fact-referenced prose; validators reject unsupported output; deterministic template always exists; no HAProxy/API credentials/network.
- **Rationale:** useful incident communication without making probabilistic prose a control mechanism or recurring API cost.
- **Rejected:** chatbot, root-cause oracle, source-code diagnosis, routing recommendation/action.

### ADR-018 — Docker Compose profiles and honest zero-cost claim

- **Status:** Accepted.
- **Decision:** compact, lab, public demo, optional LLM/analysis profiles on user hardware; LAN/VPN is the guaranteed demo fallback, optional free tunnel/static host is replaceable.
- **Rationale:** no mandatory SaaS while acknowledging hardware, Internet, DNS, and power realities.
- **Rejected:** Kubernetes/service mesh; “permanently free cloud”; mandatory free tier.

### ADR-019 — Single primary research metric with guardrail

- **Status:** Accepted.
- **Decision:** time-integrated ground-truth healthy route capacity preserved is primary; successful-request fraction is a non-inferiority gate. Thirty independent matched blocks, Friedman then Holm-adjusted paired tests/effect sizes.
- **Rationale:** directly measures minimum-scope effect while preventing do-nothing gaming.
- **Rejected:** raw classifier accuracy or MTTR alone as primary; per-second samples as replicates.

### ADR-020 — HAProxy and ingress host HA are outside MVP

- **Status:** Accepted.
- **Decision:** data-plane process/host loss is a real outage managed by supervisor/manual recovery in the student deployment. Future customer integration may use independently qualified redundant hosts.
- **Rationale:** solving distributed data-plane HA/consensus would turn the project into a different, infeasible platform.
- **Communication:** never claim the load balancer heals its own host/process failure.

### ADR-021 — Audit is tamper-evident within declared trust, not absolute immutability

- **Status:** Accepted.
- **Decision:** append-only application role, DB constraints/permissions, actor/entity versions, hash chaining, and off-host encrypted backup/export. Privileged database/host compromise can still alter history and is in the threat model.
- **Rationale:** honest assurance without adding blockchain or external paid ledger.

### ADR-022 — The frontend is evidence/control oriented

- **Status:** Accepted.
- **Decision:** premium OLED/charcoal visual system with Geist typography, sparse functional indigo/emerald/rose accents, fact-linked natural-language situation briefs, progressive-disclosure matrix density, and `Cmd/Ctrl+K` command hub. The EBMSH Decision Trace is an interactive diagnostic canvas whose verification phase splits into affected-relief and preserved-cohort tracks; every routing review includes a Blast Radius Map naming changed and protected logical memberships. Light/Dark/System remain semantic preferences, with dark as the canonical operations expression. Accessible desired/observed, uncertainty, dual-verification, and non-color states are mandatory; domain pages remain distributed across the team.
- **Rejected:** generic KPI-card dashboard, sterile raw-table-first experience, decorative AI/agent styling, chat-first logs, permanent topology motion, and live drag-to-rewire routing.

## 5. Resolved prompt tensions

| Tension | Frozen resolution |
|---|---|
| “Transactional remediation” versus external non-atomic APIs | Durable compensatable saga; no false atomicity claim |
| Redis fencing versus HAProxy’s lack of fencing-token check | Physical single writer plus durable generations; Redis is advisory coordination |
| Public zero-cost URL versus no external dependency | Self-hosted LAN/VPN fallback; public hostname/tunnel optional and replaceable |
| Random Forest “preferred” versus evidence | Candidate only; select by grouped evaluation and calibration gates |
| Full ELK and local 8B LLM versus student hardware | Optional profiles, sequential on 16 GB, absent from compact core |
| Route-specific isolation versus duplicated capacity | Logical membership state; physical instance capacity ledger |
| Runtime speed versus restart persistence | PostgreSQL desired truth + Runtime observation/reapply; state file as aid |
| Automatic route controls versus DPA reload risk | Predeclare rate/concurrency/fail-fast maps/controls; automatic incident actions remain Runtime-expressible |
| Fixed reintegration percentages versus evidence | Percentages are policy defaults; samples/window/hysteresis decide advancement |
| “Self healing” versus control-plane/data-plane host failure | Heals backend routing degradation; does not claim self-repair of proxy host |
| Observability breadth versus product identity | Telemetry exists only to decide/verify traffic routing; not a generic platform |

## 6. Decision-change checklist

Before superseding any accepted decision, record:

1. concrete evidence the current choice fails a requirement;
2. alternative and rejected options;
3. impact on invention nucleus/research hypothesis/baseline comparability;
4. data migration/config/state transition and rollback;
5. new threat/failure/split-brain behaviour;
6. API/UI/observability/resource/deployment change;
7. tests and experiment runs invalidated;
8. IP confidentiality/prior-art consequence;
9. owner, reviewer, date, and release boundary.

No new technology is accepted because it is fashionable or makes a diagram look more advanced.

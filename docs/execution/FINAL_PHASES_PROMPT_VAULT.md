# SHLB Final Phases Prompt Vault

This vault contains copy-pasteable execution prompts for the remaining
implementation work. Execute one numbered sub-phase at a time. Each prompt is
intentionally narrow so that the implementation remains reviewable,
reproducible, and safe to stop or roll back.

## Rules of Engagement

- **Foundation gate:** Phase 4.1 must pass in an isolated environment before
  any Phase 8 or Phase 9 implementation begins. The sandbox and AIOps planes
  are presentation layers over the control engine; they must never be used to
  hide a PostgreSQL-coupled or untestable fast path.
- Do not skip sub-phases or combine unrelated sub-phases.
- Do not write mocks, fixtures presented as live telemetry, dummy responses, or
  placeholder handlers.
- Preserve the worker as the sole HAProxy mutation authority.
- Keep the fast path independent of PostgreSQL, Elasticsearch, Logstash, and
  Prometheus. Those systems may receive asynchronous observations, but they
  must not be required to calculate or issue a live attenuation decision.
- Every runtime mutation must use `/var/run/haproxy/admin.sock`, an explicit
  allow-list, bounded timeouts, absolute desired state, and readback
  confirmation.
- Do not add Docker Engine socket access or any privileged container restart
  path.
- Touch only the files named by the current sub-phase unless a test or type
  error proves that one directly coupled file must also change.
- Run the stated verification commands before declaring the sub-phase complete.
- Do not begin the next sub-phase until the current sub-phase has passed.
- Phase 8 controls must call real authenticated APIs that affect real
  Compose-managed demo-backend containers. Browser timers, `setTimeout`,
  fabricated traffic, and client-only fault simulations are prohibited.
- Phase 9 must not introduce LangChain by default. Prefer the smallest
  provider adapter using the native Google GenAI SDK or a direct structured
  HTTP/Pydantic integration. Any dependency addition requires a documented
  footprint and compatibility check.

---

## Phase 4 — Fast-Path Isolation and Deterministic Remediation

### Phase 4.1 — Pure fast-path test boundary

**Copy-paste prompt**

> Act as a Principal Python concurrency engineer. Implement Phase 4.1 of SHLB:
> prove that the EWMA and hysteresis fast path can be imported and tested
> without PostgreSQL, Alembic, Redis, Elasticsearch, Prometheus, or network
> services.
>
> Modify only:
> - `control-api/src/shlb_api/fastpath.py`
> - `control-api/tests/test_fastpath.py`
> - `control-api/pyproject.toml` only if test discovery requires it
>
> Requirements:
> 1. Keep `alpha = 0.3`, three unhealthy observations before attenuation, a
>    33% minimum-capacity reserve, and staged recovery at 25%, 50%, and 100%.
> 2. Make state transitions deterministic for repeated, out-of-order, and
>    duplicate samples; reject negative latency and invalid capacity inputs.
> 3. Ensure importing `fastpath.py` does not import database models, settings
>    that connect to services, or worker startup code.
> 4. Add focused tests for EWMA math, hysteresis, capacity protection, staged
>    recovery, validation errors, and independent keys.
> 5. Do not change the durable action workflow yet.
>
> Definition of done:
> `cd control-api && pytest -q tests/test_fastpath.py` runs without a database
> service and all tests pass. Also run `python -m compileall -q src tests`.

### Phase 4.2 — Fast-path socket adapter contract

**Copy-paste prompt**

> Implement Phase 4.2 for SHLB. Harden the HAProxy Runtime fast-sample
> adapter so it is a bounded, read-only telemetry operation.
>
> Modify only:
> - `control-api/src/shlb_api/worker_io.py`
> - `control-api/tests/test_worker_io.py` or the nearest existing worker I/O
>   test file
> - `control-api/src/shlb_api/fastpath.py` only if a type boundary must be
>   corrected
>
> Requirements:
> 1. Use `asyncio.open_unix_connection()` and an ephemeral open/write/read-to-
>    EOF/close connection. Do not use `socket.socket()` or a persistent
>    interactive session.
> 2. Enforce a 150 ms total `asyncio.wait_for` budget, below the 500 ms
>    observation cadence.
> 3. Parse `show stat` defensively, including missing fields, `-` values, and
>    malformed rows; never convert malformed telemetry into a healthy value.
> 4. Split the `#` header and map by header name; skip `BACKEND` and `FRONTEND`
>    aggregate rows; expose latency, queue, sessions, status, weight, and 5xx counters with
>    explicit nullable/error semantics.
> 5. Keep this adapter read-only. It must not issue `set server` commands.
> 6. Track cumulative counters and discard negative deltas after resets.
> 7. Add tests using mocked asynchronous byte streams, not a live database or
>    HAProxy.
>
> Definition of done:
> Focused worker I/O tests pass, malformed Runtime output is surfaced as
> incomplete evidence, and no database or Elasticsearch import is needed to
> test the parser.

### Phase 4.3 — Durable bridge for fast-path recommendations

**Copy-paste prompt**

> Implement Phase 4.3 for SHLB. Connect fast-path recommendations to the
> existing durable PostgreSQL action/readback workflow without allowing the
> fast path to query or depend on PostgreSQL while calculating a decision.
>
> Modify only:
> - `control-api/src/shlb_api/worker.py`
> - `control-api/src/shlb_api/worker_policy.py`
> - `control-api/tests/test_worker_policy.py`
> - one directly coupled worker test file if required
>
> Requirements:
> 1. The 500ms loop polls HAProxy Runtime and updates in-memory EWMA first.
> 2. A recommendation may enqueue a durable action, but it must be rechecked
>    against the 33% reserve, single-writer lease, incident idempotency key,
>    and current Runtime readback before mutation.
> 3. Preserve PostgreSQL as the blast-radius ledger, not as fast-path
>    telemetry storage.
> 4. Prevent duplicate actions, concurrent conflicting actions, and recovery
>    flapping.
> 5. Emit real lifecycle events for anomaly detection, attenuation,
>    stabilization, and canary recovery; never emit an event for an action
>    that was not acknowledged by HAProxy.
>
> Definition of done:
> Focused policy/worker tests pass; the action is durable before mutation,
> Runtime readback is required after mutation, and a failed readback produces
> `NEEDS_REVIEW` or rollback rather than success.

---

## Phase 5 — Benchmark Measurement and IEEE Figures

### Phase 5.1 — Experiment result schema

**Copy-paste prompt**

> Implement Phase 5.1 for SHLB benchmarking. Define a versioned,
> machine-readable result schema for baseline, uncontrolled gray failure, and
> SHLB-active gray failure runs.
>
> Modify only:
> - `benchmarks/run_experiments.py`
> - `benchmarks/README.md` if it exists, otherwise do not create one
> - `docs/research/IEEE_PAPER_DRAFT.md`
>
> Requirements:
> 1. Record run ID, git/source identifier when available, scenario, start/end
>    times, request count, failure count/rate, mean, p95, p99, throughput,
>    fault activation, first anomaly, first attenuation, stabilization,
>    recovery, MTTD, and MTTR.
> 2. Use only timestamps observed from real API/Runtime/event responses.
> 3. Use explicit nulls with a reason when an event is not observed; never
>    invent zero values.
> 4. Keep baseline, worker-disabled, and worker-enabled runs separate.
> 5. Ensure fault cleanup runs in a `finally` path.
>
> Definition of done:
> `python benchmarks/run_experiments.py --help` works, CSV and JSON output
> have stable headers, and the paper states that results are measurements
> rather than claimed values.

### Phase 5.2 — Matplotlib plotting pipeline

**Copy-paste prompt**

> Implement Phase 5.2 for SHLB. Create the real plotting utility
> `benchmarks/plot_results.py` that reads benchmark CSV output and generates
> publication-ready figures.
>
> Modify only:
> - `benchmarks/plot_results.py`
> - `benchmarks/requirements.txt` if the repository already uses one
> - `docs/research/IEEE_PAPER_DRAFT.md`
>
> Requirements:
> 1. Read the CSV schema emitted by `run_experiments.py`; reject missing
>    required columns with a clear error.
> 2. Generate figures for p95/p99 latency, failure rate, throughput, MTTD, and
>    MTTR, with scenario labels and units.
> 3. Use deterministic styling, accessible colors, vector PDF/SVG output, and
>    no fabricated fallback data.
> 4. Write outputs under `benchmarks/results/` and do not commit generated
>    measurements unless explicitly requested.
> 5. Update the paper with figure references and a reproducible command.
>
> Definition of done:
> `python benchmarks/plot_results.py --help` works; a real CSV produces all
> requested figures; an empty or malformed CSV fails loudly.

### Phase 5.3 — Reproducible evaluation run

**Copy-paste prompt**

> Implement Phase 5.3 for SHLB evaluation operations. Validate the benchmark
> runner against a running Compose stack and document the exact commands
> needed to reproduce the experiment.
>
> Modify only:
> - `benchmarks/run_experiments.py`
> - `benchmarks/plot_results.py`
> - `docs/research/IEEE_PAPER_DRAFT.md`
> - `docs/execution/FINAL_PHASES_PROMPT_VAULT.md` only if a discovered
>   prerequisite must be recorded
>
> Requirements:
> 1. Verify the edge endpoint, fault endpoint, worker state, and cleanup
>    state before each scenario.
> 2. Capture actual control-plane event timestamps for MTTD and MTTR.
> 3. Stop immediately on partial setup; do not label an incomplete run as
>    successful.
> 4. Preserve raw CSV/JSON provenance and report environment limitations.
>
> Definition of done:
> A real run completes all three scenarios or fails with an actionable
> diagnostic. The paper contains no fabricated numerical result.

---

## Phase 6 — Frontend Demonstration and Live Evidence

### Phase 6.1 — Chaos control UX

**Copy-paste prompt**

> Implement Phase 6.1 for the SHLB React frontend. Add a prominent,
> permission-aware “Simulate Gray Failure” control that invokes the existing
> authenticated lab API for `GRAY_FAILURE_INST_A`.
>
> Modify only:
> - `frontend/features/lab/live-fault-lab.tsx`
> - `frontend/lib/api/operations.ts` if the existing mutation contract is
>   insufficient
> - focused frontend tests for the lab screen
>
> Requirements:
> 1. Use the existing API mutation; do not call the demo backend directly.
> 2. Disable the control for read-only users, mobile restrictions, pending
>    requests, and an already-active gray fault.
> 3. Show request, active, clear, expired, and failure states.
> 4. Do not show a state as observed until it comes from the API/SSE data.
> 5. Keep all accessibility labels and keyboard behavior explicit.
>
> Definition of done:
> Typecheck, lint, focused tests, and contract checks pass.

### Phase 6.2 — Decision timeline from real events

**Copy-paste prompt**

> Implement Phase 6.2 for SHLB. Build the autonomous decision timeline from
> real operational summary, decision trace, incident, action, verification,
> and reintegration data.
>
> Modify only:
> - `frontend/features/overview/live-command-center.tsx`
> - `frontend/components/ui.tsx` if a reusable timeline primitive is needed
> - focused frontend tests

> Requirements:
> 1. Render `ANOMALY_DETECTED`, `WEIGHT_ATTENUATED`, `STABILIZED`, and
>    `CANARY_RECOVERY` only when the corresponding server evidence exists.
> 2. Distinguish pending, observed, confirmed, rolled back, and unavailable.
> 3. Never infer successful attenuation from a requested command alone.
> 4. Display event timestamps and freshness.
>
> Definition of done:
> Tests cover healthy, active incident, readback mismatch, rollback, and
> unavailable stream states; no fabricated lifecycle state appears.

### Phase 6.3 — MTTR counter semantics

**Copy-paste prompt**

> Implement Phase 6.3 for SHLB. Add a live MTTR counter that uses durable
> incident and action timestamps, not client render time as the source of
> truth.
>
> Modify only:
> - `frontend/features/overview/live-command-center.tsx`
> - `frontend/features/lab/live-fault-lab.tsx`
> - focused frontend tests

> Requirements:
> 1. While an incident is active, calculate elapsed time from the server
>    incident opening timestamp.
> 2. Once resolved, freeze the displayed MTTR to server-provided resolution
>    timing when available.
> 3. If timestamps are missing or stale, show “Unavailable” or “Stale” rather
>    than zero.
> 4. Use a one-second refresh timer only for display; do not mutate source
>    telemetry.
>
> Definition of done:
> Tests cover active, resolved, stale, clock-skew, and unavailable cases.

---

## Phase 7 — Compose Boot, Security, and Release Gate

### Phase 7.1 — Static configuration gate

**Copy-paste prompt**

> Implement Phase 7.1 for SHLB infrastructure validation. Audit and correct
> only deployment configuration; do not add application features.
>
> Modify only:
> - `docker-compose.yml`
> - `haproxy/haproxy.cfg`
> - `nginx/nginx.conf`
> - `observability/logstash.conf`
> - `README.md` if command/port documentation is stale
>
> Requirements:
> 1. No Docker socket mounts, privileged mode, static service IPs, or public
>    ELK exposure.
> 2. HAProxy uses Docker DNS resolvers for backend service discovery and
>    exposes `/var/run/haproxy/admin.sock`.
> 3. Preserve Elasticsearch and Logstash memory/JVM guardrails.
> 4. Keep host port 8080 reserved and use the documented 8081 edge binding.
> 5. Preserve health checks, dependency ordering, and writable paths required
>    by Elasticsearch/Logstash.
>
> Definition of done:
> `docker compose config --quiet` passes and static searches prove forbidden
> mounts/IPs/exposures are absent.

### Phase 7.2 — Full-stack boot verification

**Copy-paste prompt**

> Implement Phase 7.2 as an operational verification pass for SHLB. Do not
> write new functional code unless a directly observed configuration defect
> requires a minimal fix.
>
> Modify only:
> - configuration files proven defective by the boot test
> - `docs/execution/FINAL_PHASES_PROMPT_VAULT.md` for durable runbook notes
>
> Requirements:
> 1. Start the Compose stack from a clean, documented state.
> 2. Verify PostgreSQL migrations, FastAPI readiness, worker lease,
>    HAProxy socket access, Nginx edge reachability, Prometheus scrape,
>    Logstash ingestion, Elasticsearch health, Kibana reachability, and
>    frontend readiness.
> 3. Confirm the worker can read Runtime state but cannot access Docker Engine.
> 4. Exercise one bounded fault and verify drain/readback/recovery without
>    restarting backend containers.
>
> Definition of done:
> The stack boots cleanly, every readiness check is reproducible, and any
> blocker is documented with the exact failing command and service logs.

### Phase 7.3 — Release evidence bundle

**Copy-paste prompt**

> Implement Phase 7.3 as the final SHLB release-evidence pass. Produce only
> documentation and validation artifacts; do not introduce unverified claims.
>
> Modify only:
> - `docs/research/IEEE_PAPER_DRAFT.md`
> - `docs/research/ALGORITHMIC_INVARIANTS.md`
> - `docs/research/PATENT_DISCLOSURE.md`
> - `docs/execution/PHASED_EXECUTION_PLAN.md`
>
> Requirements:
> 1. Reconcile the paper, invariants, patent disclosure, and execution plan
>    with the implemented behavior.
> 2. Include measured benchmark provenance, limitations, and unexecuted
>    experiments explicitly.
> 3. State the fast-path/slow-path boundary, 33% reserve invariant, EWMA
>    equation, staged recovery, single-writer rule, and readback requirement.
> 4. Do not call the system patentable or production-ready solely because a
>    design document says so; distinguish implemented facts from claims.
>
> Definition of done:
> Documentation contains no stale Scribeplane references, no fabricated
> measurements, and every implementation claim points to a verifiable file or
> command.

---

## Final execution command

After all sub-phases pass, use:

> **Execute Phase 7.3 and prepare the final SHLB release-evidence bundle. Do
> not modify functional code.**

---

## Phase 8 — Interactive Presentation Sandbox

### Phase 8.1 — Sandbox route and boundary

**Copy-paste prompt**

> Act as a Principal Product Engineer implementing Phase 8.1 of SHLB. Build a
> dedicated `/sandbox` Next.js route for the isolated Compose demo-backend
> environment.
>
> Modify only:
> - the smallest existing route file needed for `/sandbox`
> - `frontend/features/lab/live-fault-lab.tsx`
> - `frontend/lib/api/operations.ts` only if an existing typed API hook is
>   insufficient
> - focused frontend tests
>
> Requirements:
> 1. Label the view `Presentation Sandbox` and show the target environment.
> 2. Use the authenticated control API and existing SSE/query contracts; do
>    not call demo containers directly from the browser.
> 3. Keep sandbox actions isolated from customer/BYOO origin groups.
> 4. Show real worker status, Runtime freshness, active fault, target node,
>    expiry, and permission state.
> 5. Do not add fake traffic, fake healing events, or client-side success
>    fallbacks.
>
> Definition of done:
> Typecheck, lint, focused tests, and frontend contract checks pass. A
> read-only user cannot mutate the sandbox.

### Phase 8.2 — Live traffic map and chaos controls

**Copy-paste prompt**

> Implement Phase 8.2 for SHLB's `/sandbox` route. Add three explicit,
> bounded chaos controls targeting only declared demo backends:
> **CPU Spike**, **Memory Leak**, and **Network Latency**.
>
> Modify only:
> - `frontend/features/sandbox/*` or the existing sandbox route components
> - `frontend/lib/api/operations.ts`
> - focused frontend tests
>
> Requirements:
> 1. Map each button to the existing authenticated lab fault contract; if the
>    backend schema does not support a scenario, stop and report the missing
>    contract rather than inventing a request.
> 2. Disable actions during pending requests, mobile restriction, insufficient
>    permissions, incompatible active faults, or stale control-plane data.
> 3. Render a visual traffic map from real route/membership telemetry with
>    clear ready, attenuated, drained, probing, and unavailable states.
> 4. Add animation only to represent observed request/stream updates; never
>    animate fabricated packets or health transitions.
> 5. Make all controls keyboard accessible and explain fault scope/expiry.
>
> Definition of done:
> Focused tests cover each scenario, error cleanup, stale telemetry, and
> read-only access. Typecheck, lint, and contract checks pass.

### Phase 8.3 — MTTR and autonomous timeline

**Copy-paste prompt**

> Implement Phase 8.3 for the SHLB presentation sandbox. Add a live MTTR
> clock and a server-evidence-driven lifecycle timeline.
>
> Modify only:
> - sandbox page/components
> - `frontend/components/ui.tsx` only if a reusable timeline/clock primitive
>   is required
> - focused frontend tests
>
> Requirements:
> 1. Start elapsed time from the server fault/incident timestamp, not button
>    click time when authoritative data is available.
> 2. Freeze MTTR at server-confirmed resolution/reintegration; display
>    `Unavailable` or `Stale` when timestamps are missing.
> 3. Advance only from observed events:
>    `FAULT_APPLIED`, `ANOMALY_DETECTED`, `WEIGHT_ATTENUATED`,
>    `STABILIZED`, `CANARY_RECOVERY`, `FULL_REINTEGRATION`.
> 4. Display rollback and `NEEDS_REVIEW` as terminal safety states.
>
> Definition of done:
> Tests cover active, resolved, stale, rollback, unavailable, and clock-skew
> states. No timeline event is inferred from elapsed browser time.

---

## Phase 9 — AI Root Cause Analysis and Safe LLM Escalation

### Phase 9.1 — Exhausted-capacity trigger and diagnostic contract

**Copy-paste prompt**

> Act as a Principal AI infrastructure engineer implementing Phase 9.1 of
> SHLB. Define the safe, deterministic trigger and typed contract for
> AI-assisted RCA when ordinary remediation is exhausted.
>
> Modify only:
> - `control-api/src/shlb_api/worker_policy.py`
> - `control-api/src/shlb_api/worker.py`
> - `control-api/src/shlb_api/schemas.py`
> - focused backend tests
>
> Requirements:
> 1. Trigger `UNRECOVERABLE_STATE` when healthy capacity is below 33%, the
>    reserve invariant blocks further attenuation, all peers violate policy,
>    or verified rollback cannot restore a safe state.
> 2. Debounce by generation/window/idempotency key; never invoke an LLM per
>    500ms poll.
> 3. Keep the fast path independent of LangChain, LLM APIs, PostgreSQL,
>    Elasticsearch, and Logstash while it calculates ordinary decisions.
> 4. Define a bounded, redacted RCA envelope containing latency EWMA/p95/p99,
>    5xx/timeout rates, HAProxy queue sizes, Runtime state, capacity, semantic
>    signatures, and prior action outcomes.
> 5. The RCA result is advisory. It cannot issue Runtime commands, mutate
>    Docker, mark incidents resolved, or bypass the durable ledger.
>
> Definition of done:
> Unit tests prove trigger/debounce behavior, reserve protection, payload
> redaction/size limits, and no provider call during ordinary healthy or
> attenuable states.

### Phase 9.2 — LangChain/RAG provider adapter

**Copy-paste prompt**

> Implement Phase 9.2 for SHLB. Add a provider-isolated, minimal RAG adapter
> for generating Markdown RCA reports from the validated diagnostic envelope.
>
> Modify only:
> - `control-api/src/shlb_api/aiops.py`
> - dependency manifest/lock file only when strictly required
> - focused adapter tests
>
> Requirements:
> 1. Do **not** add LangChain or a broad agent framework. Prefer the native
>    Google GenAI SDK, or a small direct HTTPS client with Pydantic request and
>    response schemas. Use the smallest dependency footprint that supports the
>    configured provider.
> 2. Use configuration and secret files for the external provider; never
>    hardcode API keys or send secrets in prompts.
> 3. Retrieve only approved SHLB runbooks, invariants, and architecture
>    documents; enforce tenant and incident scope.
> 4. Define a system prompt requiring: incident summary, ranked hypotheses
>    with evidence, confidence, missing evidence, containment options, and
>    next diagnostics in Markdown.
> 5. Validate output size, required headings, and unsafe command-like content.
> 6. Use finite connect/read/token budgets, explicit timeout handling, and
>    `RCA_UNAVAILABLE` on failure. Never silently return a success-shaped
>    fallback.
> 7. Tests must exercise the adapter boundary without contacting an external
>    provider; do not add fake RCA data to production paths.
>
> Definition of done:
> The adapter has a typed input/output contract, rejects invalid output,
> redacts sensitive fields, and fails explicitly when provider configuration
> is absent.

### Phase 9.3 — Durable RCA event and SSE delivery

**Copy-paste prompt**

> Implement Phase 9.3 for SHLB. Persist and stream validated RCA lifecycle
> events without granting the AI adapter mutation authority.
>
> Modify only:
> - `control-api/src/shlb_api/worker.py`
> - existing event/SSE API module
> - the smallest required persistence migration/model file
> - focused backend tests
>
> Requirements:
> 1. Persist request, provider status, report hash, report content or approved
>    object reference, timestamps, and incident/action correlation.
> 2. Emit `rca_started`, `rca_report`, and `rca_unavailable` through the
>    existing SSE mechanism with tenant/environment scope.
> 3. Ensure duplicate delivery is idempotent and reports are ordered by
>    durable sequence.
> 4. Keep PostgreSQL authoritative for lifecycle state; Elasticsearch remains
>    forensic input only.
> 5. Do not expose provider credentials or unrestricted raw logs to the
>    frontend.
>
> Definition of done:
> Tests cover timeout, duplicate trigger, invalid report, reconnect/replay,
> and unavailable provider behavior. A streamed report cannot transition an
> incident to resolved.

### Phase 9.4 — RCA Markdown dashboard

**Copy-paste prompt**

> Implement Phase 9.4 for SHLB. Add a safe Markdown RCA renderer to the
> React dashboard and connect it to the real `rca_report` SSE event.
>
> Modify only:
> - `frontend/features/overview/live-command-center.tsx`
> - a focused `frontend/components/rca-report.tsx`
> - existing SSE/API typing file
> - focused frontend tests
>
> Requirements:
> 1. Render headings, evidence tables, confidence, limitations, and next
>    diagnostics from the validated report.
> 2. Sanitize Markdown/HTML and never execute links, scripts, or commands from
>    model output.
> 3. Show `RCA_PENDING`, `RCA_UNAVAILABLE`, stale, and provider-error states
>    explicitly; do not show empty content as a successful report.
> 4. Preserve incident/action IDs and report timestamp for auditability.
> 5. Label the report `AI advisory` and provide the deterministic evidence
>    trace beside it.
>
> Definition of done:
> Typecheck, lint, unit tests, contract checks, and production build pass.
> Tests cover sanitized Markdown, malformed reports, reconnect replay, and
> provider unavailability.

### Phase 9.5 — AI safety and evaluation gate

**Copy-paste prompt**

> Implement Phase 9.5 as a documentation and validation pass for SHLB's AI
> diagnostic plane. Do not add autonomous model-driven remediation.
>
> Modify only:
> - `docs/architecture/HLD.md`
> - `docs/architecture/LLD.md`
> - `docs/research/ALGORITHMIC_INVARIANTS.md`
> - `docs/research/IEEE_PAPER_DRAFT.md`
> - focused evaluation documentation if already present
>
> Requirements:
> 1. Document the exhausted-capacity trigger, diagnostic envelope, retrieval
>    boundary, provider failure behavior, and advisory-only constraint.
> 2. Define evaluation metrics: trigger precision, report latency, evidence
>    citation coverage, unsafe recommendation rate, and operator acceptance.
> 3. Separate measured results from hypotheses and disclose provider/model
>    version, prompt version, and data-retention assumptions.
> 4. Do not claim the LLM improves remediation unless reproducible experiments
>    provide evidence.
>
> Definition of done:
> The docs agree with the implementation, contain no fabricated AI metrics,
> and explicitly state that HAProxy mutation remains deterministic and
> ledger-controlled.

## Updated final execution command

After Phases 8 and 9 pass, use:

> **Execute Phase 9.5 and prepare the final SHLB architecture, AI-safety, and
> presentation-evidence bundle. Do not modify functional code unless a
> documented validation defect requires it.**

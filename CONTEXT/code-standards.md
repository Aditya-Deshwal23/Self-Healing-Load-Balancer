# Code Standards

## General

- Keep modules small and single-purpose — `worker_policy.py` and
  `fastpath.py` have zero runtime dependencies and full type hints;
  hold new domain modules to that bar
- Fix root causes, not workarounds — e.g. the `classify()`
  generalization removed hardcoded topology constants rather than
  special-casing around them
- Do not mix unrelated concerns in one component, route, or module

## Python

- Strict typing throughout `shlb_api`
- Pydantic models for all FastAPI request/response validation in
  `routers/*.py`
- ML/statistical feature extraction stays pure functions: input
  dict → output dict, no I/O, no DB session, no HAProxy/Prometheus
  client inside them — this is what makes `classify()` and
  `FastPathController` trivially unit-testable without the full
  Postgres/Redis stack running; new modules (e.g. a future
  `feature_extraction.py`) must follow the same pattern
- No hardcoded route/instance/topology constants outside
  `worker_policy.py`'s `ROUTES`/`INSTANCES`/`LAB_POLICY` — do not
  reintroduce what Phase 1 just removed

## Next.js / TypeScript

- Strict mode (`strict: true`) throughout
- Server components by default in `frontend/app`; add `"use client"`
  only where interactivity (command palette, live matrix hover, SSE
  subscriptions) requires it
- Data fetching through TanStack Query via `frontend/lib/api`, not
  ad hoc `fetch` calls scattered through components
- Feature folders under `frontend/features/` each own their
  components and queries — don't reach across feature boundaries

## Styling

- No CSS framework — style with the existing semantic class
  pattern in `frontend/app/globals.css` (e.g. `.panel`, `.button`,
  `.status-tag`) plus the CSS custom-property tokens in
  `ui-context.md`. Do not introduce Tailwind, a component library
  (shadcn/ui or otherwise), or inline hardcoded hex values
- Reference tokens by name (`var(--accent-copper)`, etc.) so
  light/dark both stay correct automatically via `[data-theme]`
- Follow the border-radius scale defined in `ui-context.md`

## API Routes

- Validate and parse request input via Pydantic before any logic
  runs
- Enforce the session/auth dependency before any mutation
- **Hard invariant**: no handler in `routers/*.py` may itself run
  the `classify()`/actuation loop or write to the HAProxy Runtime
  socket. That authority belongs solely to `ControlWorker.tick()`
  running under the Redis lease. A handler may read state or write
  an intent record (e.g. a `LabFault` row) for the worker to act on
  next tick — never mutate HAProxy directly. This is the coding-rule
  form of the single-writer invariant in `architecture.md`
- Return consistent, predictable response shapes — follow the
  existing list/detail parity pattern in `routers/operations.py`

## Data and Storage

- Structural/evidentiary data belongs in PostgreSQL.
  `Classification.evidence_support` and
  `EvidenceCertificate.scope_evidence` are JSON columns — prefer
  extending these for lab-scale additions (like the shadow signal)
  over adding new tables; add a real migration only when you need to
  query or filter on a field, not merely store it
- Coordination/session-only data belongs in Redis; never treat it as
  durable history
- No large binary/blob storage layer exists yet — don't put raw
  benchmark artifacts or packet captures directly in a Postgres JSON
  column; raise it as an open question first

## File Organization

- `control-api/src/shlb_api/routers/` — one file per resource group
  (`auth`, `projects`, `registry`, `operations`, `system`, `events`)
- `control-api/src/shlb_api/` (root) — worker/domain logic:
  `worker.py`, `worker_policy.py`, `fastpath.py`, `worker_io.py`,
  `models.py`, `contracts.py`
- `control-api/tests/` — one test file per module under test;
  safety-critical modules (`worker_policy.py`, `fastpath.py`) get the
  tightest coverage
- `frontend/features/<feature>/` — one folder per IA section
  (`overview`, `actions`, `incidents`, `lab`, `traffic`, `system`,
  `recovery`)
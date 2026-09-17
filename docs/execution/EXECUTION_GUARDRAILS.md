# SHLB Execution Guardrails

This file is a mandatory gate for all future implementation sessions.

## Foundation before presentation

Do not begin Phase 8 (Interactive Presentation Sandbox) or Phase 9 (AI RCA)
until Phase 4.1 has passed independently. The fast path is the transmission
for every later feature: it must be importable and testable without
PostgreSQL, Alembic, Redis, Elasticsearch, Prometheus, or network services.
Adding a polished sandbox or AI report before that proof would create a
presentation shell around an unverified control engine.

The required gate is:

```text
cd control-api
pytest -q tests/test_fastpath.py
python -m compileall -q src tests
```

The first command must run without starting PostgreSQL or any other service.
If it cannot, the work remains in Phase 4.1 regardless of frontend or AI
readiness.

## AI dependency boundary

Phase 9 must not pull in LangChain by default. LangChain's transitive
dependency footprint is disproportionate for this lightweight control-plane
container and increases compatibility and supply-chain risk. The preferred
implementation is the native Google GenAI SDK; the acceptable fallback is a
small direct HTTPS client with strict Pydantic request/response schemas.
Provider calls are bounded, redacted, advisory-only, and never receive
mutation authority.

Any proposed dependency must document its version, transitive footprint,
container impact, license, and why the native SDK or direct HTTP option is
insufficient before it can be introduced.

## Real container demonstration

Phase 8 is a real integration demonstration, not a browser animation. Each
chaos control must issue an authenticated request to the control API, which
must apply a bounded fault to an actual Compose-managed `demo-backend`
container over the internal network. The browser must not use `setTimeout()`,
local state, fabricated packets, or synthetic health transitions as a
substitute for the fault.

An examiner must be able to inspect the browser Network panel and observe the
real request, then correlate the response with demo-backend logs, HAProxy
Runtime samples, durable worker events, and the displayed MTTR. If any
required backend fault contract is unavailable, stop and report the missing
contract instead of implementing a fake sandbox.

## Order of execution

The enforced order is:

```text
Phase 4.1 -> Phase 4.2 -> Phase 4.3
          -> Phase 5 -> Phase 6 -> Phase 7
          -> Phase 8 -> Phase 9
```

No phase may claim completion from documentation alone. Each phase must pass
its own reproducible definition of done and preserve the safety invariants
above.

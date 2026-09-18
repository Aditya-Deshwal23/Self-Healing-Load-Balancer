Archived: out of scope for the current single-environment lab prototype and the Phase 1 rule-only implementation (see CONTEXT/project-overview.md and CONTEXT/architecture.md). Kept for historical reference only.

# Execution Prompt Vault

## Runtime hardening

> Execute Phase 1A. Inspect the current Compose and proxy files, implement only
> the stated security boundary, run the exact verification commands, and report
> any environment blocker without weakening the invariant.

## Durable protocol

> Execute Phase 2A. Implement a real IndexedDB outbox and durable-ack contract.
> Redis receipt must never evict local state. Add failure-injection tests before
> changing protocol semantics.

## Research evaluation

> Execute Phase 3B. Build a reproducible benchmark against real proxy/runtime
> endpoints. Report raw observations, confidence intervals, and limitations;
> do not fabricate healthy or failure data.

# Self-Healing Load Balancer (EBMSH)

## Overview

A self-healing traffic orchestrator that detects and quarantines
route×instance-scoped failures — including "gray" failures that
pass standard health probes but degrade latency or error rate —
using Evidence-Bounded Minimum-Scope Healing (EBMSH). A
deterministic rule engine is the sole actuation authority; an
optional statistical/ML signal runs alongside it in HYBRID_SHADOW
mode, logging what it would flag without ever mutating traffic.
Built as an Innovative Product Development showcase and an
IEEE-track research prototype, deployable locally via Docker
Compose without cloud infrastructure.

## Goals

1. Detect and safely quarantine failures at the narrowest scope
   the evidence supports — a single route×instance cell — never
   a broader blast radius than the data justifies.
2. Prove empirically that a hybrid statistical signal reduces
   Mean Time to Detect (MTTD) for gray failures the deterministic
   rules structurally cannot see yet (error rate below the hard
   threshold), without increasing the false-action rate above the
   promotion gate defined in `docs/design/20_RISK_REGISTER_AND_DECISION_LOG.md`.
3. Ship a fully explainable, replayable reference implementation:
   every action traceable through a Fingerprint → Classification →
   EvidenceCertificate hash chain, suitable as an IEEE submission's
   reproducibility package.

## Core User Flow

1. Operator authenticates (session-cookie login) and lands on the
   Command Center.
2. Observes live route×instance evidence — HAProxy Runtime state,
   Prometheus rates/latency — via the Route × Instance Matrix.
3. The control-worker (sole HAProxy writer, holding a Redis
   coordination lease) ticks on a fixed interval: the deterministic
   rule engine (`classify()`) evaluates every cell; the HYBRID_SHADOW
   statistical signal evaluates alongside it and is attached to the
   decision as advisory evidence only.
4. On an actionable classification (`ROUTE_INSTANCE_FAILURE` or
   `INSTANCE_DOWN`), the worker prepares, applies, and reads back a
   HAProxy Runtime change, then dual-verifies (symptom relief +
   preserved capacity) before committing.
5. The operator inspects the Incident's Decision Trace — showing
   deterministic evidence and the shadow signal side by side — and
   watches staged reintegration once the underlying condition clears.

## Features

### Evidence-Bounded Healing
- Deterministic per-cell rule engine over the full route×instance
  topology (no hardcoded flagship scenario)
- Capacity-floor safety gates (`route_instance_capacity`,
  `instance_capacity`) required before any actuation
- HYBRID_SHADOW statistical signal (EWMA-based) logged on every
  decision, structurally unable to change `final_class`/`actionable`

### Explainability & Research Instrumentation
- Fingerprint / Classification / EvidenceCertificate hash chain for
  deterministic, replayable decisions
- Decision Trace UI exposing rule evidence, competing hypotheses,
  and the shadow signal for the same window
- Fault Lab for reproducible, bounded fault injection
- Baseline/ablation experiment harness (B1–B4) for the IEEE
  evaluation plan

## Scope

### In Scope
- Single-environment lab prototype: 4 logical routes, 3 physical
  demo backend instances
- The full EBMSH transaction: evidence → classification → capacity
  gate → action → verification → reintegration
- HYBRID_SHADOW statistical augmentation and its ablation study

### Out of Scope
- Multi-region/multi-cluster operation, Kubernetes, production
  autoscaling
- Deep learning, reinforcement learning, or bandit-based routing
  (explicitly rejected in `docs/design/09` and the decision log)
- Promotion of the statistical signal to `HYBRID_ACTIVE` (requires
  the full ADR-gated calibration/shadow-validation process — not a
  Phase 1 goal)

## Success Criteria

1. `classify()` correctly and safely resolves both hard and
   generalized (non-flagship) fault scenarios end to end, verified
   by the `control-api` test suite.
2. The HYBRID_SHADOW signal is persisted (`ObservationWindow.metrics`,
   `Classification.evidence_support`) without ever influencing
   `decision.final_class` or `decision.actionable` — verified by a
   dedicated safety test, not just code review.
3. `benchmarks/run_experiments.py` produces a real B1–B4 comparison
   CSV, and an MTTD_shadow-vs-MTTD_rules extraction returns
   non-fabricated numbers for at least one injected gray-fault run.
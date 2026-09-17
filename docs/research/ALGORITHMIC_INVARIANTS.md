# SHLB Research Invariants and Proof Sketches

## Evidence-window convergence

For each route/instance tuple, SHLB joins metrics, HAProxy runtime counters,
and semantic logs by an observation-window identifier. Late evidence is
discarded from the active decision once the window is sealed, but retained in
the ledger for audit. Thus a retry cannot silently combine measurements from
different windows.

## Decision complexity

For `R` routes, `N` instances, and `E` evidence records in a window, indexed
aggregation is `O(E + R*N)` time and `O(R*N + E)` bounded memory before
retention. Candidate mutation selection is `O(R*N)` and readback is `O(1)`
per affected membership. The implementation must enforce caps on `E` and
window duration.

## Dynamic latency baseline

The fast path does not use a global latency threshold. For each route/instance
key it maintains two independent exponentially weighted moving averages:

```text
current_t  = 0.30 * sample_t + 0.70 * current_(t-1)
baseline_t  = 0.05 * sample_t + 0.95 * baseline_(t-1)
```

Both averages initialize from the first finite, non-negative sample. A latency
anomaly exists only when:

```text
sample_count >= 20
AND current_t > 2.5 * baseline_t
AND (current_t - baseline_t) > 15 ms
```

An error-rate signal may independently classify a sample as unhealthy when its
configured rate is reached, but it is also gated by the 20-sample probation
period. No latency or error anomaly can trigger during probation. Three
consecutive unhealthy observations are required after probation before an
attenuation recommendation. Any healthy observation resets the unhealthy
streak, so the detection bound depends on the polling cadence and request
observations rather than on wall-clock ticks alone.

For polling interval `P`, consecutive unhealthy requirement `K`, and EWMA
settling time `T_settle`, the practical detection bound is:

```text
T_detect <= P + T_settle + (K - 1) * P
```

This is a derived bound, not a claim of universally sub-second detection.

## Safety proof sketch

An automatic mutation is permitted only if: (1) evidence completeness is above
the configured threshold, (2) the classification is not `UNKNOWN`, (3) the
affected membership is allow-listed, (4) peer capacity remains safe, and (5)
the PostgreSQL action ledger records `PREPARED`. Therefore incomplete or
conflicting evidence cannot directly cause attenuation.

## Recovery invariant

Reintegration is monotonic through explicit stages. A node cannot skip a
canary stage, and full weight is restored only after synthetic probes,
runtime readback, and route-level success evidence pass. A failed stage leaves
the node drained and creates a durable audit event.

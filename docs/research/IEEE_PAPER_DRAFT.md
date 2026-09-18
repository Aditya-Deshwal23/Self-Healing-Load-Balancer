# SHLB: Autonomous Gray-Failure Detection and Adaptive Attenuation in Modern L7 Reverse Proxies

## Abstract

Gray failures are partial service degradations that evade binary health checks
while damaging tail latency and reliability. SHLB separates a low-latency
fast path based on HAProxy Runtime statistics from a slower forensic ELK path.
A dual-EWMA relative-deviation detector, hysteresis, a 33% minimum capacity
reserve, and staged recovery attenuate affected memberships without proxy
reloads. The included benchmark runner records real client latency and failure
outcomes from the Compose deployment. Results are reported as measured CSV
observations rather than predetermined claims.

## I. Introduction

Modern microservice fleets expose failure modes between healthy and unavailable:
queue growth, long-tail latency, and intermittent application errors. Passive
TCP checks and binary HTTP checks often remain green. SHLB treats these gray
signals as a scoped control problem. It combines proxy-local observations,
application metrics, and direct probes while keeping the mutation authority in
one audited worker.

## II. Related Work and Prior Art

Huang et al. identify gray failures as a distinct cloud-scale reliability
problem in “Gray Failure: The Achilles’ Heel of Cloud-Scale Systems” (HotOS
2017). Their work establishes the motivation for detecting partial failures
that evade binary liveness checks; SHLB does not claim that problem as novel.
Hayashibara et al.’s φ accrual failure detector (2004) demonstrates adaptive
failure suspicion based on observed inter-arrival behavior and motivates
relative, history-aware detection rather than one static threshold.

Envoy adaptive concurrency and Netflix concurrency limits regulate outstanding
work, while HAProxy agent checks provide external health signals. These
approaches are valuable and may offer stronger integrated control in
Envoy-based deployments. SHLB does not claim its dual-EWMA mathematics is
superior to Envoy. Its contribution is operational: a low-footprint,
out-of-band overlay that applies adaptive attenuation to legacy or stock
HAProxy/Nginx deployments without requiring an Envoy sidecar migration.

## III. System Architecture

Nginx terminates local TLS and serves the dashboard. HAProxy performs routing,
health checks, metrics export, and runtime weight/drain changes through
`admin.sock`. The FastAPI API provides authenticated durable resources.
A single worker owns the PostgreSQL advisory lock, reads Runtime statistics,
and commits action intent before mutation. Prometheus supplies time-series
evidence; Logstash and Elasticsearch retain forensic logs asynchronously.

## IV. Mathematical Model and Algorithm

For instance `i`, SHLB maintains a fast current EWMA and a slow baseline:

`C_i(t) = 0.30 * L_i(t) + 0.70 * C_i(t-1)`

`B_i(t) = 0.05 * L_i(t) + 0.95 * B_i(t-1)`

Latency is anomalous when:

`sample_count >= 20`, `C_i(t) > 2.5 * B_i(t)`, and
`C_i(t) - B_i(t) > 15 ms`.

The first 20 samples are a probation period, preventing cold-start penalties.
After probation, an unhealthy candidate requires three consecutive
observations rather than one sample. A configured error-rate signal may
independently qualify a sample after probation.
The safety predicate rejects attenuation if the resulting eligible capacity
falls below 67% of physical capacity. Recovery advances through 25%, 50%, and
100% only after a cooldown and repeated healthy observations. Runtime readback
and the PostgreSQL action ledger remain mandatory; EWMA is a recommendation
signal, not an authority bypass.

If `P` is the polling period, `T_settle` is the dual-EWMA settling time, and
`K` is the unhealthy observation count, the practical detection bound is:

`T_detect <= P + T_settle + (K - 1) * P`

This is a derived engineering bound, not a universal sub-second claim.

## V. Empirical Evaluation and Benchmarking

Run the real lab first, then:

```sh
python3 benchmarks/run_experiments.py --base-url https://localhost:8443
```

The runner emits `benchmarks/results.csv` with request count, failure rate,
mean, p95, and p99 latency. For publication, execute three controlled runs:
round-robin baseline, gray-failure injection on `demo-backend-a`, and the same
injection with the fast-path controller enabled. Record MTTD as the first
durable anomaly event minus fault activation, and MTTR as the first confirmed
attenuation/readback event minus activation. Report median and 95% confidence
interval over independent runs.

> **📍 IMPLEMENTATION STATUS (2026-09-18):** As of Phase 1 (complete), the
> HYBRID_SHADOW fast-path EWMA signal is wired into the worker pipeline and
> records `shadow_statistical_signal` in every `Classification.evidence_support`
> payload — the signal is advisory-only and verified never to change
> `final_class` or `actionable`. The `benchmarks/run_experiments.py` script
> currently runs the round-robin, gray-failure-without-SHLB, and
> gray-failure-with-SHLB scenarios; the required B1–B4 baseline ablation runs
> have not been implemented or executed against the live Compose stack. The
> schema-based MTTD extraction is available in
> `benchmarks/extract_mttd_shadow_vs_rules.sql`, but no empirical result exists
> yet because the Compose services are not healthy. The query reads the
> pre-incident `fast_path_recommendations` persisted in observation-window
> metrics. `experiments/manifest.json` has not yet been created.

No empirical number is asserted in this draft until the CSV is generated from
the target hardware and software versions.

## VI. Conclusion and Future Scope

SHLB demonstrates a defensible separation between low-latency remediation and
high-fidelity forensic retention. Future work includes a continuous PID
controller, CUSUM or Page-Hinkley change-point detection, multi-node
controller failover, eBPF queue attribution, and asynchronous bounded action
queues to mitigate PostgreSQL write-storms. Any extension must preserve the
single-writer ledger, capacity reserve, readback, and staged recovery
invariants.

# SHLB Patent-Style Disclosure Outline

## Working title

Evidence-bounded reversible traffic attenuation with forensic triangulation,
blast-radius accounting, and canary re-attestation.

## Novelty candidates

1. A controller that joins proxy runtime counters, semantic log evidence, and
   application probes into a quorum before changing one route membership.
2. A dual-EWMA relative-deviation detector that adapts to each
   route/instance latency baseline instead of applying one global
   millisecond threshold, combined with volume-aware evidence windows.
3. A PostgreSQL action ledger that makes runtime mutation and readback a
   recoverable transaction protocol without reloading the proxy.
4. A canary reintegration schedule whose advancement requires both synthetic
   traffic evidence and runtime state alignment.
5. A blast-radius ledger that counts physical capacity once while representing
   multiple logical route memberships, preventing cascading drain decisions.

## Prior-art boundary and claim discipline

Gray-failure detection is established prior art, including Huang et al.,
“Gray Failure: The Achilles’ Heel of Cloud-Scale Systems” (HotOS 2017).
Failure-detector adaptation is also established by Hayashibara et al.,
“The φ Accrual Failure Detector” (2004). Envoy and related proxies provide
adaptive concurrency and outlier controls. SHLB must therefore avoid claiming
invention of gray-failure detection, EWMA smoothing, adaptive concurrency, or
proxy outlier ejection in isolation.

The defensible contribution is the operational composition: an out-of-band
overlay for stock HAProxy/Nginx, relative dual-EWMA attenuation, physical
capacity accounting across logical memberships, a durable prepare/command/
readback protocol, and probe-gated reintegration. Counsel must validate every
claim against the cited prior art.

## Claim drafting constraints

The claims should be narrowed to observable protocol steps and invariants, not
generic “AI self-healing.” Experimental evaluation must report false-positive
attenuation, recovery latency, active-connection preservation, blast-radius
violations, and canary rollback rate. Patent counsel must perform a prior-art
search before filing; this outline is an engineering disclosure, not legal
search before filing; this outline is an engineering disclosure, not legal
advice. Future technical scope includes continuous PID control, CUSUM or
Page-Hinkley change-point detection, and asynchronous action-event queues to
mitigate PostgreSQL write storms.

# SHLB Interactive Presentation Sandbox

## Purpose and boundary

Presentation Sandbox is a controlled, self-contained mode for demonstrating
SHLB behavior without requiring an external client integration. It targets
only the Compose-managed `demo-backend` pool and uses the same FastAPI,
worker, HAProxy Runtime socket, PostgreSQL ledger, and SSE event stream as the
normal system. It is not a simulator: traffic, faults, Runtime state, and
healing events come from live services.

The sandbox must be visibly labelled in the UI and must never share customer
origin registrations, credentials, or routing groups. A sandbox fault is
scoped by environment, target instance, scenario, duration, and a durable
ground-truth identifier.

## Presenter flow

1. The presenter opens `/sandbox` and selects **Presentation Sandbox**.
2. The frontend loads the current demo environment, node memberships, worker
   status, Runtime freshness, and active fault state.
3. The presenter starts bounded traffic generation through the authenticated
   control API. The traffic map visualizes observed request flow; it does not
   display client-side fake packets.
4. The presenter chooses one chaos action:
   - **CPU Spike**: apply bounded CPU pressure to the selected demo backend;
   - **Memory Leak**: apply bounded, expiring memory pressure;
   - **Network Latency**: add controlled request delay and optional errors.
5. The control API records the fault request. The worker applies it to the
   declared demo target through the existing lab adapter and records
   `lab_fault_applied`.
6. HAProxy Runtime samples feed the fast EWMA path. If policy thresholds and
   hysteresis are met, the worker attenuates the affected membership and
   publishes a readback-confirmed event.
7. The dashboard displays the timeline:
   `FAULT_APPLIED -> ANOMALY_DETECTED -> WEIGHT_ATTENUATED ->
   STABILIZED -> CANARY_RECOVERY -> FULL_REINTEGRATION`.
8. The presenter clears the fault or waits for expiry. Recovery proceeds only
   through probe-gated stages and the UI freezes MTTR using server timestamps
   when the incident resolves.

## Visual model

The sandbox view contains four synchronized surfaces:

| Surface | Live source | Presentation purpose |
|---|---|---|
| traffic map | Runtime membership and observed request metrics | show eligible, attenuated, drained, and recovering nodes |
| chaos controls | authenticated lab API | make fault scope and expiry explicit |
| decision timeline | SSE plus decision trace | show only server-confirmed lifecycle transitions |
| MTTR clock | incident/action timestamps | show detection-to-confirmed-recovery duration |

Unavailable or stale streams are shown as unavailable. The frontend never
turns a missing event into a green status and never advances a timeline based
on elapsed browser time alone.

## Isolation and security

- The route is protected by the same frontend session and role checks as the
  existing lab surface.
- Fault creation, clearing, and target selection are validated by FastAPI.
- The demo backend accepts only the internal lab authorization path.
- No browser receives the HAProxy admin socket, Docker socket, database
  credentials, or provider API keys.
- Fault duration is bounded and cleanup is idempotent.
- A sandbox incident cannot mutate a customer BYOO origin.

## Research and demo evidence

Each demonstration should preserve the event stream, Runtime snapshots, action
IDs, and benchmark result ID. A presentation can therefore be replayed as an
auditable experiment: fault activation, first qualifying anomaly, attenuation
acknowledgement, stabilization, and canary recovery all have server-side
timestamps.

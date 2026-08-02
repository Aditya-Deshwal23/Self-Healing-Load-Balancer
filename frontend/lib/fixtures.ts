import type {
  ActionLifecycle,
  FailureClass,
  InstanceFixture,
  MatrixCellData,
  RouteFixture,
  TimePoint,
  TraceStage,
} from "@/lib/types";

export const demoMeta = {
  fixture: true,
  generatedAt: "2026-07-21T16:39:42.000Z",
  displayTime: "21 Jul 2026 · 22:09 IST",
  timezone: "Asia/Kolkata (UTC+05:30)",
  evidenceWindow: "21:54–22:09 IST",
  eventCursor: "fixture-evt-20491",
  apiAvailable: false,
  sseAvailable: false,
  labCapability: true,
};

export const environments = [
  {
    id: "lab-local",
    label: "Local traffic lab",
    kind: "LAB",
    mode: "RULES_ONLY",
    safeMode: false,
  },
  {
    id: "recovery-drill",
    label: "Recovery drill",
    kind: "PILOT",
    mode: "SAFE_MODE",
    safeMode: true,
    reason: "Redis coordination unavailable during recovery rehearsal",
    startedAt: "21 Jul · 21:47 IST",
    suppressedActions: 4,
    lastKnownGood: "generation 184 · config 7bf5c57e",
  },
] as const;

export const routes: RouteFixture[] = [
  { id: "public", label: "/public", backend: "be_public", criticality: "standard", requestsPerSecond: 48.2, retryPolicy: "safe GET · max 1" },
  { id: "auth", label: "/auth", backend: "be_auth", criticality: "high", requestsPerSecond: 31.6, retryPolicy: "connection only · max 1" },
  { id: "catalog", label: "/catalog", backend: "be_catalog", criticality: "standard", requestsPerSecond: 57.8, retryPolicy: "safe GET · max 1" },
  { id: "checkout", label: "/checkout", backend: "be_checkout", criticality: "critical", requestsPerSecond: 22.4, retryPolicy: "suppressed · ambiguous POST" },
  { id: "recommendations", label: "/recommendations", backend: "be_recommendations", criticality: "standard", requestsPerSecond: 8.7, retryPolicy: "safe GET · max 1" },
];

export const instances: InstanceFixture[] = [
  { id: "inst-a", label: "Backend A", server: "srv_inst_a", version: "demo-v1", capacity: 100, utilization: 62, addressAlias: "backend-a.internal:8080", probe: "passing", lastTrafficSeconds: 1 },
  { id: "inst-b", label: "Backend B", server: "srv_inst_b", version: "demo-v1", capacity: 100, utilization: 54, addressAlias: "backend-b.internal:8080", probe: "degraded", lastTrafficSeconds: 2 },
  { id: "inst-c", label: "Backend C", server: "srv_inst_c", version: "demo-v2", capacity: 100, utilization: 71, addressAlias: "backend-c.internal:8080", probe: "unknown", lastTrafficSeconds: 4 },
];

function cell(
  routeId: string,
  instanceId: string,
  overrides: Partial<MatrixCellData> = {},
): MatrixCellData {
  return {
    routeId,
    instanceId,
    state: "healthy",
    desired: { admin: "ready", weight: 100 },
    observed: { admin: "ready", weight: 100 },
    effectiveWeight: 100,
    errorRate: 0.3,
    p95Ms: 118,
    sampleCount: 842,
    freshnessSeconds: 3,
    evidence: "complete",
    deviation: "within peers",
    note: "Observed state matches durable intent. Route and peer evidence are within the configured range.",
    ...overrides,
  };
}

export const matrixCells: MatrixCellData[] = [
  cell("public", "inst-a", { errorRate: 0.2, p95Ms: 82, sampleCount: 1068 }),
  cell("public", "inst-b", { errorRate: 0.3, p95Ms: 86, sampleCount: 991, deviation: "p95 +1.8%" }),
  cell("public", "inst-c", { errorRate: 0.2, p95Ms: 84, sampleCount: 1012 }),
  cell("auth", "inst-a", { errorRate: 0.7, p95Ms: 138, sampleCount: 734 }),
  cell("auth", "inst-b", { errorRate: 0.8, p95Ms: 141, sampleCount: 698, deviation: "success −0.1 pp" }),
  cell("auth", "inst-c", {
    state: "unknown",
    errorRate: null,
    p95Ms: null,
    sampleCount: 0,
    freshnessSeconds: 94,
    evidence: "stale",
    deviation: "telemetry stale",
    note: "HAProxy state is readable, but route telemetry is 94 seconds old. Result is unknown, not healthy.",
  }),
  cell("catalog", "inst-a", { errorRate: 0.4, p95Ms: 109, sampleCount: 1282 }),
  cell("catalog", "inst-b", { errorRate: 0.5, p95Ms: 113, sampleCount: 1198, deviation: "p95 +3.7%" }),
  cell("catalog", "inst-c", {
    state: "reintegrating",
    desired: { admin: "ready", weight: 20 },
    observed: { admin: "ready", weight: 5 },
    effectiveWeight: 5,
    errorRate: 0.6,
    p95Ms: 127,
    sampleCount: 86,
    freshnessSeconds: 5,
    evidence: "partial",
    deviation: "requested 20 · observed 5",
    marker: "drift",
    note: "The configured reintegration stage is 20%, but HAProxy readback remains at weight 5. This is drift, not success.",
  }),
  cell("checkout", "inst-a", { errorRate: 2.9, p95Ms: 312, sampleCount: 481, deviation: "peer control" }),
  cell("checkout", "inst-b", {
    state: "quarantined",
    desired: { admin: "drain", weight: 0 },
    observed: { admin: "drain", weight: 0 },
    effectiveWeight: 0,
    errorRate: 18.2,
    p95Ms: 824,
    sampleCount: 428,
    freshnessSeconds: 2,
    evidence: "complete",
    deviation: "errors 6.1× peers",
    marker: "quarantine",
    incidentId: "inc-1042",
    note: "Only checkout on Backend B is quarantined. Public, auth, and catalog memberships on the same physical instance remain eligible.",
  }),
  cell("checkout", "inst-c", { errorRate: 3.2, p95Ms: 326, sampleCount: 452, deviation: "peer control" }),
  cell("recommendations", "inst-a", { errorRate: 0.5, p95Ms: 176, sampleCount: 214 }),
  cell("recommendations", "inst-b", { errorRate: 0.6, p95Ms: 182, sampleCount: 198 }),
  cell("recommendations", "inst-c", {
    state: "no-membership",
    desired: { admin: "none", weight: null },
    observed: { admin: "none", weight: null },
    effectiveWeight: null,
    errorRate: null,
    p95Ms: null,
    sampleCount: 0,
    freshnessSeconds: null,
    evidence: "missing",
    deviation: "not in pool",
    note: "Backend C is not registered in the recommendations pool. This is topology, not missing telemetry.",
  }),
];

export const operationalSummary = [
  { label: "Environment", value: "Guarded", detail: "1 route-local quarantine", state: "warning" },
  { label: "Route-eligible capacity", value: "83%", detail: "checkout 67% · fleet 300 units", state: "neutral" },
  { label: "Open incidents", value: "2", detail: "1 requires review", state: "danger" },
  { label: "Active quarantine", value: "1", detail: "1 of 15 memberships", state: "warning" },
  { label: "Verification", value: "1", detail: "124 samples remaining", state: "neutral" },
  { label: "Control loop", value: "4 s", detail: "last confirmed · fixture", state: "muted" },
] as const;

export const classDescriptions: Record<FailureClass, { plain: string; action: string }> = {
  HEALTHY: { plain: "Fresh evidence supports normal behavior.", action: "No healing change." },
  INSTANCE_DOWN: { plain: "Hard failure spans an instance's memberships.", action: "Complete-instance drain if physical reserve remains safe." },
  INSTANCE_DEGRADED: { plain: "Peer-relative degradation spans routes on one instance.", action: "Bounded instance weight reduction, then verify." },
  ROUTE_INSTANCE_FAILURE: { plain: "One route membership diverges while its siblings and peers counter-support broader scope.", action: "Route × instance quarantine." },
  SHARED_ROUTE_FAILURE: { plain: "The same route fails across peer instances.", action: "Suppress unsafe retry and apply route protection; do not mass-eject." },
  TRAFFIC_OVERLOAD: { plain: "Broad queue and load evidence explains degradation.", action: "Admission, rate, or concurrency protection." },
  VERSION_SPECIFIC_FAILURE: { plain: "A deployment cohort regresses against a comparable control cohort.", action: "Version membership removal if remaining capacity is safe." },
  UNKNOWN: { plain: "Evidence is sparse, conflicting, stale, out-of-distribution, or unsafe.", action: "No destructive automatic action; require review." },
};

export const incident = {
  id: "inc-1042",
  title: "Checkout diverged on Backend B",
  classification: "ROUTE_INSTANCE_FAILURE" as FailureClass,
  status: "VERIFYING",
  severity: "HIGH",
  scope: "/checkout × Backend B",
  openedAt: "21 Jul · 22:02:14 IST",
  lastObserved: "2 seconds before snapshot",
  owner: "Control worker · rules path",
  correlationId: "cor_shlb_7c3f19",
  confidence: 82,
  completeness: 88,
  conflicts: 1,
  missingSources: ["Backend C auth route telemetry"],
  brief:
    "Since 22:02, /checkout on Backend B timed out 6.1× more often than checkout on its peers. Public, auth, and catalog on the same physical instance remained within their aligned ranges. A route-only quarantine is observed; verification is not complete.",
};

export const traceStages: TraceStage[] = [
  { id: "evidence", short: "Evidence", label: "Evidence window", status: "complete", at: "22:02:14.118", engine: "window-builder v1.4", result: "6 sources · 428 affected samples", reason: "Proxy outcomes, peers, sibling routes, queue, observed state, and probes align within one bounded window.", refs: ["win_7fe2", "prom_q_18", "log_q_41"] },
  { id: "fingerprint", short: "Fingerprint", label: "Failure fingerprint", status: "complete", at: "22:02:14.184", engine: "fingerprint v2.1", result: "route-local divergence", reason: "Affected route set is {checkout}; affected instance set is {B}; three sibling routes provide healthy counter-evidence.", refs: ["fp_b5e8", "sig_92ab"] },
  { id: "classification", short: "Class", label: "Classification", status: "complete", at: "22:02:14.231", engine: "rules resolver v4", result: "ROUTE_INSTANCE_FAILURE", reason: "Route-local rule fired. Instance-wide and shared-route rules were contradicted by aligned controls.", refs: ["cls_281", "rule_route_local_04"] },
  { id: "confidence", short: "Bounds", label: "Confidence and completeness", status: "complete", at: "22:02:14.244", engine: "confidence v2", result: "0.82 confidence · 0.88 complete", reason: "One stale auth source lowers completeness. Shadow-model probability is advisory and does not authorize traffic changes.", refs: ["conf_208", "model_shadow_rf3"] },
  { id: "safety", short: "Safety", label: "Deterministic safety decision", status: "complete", at: "22:02:14.310", engine: "safety-envelope v5", result: "Allowed with 7/7 checks", reason: "Checkout keeps two peers; unique fleet capacity is counted once; ambiguous POST retry remains suppressed; rollback snapshot exists.", refs: ["cert_91c", "policy_checkout_12"] },
  { id: "routing-unit", short: "Scope", label: "Minimum routing unit", status: "complete", at: "22:02:14.344", engine: "selector v3", result: "ROUTE_INSTANCE · 1 membership", reason: "This is the smallest supported safe unit. Whole-instance, complete-route, and version candidates displace unsupported healthy scope.", refs: ["unit_checkout_b", "cost_4d11"] },
  { id: "haproxy", short: "HAProxy", label: "HAProxy action and readback", status: "complete", at: "22:02:14.912", engine: "adapter v1 · generation 184", result: "Requested drain · observed drain", reason: "The absolute target was applied once and confirmed by Runtime readback. This confirms state, not effectiveness.", refs: ["act_7719", "attempt_01", "obs_291"] },
  { id: "verification", short: "Verify", label: "Dual verification", status: "current", at: "22:08:54.022", engine: "verification v3", result: "Relief passed · preservation collecting", reason: "Affected errors improved. The preserved cohort still needs 124 real requests before the invariant can close.", refs: ["ver_554", "window_post_44"] },
  { id: "outcome", short: "Outcome", label: "Outcome and recovery", status: "blocked", at: "pending", engine: "controller policy v12", result: "Not yet decided", reason: "No commit or reintegration advance is allowed until both verification obligations pass with fresh evidence.", refs: ["reint_228"] },
];

export const scopeCandidates = [
  { unit: "Route membership", targets: "1", healthyDisplaced: "0", result: "Allowed · selected", reason: "Supported by evidence and residual route capacity" },
  { unit: "Whole instance", targets: "4", healthyDisplaced: "3 pools", result: "Rejected", reason: "Public, auth, and catalog on B are healthy counter-evidence" },
  { unit: "Complete route", targets: "3", healthyDisplaced: "2 peers", result: "Rejected", reason: "Checkout peers A and C remain useful controls" },
  { unit: "Version cohort", targets: "10", healthyDisplaced: "9 memberships", result: "Not allowed", reason: "No contemporaneous version-wide regression" },
];

export const action = {
  id: "act-7719",
  lifecycle: "VERIFYING" as ActionLifecycle,
  controllerGeneration: 184,
  target: "be_checkout/srv_inst_b",
  routingUnit: "ROUTE_INSTANCE",
  actor: "controller:rules-only",
  reason: "Evidence certificate cert_91c selected minimum supported safe scope",
  idempotencyKey: "sha256:11a8…7d02",
  expectedEffect: "Checkout failures fall while three sibling routes on Backend B retain eligibility.",
  expiry: "22:12:14 IST",
  approval: "Automatic · policy revision 12",
  rollbackSnapshot: "snap_lkg_183_checkout_b",
  previous: { admin: "ready", weight: 100, generation: 183 },
  requested: { admin: "drain", weight: 0, generation: 184 },
  observed: { admin: "drain", weight: 0, generation: 184 },
  attempts: [
    { number: 1, at: "22:02:14.411", operation: "set absolute state", result: "acknowledged", readback: "drain · weight 0", duration: "501 ms" },
  ],
};

export const actionQueue = [
  action,
  { id: "act-7720", lifecycle: "NEEDS_REVIEW" as ActionLifecycle, target: "be_auth/srv_inst_c", routingUnit: "NO_CHANGE", actor: "controller", expectedEffect: "None", expiry: "—", approval: "Operator review required" },
  { id: "act-7688", lifecycle: "COMMITTED" as ActionLifecycle, target: "be_catalog/srv_inst_c", routingUnit: "ROUTE_INSTANCE", actor: "operator:approved", expectedEffect: "Bound catalog exposure", expiry: "completed", approval: "Approved" },
  { id: "act-7651", lifecycle: "ROLLED_BACK" as ActionLifecycle, target: "be_public/srv_inst_a", routingUnit: "INSTANCE_WEIGHT", actor: "controller", expectedEffect: "Reduce latency", expiry: "completed", approval: "Automatic" },
  { id: "act-7610", lifecycle: "RESULT_UNKNOWN" as ActionLifecycle, target: "be_checkout/srv_inst_c", routingUnit: "ROUTE_INSTANCE", actor: "operator", expectedEffect: "Confirm stale readback", expiry: "expired", approval: "Duplicate controls frozen" },
];

export const reintegration = {
  id: "reint-228",
  target: "/catalog × Backend C",
  currentStage: "20%",
  requestedWeight: 20,
  observedWeight: 5,
  observedShare: 4.7,
  samples: 176,
  requiredSamples: 300,
  cooldown: "00:48",
  flapCount: 1,
  nextEligibleAt: "22:10:30 IST, after readback and 124 samples",
  lastVerified: "5%",
  probe: "3/3 passed · synthetic",
  preservation: "Public/auth/checkout on C within bounds",
};

export const reintegrationStages = [
  { name: "QUARANTINED", status: "complete", requested: 0, observed: 0, note: "Incident contained" },
  { name: "PROBING", status: "complete", requested: 0, observed: 0, note: "3/3 probes passed" },
  { name: "5%", status: "verified", requested: 5, observed: 5, note: "Last verified safe stage" },
  { name: "20%", status: "current", requested: 20, observed: 5, note: "Readback differs · collecting" },
  { name: "50%", status: "pending", requested: 50, observed: null, note: "Needs 300 samples" },
  { name: "100%", status: "pending", requested: 100, observed: null, note: "Needs 500 samples" },
  { name: "HEALTHY", status: "pending", requested: 100, observed: null, note: "5 min stable at full weight" },
] as const;

export const errorSeries: TimePoint[] = [
  { time: "21:54", value: 2.8, peer: 2.9, preserved: 99.5 },
  { time: "21:56", value: 3.1, peer: 3.0, preserved: 99.4 },
  { time: "21:58", value: 5.4, peer: 3.1, preserved: 99.5 },
  { time: "22:00", value: 11.7, peer: 3.0, preserved: 99.3 },
  { time: "22:02", value: 18.2, peer: 3.1, preserved: 99.4 },
  { time: "22:04", value: 7.8, peer: 3.0, preserved: 99.3 },
  { time: "22:06", value: 3.9, peer: 3.1, preserved: 99.4 },
  { time: "22:08", value: 3.1, peer: 3.0, preserved: 99.3 },
];

export const trafficSeries: TimePoint[] = [
  { time: "21:54", value: 151, peer: 48, preserved: 83 },
  { time: "21:56", value: 157, peer: 50, preserved: 83 },
  { time: "21:58", value: 164, peer: 51, preserved: 82 },
  { time: "22:00", value: 171, peer: 56, preserved: 80 },
  { time: "22:02", value: 168, peer: 54, preserved: 78 },
  { time: "22:04", value: 160, peer: 52, preserved: 82 },
  { time: "22:06", value: 158, peer: 50, preserved: 83 },
  { time: "22:08", value: 161, peer: 51, preserved: 83 },
];

export const incidentTimeline = [
  { at: "22:02:14", label: "Incident opened", detail: "Route-local divergence supported by 428 samples", state: "danger" },
  { at: "22:02:14", label: "Minimum scope selected", detail: "checkout × Backend B; three sibling memberships preserved", state: "warning" },
  { at: "22:02:15", label: "HAProxy state confirmed", detail: "requested drain matches observed drain", state: "neutral" },
  { at: "22:06:42", label: "Relief obligation passed", detail: "checkout error family returned to peer range", state: "success" },
  { at: "22:09:42", label: "Preservation still collecting", detail: "124 real requests remain; no outcome committed", state: "warning" },
];

export const incidents = [
  incident,
  { id: "inc-1043", title: "Auth telemetry is stale on Backend C", classification: "UNKNOWN" as FailureClass, status: "NEEDS_REVIEW", severity: "MEDIUM", scope: "/auth × Backend C", openedAt: "21 Jul · 22:07:09 IST", confidence: 41, completeness: 52, owner: "Unassigned" },
  { id: "inc-1037", title: "Catalog latency followed the demo-v2 cohort", classification: "VERSION_SPECIFIC_FAILURE" as FailureClass, status: "REINTEGRATING", severity: "HIGH", scope: "demo-v2 × /catalog", openedAt: "21 Jul · 20:44:11 IST", confidence: 76, completeness: 93, owner: "R. Iyer" },
  { id: "inc-1029", title: "Offered load exceeded checkout admission policy", classification: "TRAFFIC_OVERLOAD" as FailureClass, status: "RESOLVED", severity: "HIGH", scope: "/checkout", openedAt: "20 Jul · 17:19:32 IST", confidence: 91, completeness: 97, owner: "S. Nair" },
];

export const logRows = [
  { at: "22:09:38.412", source: "haproxy", event: "request_completed", route: "/checkout", member: "inst-a", result: "2xx", duration: "301 ms", correlation: "req_38d4" },
  { at: "22:09:37.908", source: "controller", event: "verification_updated", route: "/checkout", member: "inst-b", result: "collecting", duration: "—", correlation: "cor_shlb_7c3f19" },
  { at: "22:09:36.115", source: "nginx", event: "request_completed", route: "/public", member: "inst-b", result: "2xx", duration: "84 ms", correlation: "req_d1a8" },
  { at: "22:09:34.792", source: "haproxy", event: "request_completed", route: "/auth", member: "inst-c", result: "telemetry gap", duration: "—", correlation: "req_7c21" },
  { at: "22:09:32.404", source: "worker", event: "desired_observed_drift", route: "/catalog", member: "inst-c", result: "20 requested / 5 observed", duration: "4 ms", correlation: "cor_reint_228" },
];

export const experimentBaselines = [
  { name: "Plain Round Robin", median: 58, low: 51, high: 65, success: 96.4, retry: 1.18, trials: 30 },
  { name: "HAProxy health checks", median: 62, low: 55, high: 69, success: 96.9, retry: 1.11, trials: 30 },
  { name: "Static backend-wide", median: 49, low: 41, high: 57, success: 97.2, retry: 1.06, trials: 30 },
  { name: "EBMSH proposed", median: 84, low: 79, high: 88, success: 97.4, retry: 1.03, trials: 30 },
];

export const experimentScenarios = [
  "Instance crash",
  "Slow instance",
  "Route-instance failure",
  "Shared-route dependency",
  "Traffic overload",
  "Version regression",
  "Flapping recovery",
  "Unknown mixed anomaly",
];

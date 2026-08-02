export const failureClasses = [
  "HEALTHY",
  "INSTANCE_DOWN",
  "INSTANCE_DEGRADED",
  "ROUTE_INSTANCE_FAILURE",
  "SHARED_ROUTE_FAILURE",
  "TRAFFIC_OVERLOAD",
  "VERSION_SPECIFIC_FAILURE",
  "UNKNOWN",
] as const;

export type FailureClass = (typeof failureClasses)[number];

export type EvidenceState = "complete" | "partial" | "stale" | "missing";
export type MembershipState =
  | "healthy"
  | "degraded"
  | "failing"
  | "quarantined"
  | "verifying"
  | "reintegrating"
  | "unknown"
  | "no-membership";

export type RoutingState = {
  admin: "ready" | "drain" | "maint" | "unavailable" | "none";
  weight: number | null;
};

export type MatrixCellData = {
  routeId: string;
  instanceId: string;
  state: MembershipState;
  desired: RoutingState;
  observed: RoutingState;
  effectiveWeight: number | null;
  errorRate: number | null;
  p95Ms: number | null;
  sampleCount: number;
  freshnessSeconds: number | null;
  evidence: EvidenceState;
  deviation: string;
  marker?: "quarantine" | "reintegration" | "drift";
  incidentId?: string;
  note: string;
};

export type RouteFixture = {
  id: string;
  label: string;
  backend: string;
  criticality: "critical" | "high" | "standard";
  requestsPerSecond: number;
  retryPolicy: string;
};

export type InstanceFixture = {
  id: string;
  label: string;
  server: string;
  version: string;
  capacity: number;
  utilization: number;
  addressAlias: string;
  probe: "passing" | "degraded" | "unknown";
  lastTrafficSeconds: number;
};

export type TraceStage = {
  id: string;
  short: string;
  label: string;
  status: "complete" | "current" | "blocked" | "pending";
  at: string;
  engine: string;
  result: string;
  reason: string;
  refs: string[];
};

export type TimePoint = {
  time: string;
  value: number | null;
  peer?: number | null;
  preserved?: number | null;
};

export type ActionLifecycle =
  | "PLANNED"
  | "SAFETY_CHECKED"
  | "PREPARED"
  | "APPLIED"
  | "STATE_CONFIRMED"
  | "VERIFYING"
  | "COMMITTED"
  | "ROLLING_BACK"
  | "ROLLED_BACK"
  | "NEEDS_REVIEW"
  | "RESULT_UNKNOWN"
  | "EXPIRED"
  | "SUPERSEDED";

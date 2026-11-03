"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { useControlPlane } from "@/lib/use-control-plane";

export type OperationalIncident = {
  id: string;
  environment_id: string;
  route_id: string | null;
  instance_id: string | null;
  target: { route: string | null; instance: string | null };
  status: string;
  severity: string;
  classification: string;
  fingerprint_hash: string;
  summary: string;
  opened_at: string;
  last_observed_at: string;
  resolved_at: string | null;
  version: number;
};
export type OperationalAction = {
  id: string;
  incident_id: string;
  lifecycle: string;
  kind: string;
  controller_generation: number;
  target: { backend: string; server: string };
  previous_desired: Record<string, unknown>;
  previous_observed: Record<string, unknown>;
  requested_state: Record<string, unknown>;
  expected_effect: string;
  preservation_set: string[];
  verification_criteria: Record<string, unknown>;
  rollback_strategy: Record<string, unknown>;
  expires_at: string;
  version: number;
  attempts: Array<{
    id: string;
    sequence: number;
    operation: string;
    status: string;
    issued_at: string;
    completed_at: string | null;
    response: Record<string, unknown>;
    observed_state: Record<string, unknown>;
    error_code: string | null;
  }>;
  verification?: Array<{
    revision: number;
    result: string;
    affected: Record<string, unknown>;
    preservation: Record<string, unknown>;
    sample_count: number;
    completed_at: string | null;
  }>;
};
export type MatrixCell = {
  membership_id: string;
  route_id: string;
  route: string;
  criticality: string;
  instance_id: string;
  instance: string;
  capacity: number;
  haproxy_backend: string;
  haproxy_server: string;
  desired: { admin: string; weight: number | null };
  observed: {
    admin_state: string;
    status: string;
    weight: number;
    queue: number;
    sessions: number;
    last_change_seconds: number;
  } | null;
  drift: boolean;
  evidence: {
    samples?: number;
    errors?: number;
    status_codes?: Record<string, number>;
    error_rate?: number | null;
    p95_ms?: number | null;
  };
  direct_probe?: {
    reachable?: boolean;
    application_ok?: boolean;
    status?: number | null;
  };
  incident_id: string | null;
};
export type TrafficHistory = {
  range_seconds: number;
  bucket_seconds: number;
  observation_window_seconds: number;
  points: Array<{
    at: string;
    routes: Record<string, {
      requests_per_second: number | null;
      errors_per_second: number | null;
      error_rate: number | null;
      worst_instance_p95_ms: number | null;
      samples: number;
    }>;
  }>;
};
export type OperationalSummary = {
  environment: {
    id: string;
    name: string;
    kind: string;
    mode: string;
    automation_frozen: boolean;
    controller_generation: number;
  };
  traffic: {
    admitted_rps: number | null;
    success_ratio: number | null;
    healthy_capacity_percent: number | null;
    route_capacity_percent?: Record<string, number>;
  };
  active_incidents: OperationalIncident[];
  current_action: OperationalAction | null;
  freshness: {
    evidence_window_ended_at: string | null;
    observed_state_at: string | null;
    completeness: number;
  };
  worker: {
    status: string;
    generation: number | null;
    last_heartbeat_at: string | null;
  };
  lab_reset: null | {
    id: string;
    status: string;
    result: Record<string, unknown>;
    created_at: string;
    completed_at: string | null;
  };
};
export type DecisionTraceData = {
  incident: OperationalIncident;
  lab_fault: null | {
    id: string;
    scenario: string;
    scenario_kind: string | null;
    target: { route: string | null; instance: string | null };
    duration_seconds: number;
    status: string;
    ground_truth_id: string;
    applied_at: string | null;
    expires_at: string;
    cleared_at: string | null;
  };
  evidence: null | {
    window_id: string;
    started_at: string;
    ended_at: string;
    completeness: number;
    metrics: Record<string, unknown>;
    probes: Record<string, unknown>;
    conflicts: string[];
  };
  fingerprint: null | {
    id: string;
    schema_version: string;
    hash: string;
    canonical: string;
  };
  classifications: Array<{
    id: string;
    revision: number;
    final_class: string;
    confidence: number;
    completeness: number;
    evidence_support: Record<string, unknown>;
    competing_hypotheses: Array<Record<string, unknown>>;
    evidence_window: null | {
      window_id: string;
      started_at: string;
      ended_at: string;
      completeness: number;
      metrics: Record<string, unknown>;
      probes: Record<string, unknown>;
      conflicts: string[];
    };
  }>;
  certificate: null | {
    id: string;
    hash: string;
    scope_evidence: Record<string, unknown>;
    safety_inputs: Record<string, unknown>;
    candidate_actions: Array<Record<string, unknown>>;
  };
  action: OperationalAction | null;
  verification: null | {
    result: string;
    affected: Record<string, unknown>;
    preservation: Record<string, unknown>;
    sample_count: number;
    completed_at: string | null;
  };
  recovery: null | {
    id: string;
    status: string;
    current_stage: string;
    last_verified_stage: string;
  };
};
export type RecoveryRun = {
  id: string;
  incident_id: string;
  action_id: string;
  status: string;
  current_stage: string;
  last_verified_stage: string;
  retry_count: number;
  maximum_retries: number;
  next_transition_at: string | null;
  version: number;
};
export type RecoveryDetail = RecoveryRun & {
  stages: Array<{
    id: string;
    sequence: number;
    name: string;
    requested_weight: number | null;
    observed_weight: number | null;
    status: string;
    sample_count: number;
    minimum_samples: number;
    started_at: string | null;
    verified_at: string | null;
    result: Record<string, unknown>;
  }>;
};
export type LabFault = {
  id: string;
  scenario: string;
  scenario_kind: string;
  target: { route: string | null; instance: string | null };
  duration_seconds: number;
  status: string;
  ground_truth_id: string;
  expires_at: string;
  applied_at: string | null;
  cleared_at: string | null;
  version: number;
};

function useEnvironmentQuery<T>(
  suffix: string,
  path: (environmentId: string) => string,
  interval = 5000,
) {
  const control = useControlPlane();
  const environmentId = control.status?.environment.id;
  return useQuery({
    queryKey: ["environment", environmentId, suffix],
    queryFn: async () => (await apiRequest<T>(path(environmentId!))).data,
    enabled: control.state === "live" && Boolean(environmentId),
    refetchInterval: interval,
  });
}

export function useOperationalSummary() {
  return useEnvironmentQuery<OperationalSummary>(
    "summary",
    (id) => `/api/v1/environments/${id}/operational-summary`,
    3000,
  );
}
export function useTrafficHistory() {
  return useEnvironmentQuery<TrafficHistory>(
    "traffic-history",
    (id) => `/api/v1/environments/${id}/traffic-history`,
    5000,
  );
}
export function useMatrix() {
  return useEnvironmentQuery<{
    environment_id: string;
    observed_at: string | null;
    evidence_window_ended_at: string | null;
    cells: MatrixCell[];
  }>("matrix", (id) => `/api/v1/environments/${id}/matrix`, 3000);
}
export function useIncidents() {
  return useEnvironmentQuery<{ items: OperationalIncident[] }>(
    "incidents",
    (id) => `/api/v1/environments/${id}/incidents`,
    3000,
  );
}
export function useActions() {
  return useEnvironmentQuery<{ items: OperationalAction[] }>(
    "actions",
    (id) => `/api/v1/environments/${id}/actions`,
    3000,
  );
}
export function useRecoveries() {
  return useEnvironmentQuery<{ items: RecoveryRun[] }>(
    "recovery",
    (id) => `/api/v1/environments/${id}/reintegration`,
    3000,
  );
}
export function useFaults() {
  return useEnvironmentQuery<{ items: LabFault[] }>(
    "faults",
    (id) => `/api/v1/environments/${id}/lab/faults`,
    3000,
  );
}

export function useIncident(incidentId?: string) {
  const control = useControlPlane();
  return useQuery({
    queryKey: ["incident", incidentId],
    queryFn: async () =>
      (await apiRequest<OperationalIncident>(`/api/v1/incidents/${incidentId}`))
        .data,
    enabled: control.state === "live" && Boolean(incidentId),
    refetchInterval: 3000,
  });
}
export function useDecisionTrace(incidentId?: string) {
  const control = useControlPlane();
  return useQuery({
    queryKey: ["incident", incidentId, "trace"],
    queryFn: async () =>
      (
        await apiRequest<DecisionTraceData>(
          `/api/v1/incidents/${incidentId}/decision-trace`,
        )
      ).data,
    enabled: control.state === "live" && Boolean(incidentId),
    refetchInterval: 3000,
  });
}
export function useAction(actionId?: string) {
  const control = useControlPlane();
  return useQuery({
    queryKey: ["action", actionId],
    queryFn: async () =>
      (await apiRequest<OperationalAction>(`/api/v1/actions/${actionId}`)).data,
    enabled: control.state === "live" && Boolean(actionId),
    refetchInterval: 3000,
  });
}
export function useRecovery(runId?: string) {
  const control = useControlPlane();
  return useQuery({
    queryKey: ["recovery", runId],
    queryFn: async () =>
      (await apiRequest<RecoveryDetail>(`/api/v1/reintegration/${runId}`)).data,
    enabled: control.state === "live" && Boolean(runId),
    refetchInterval: 3000,
  });
}

export function useCreateFault() {
  const control = useControlPlane();
  const client = useQueryClient();
  const environmentId = control.status?.environment.id;
  return useMutation({
    mutationFn: async ({
      scenario,
      scenarioKind,
      targetRoute,
      targetInstance,
      durationSeconds,
    }: {
      scenario: string;
      scenarioKind: "route_failure" | "instance_down" | "gray_failure" | "unknown_conflict";
      targetRoute: string | null;
      targetInstance: string | null;
      durationSeconds: number;
    }) =>
      (
        await apiRequest<LabFault>(
          `/api/v1/environments/${environmentId}/lab/faults`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRF-Token": control.session!.csrf_token,
              "Idempotency-Key": crypto.randomUUID(),
            },
            body: JSON.stringify({
              scenario,
              scenario_kind: scenarioKind,
              target_route: targetRoute,
              target_instance: targetInstance,
              duration_seconds: durationSeconds,
            }),
          },
        )
      ).data,
    onSuccess: async () => {
      await client.invalidateQueries({
        queryKey: ["environment", environmentId],
      });
    },
  });
}

export function useClearFault() {
  const control = useControlPlane();
  const client = useQueryClient();
  const environmentId = control.status?.environment.id;
  return useMutation({
    mutationFn: async (fault: LabFault) =>
      (
        await apiRequest<LabFault>(`/api/v1/lab/faults/${fault.id}`, {
          method: "DELETE",
          headers: {
            "X-CSRF-Token": control.session!.csrf_token,
            "Idempotency-Key": crypto.randomUUID(),
            "If-Match": `"${fault.version}"`,
          },
        })
      ).data,
    onSuccess: async () => {
      await client.invalidateQueries({
        queryKey: ["environment", environmentId],
      });
    },
  });
}

export function useResetLab() {
  const control = useControlPlane();
  const client = useQueryClient();
  const environmentId = control.status?.environment.id;
  return useMutation({
    mutationFn: async () =>
      (
        await apiRequest<NonNullable<OperationalSummary["lab_reset"]>>(
          `/api/v1/environments/${environmentId}/lab/reset`,
          {
            method: "POST",
            headers: {
              "X-CSRF-Token": control.session!.csrf_token,
              "Idempotency-Key": crypto.randomUUID(),
            },
          },
        )
      ).data,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["environment", environmentId] });
    },
  });
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/api/client";
import { useControlPlane } from "@/lib/use-control-plane";

export type OperationalIncident = {
  id: string;
  environment_id: string;
  route_id: string | null;
  instance_id: string | null;
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
    error_rate?: number | null;
    p95_ms?: number | null;
  };
  incident_id: string | null;
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
};
export type DecisionTraceData = {
  incident: OperationalIncident;
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
export function useMatrix() {
  return useEnvironmentQuery<{
    environment_id: string;
    observed_at: string | null;
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
      durationSeconds,
    }: {
      scenario: string;
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

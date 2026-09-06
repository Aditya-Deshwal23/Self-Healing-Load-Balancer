import { expect, test } from "@playwright/test";

const incident = {
  id: "inc-live",
  environment_id: "env-live",
  route_id: "route-checkout",
  instance_id: "inst-b",
  status: "VERIFYING",
  severity: "HIGH",
  classification: "ROUTE_INSTANCE_FAILURE",
  fingerprint_hash: "fp-live",
  summary: "Checkout requires observed-state confirmation",
  opened_at: "2026-09-06T11:30:00.000Z",
  last_observed_at: "2026-09-06T11:30:01.000Z",
  resolved_at: null,
  version: 1,
};

const action = {
  id: "act-live",
  incident_id: incident.id,
  lifecycle: "COMMITTED",
  kind: "ROUTE_MEMBERSHIP_QUARANTINE",
  controller_generation: 12,
  target: { backend: "be_checkout", server: "srv_inst_b" },
  previous_desired: { admin_state: "ready", weight: 100 },
  previous_observed: { admin_state: "ready", weight: 100 },
  requested_state: { admin_state: "drain", weight: 0 },
  expected_effect: "Remove the failing route membership.",
  preservation_set: [],
  verification_criteria: {},
  rollback_strategy: {},
  expires_at: "2026-09-06T12:00:00.000Z",
  version: 1,
  attempts: [],
};

test("desired-state-only actions render confirming until Runtime readback", async ({
  page,
}) => {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    let data: unknown;
    if (path.endsWith("/auth/me")) {
      data = {
        user: { id: "user", email: "researcher@shlb.local", status: "ACTIVE" },
        scopes: [],
        csrf_token: "csrf",
      };
    } else if (path.endsWith("/system/status")) {
      data = {
        environment: {
          id: "env-live",
          project_id: "project",
          name: "LAB",
          kind: "LAB",
          mode: "RULES_ONLY",
          automation_frozen: false,
          controller_generation: 12,
        },
        control_plane: {
          api: "ok",
          postgresql: "ok",
          redis: "ok",
          sse: "ok",
          worker: "ok",
          haproxy_access: true,
          control_authority: "worker",
        },
        freshness: {
          control_loop: "2026-09-06T11:30:01.000Z",
          telemetry: "2026-09-06T11:30:01.000Z",
          last_confirmed_state: null,
        },
      };
    } else if (path.endsWith("/system/capabilities")) {
      data = {
        phase: "LAB",
        features: {
          lab: true,
          rest_registry: true,
          server_side_sessions: true,
          sse: true,
          prometheus_evidence: true,
          haproxy_readback: true,
          routing_mutations: true,
          healing_actions: true,
          verification: true,
          reintegration: true,
        },
        prototype_support: { implemented: [], planned: [] },
      };
    } else if (path.endsWith("/operational-summary")) {
      data = {
        environment: {
          id: "env-live",
          name: "LAB",
          kind: "LAB",
          mode: "RULES_ONLY",
          automation_frozen: false,
          controller_generation: 12,
        },
        traffic: {
          admitted_rps: 1,
          success_ratio: 1,
          healthy_capacity_percent: 1,
        },
        active_incidents: [incident],
        current_action: action,
        freshness: {
          evidence_window_ended_at: "2026-09-06T11:30:01.000Z",
          observed_state_at: null,
          completeness: 1,
        },
        worker: {
          status: "ACTIVE",
          generation: 12,
          last_heartbeat_at: "2026-09-06T11:30:01.000Z",
        },
      };
    } else if (path.endsWith("/decision-trace")) {
      data = {
        incident,
        evidence: null,
        fingerprint: null,
        classifications: [],
        certificate: null,
        action,
        verification: null,
        recovery: null,
      };
    } else if (path.endsWith("/matrix")) {
      data = { environment_id: "env-live", observed_at: null, cells: [] };
    } else {
      data = {};
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ data }),
    });
  });

  await page.goto("/app");
  await expect(page.getByText(/Confirming observed state/i)).toBeVisible();
  await expect(page.getByText("COMMITTED")).toHaveCount(0);
  await expect(page.getByText(/HAProxy observed/)).toBeVisible();
});

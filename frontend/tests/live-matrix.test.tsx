import axe from "axe-core";
import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { MatrixCell } from "@/lib/api/operations";

const testCells = vi.hoisted(() => {
  const routes = ["public", "auth", "catalog", "checkout"];
  const instances = ["inst-a", "inst-b", "inst-c"];
  return routes.flatMap((route, routeIndex) =>
    instances.map((instance, instanceIndex) => ({
      membership_id: `${route}-${instance}`,
      route_id: `route-${route}`,
      route,
      criticality: route === "checkout" ? "CRITICAL" : "STANDARD",
      instance_id: `instance-${instance}`,
      instance,
      capacity: 100,
      haproxy_backend: `be_${route}`,
      haproxy_server: `srv_inst_${instance.at(-1)}`,
      desired:
        route === "checkout" && instance === "inst-b"
          ? { admin: "drain", weight: 0 }
          : { admin: "ready", weight: 100 },
      observed:
        route === "checkout" && instance === "inst-b"
          ? {
              admin_state: "drain",
              status: "DRAIN",
              weight: 0,
              queue: 0,
              sessions: 0,
              last_change_seconds: 2,
            }
          : {
              admin_state: "ready",
              status: "UP",
              weight: 100,
              queue: 0,
              sessions: 1,
              last_change_seconds: 30,
            },
      drift: false,
      evidence: {
        samples: 12 + routeIndex + instanceIndex,
        errors: 0,
        error_rate: 0,
        p95_ms: 2.4,
      },
      incident_id:
        route === "checkout" && instance === "inst-b"
          ? "incident-12345678"
          : null,
    })),
  ) as MatrixCell[];
});

vi.mock("@/lib/api/operations", async (importOriginal) => {
  const original =
    await importOriginal<typeof import("@/lib/api/operations")>();
  return {
    ...original,
    useMatrix: () => ({
      isLoading: false,
      isError: false,
      data: {
        environment_id: "lab",
        observed_at: "2026-08-02T12:00:00Z",
        cells: testCells,
      },
    }),
  };
});

import { LiveRouteMatrix } from "@/features/traffic/live-matrix";

describe("live route matrix", () => {
  it("exposes exact state, keyboard navigation, and a focus-managed detail sheet", async () => {
    const { container, getByRole } = render(<LiveRouteMatrix />);
    const first = getByRole("button", { name: /public on inst-a: Healthy/i });
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowRight" });
    expect(
      getByRole("button", { name: /public on inst-b: Healthy/i }),
    ).toHaveFocus();

    const target = getByRole("button", {
      name: /checkout on inst-b: Quarantined/i,
    });
    fireEvent.click(target);
    expect(getByRole("dialog", { name: /checkout.*inst-b/i })).toHaveAttribute(
      "open",
    );
    expect(
      getByRole("button", { name: "Close membership details" }),
    ).toBeVisible();

    const results = await axe.run(container);
    expect(results.violations).toEqual([]);
  });
});

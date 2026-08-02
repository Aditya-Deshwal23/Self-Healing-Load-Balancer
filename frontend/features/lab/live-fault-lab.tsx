"use client";

import { AlertTriangle, Check, FlaskConical, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { useClearFault, useCreateFault, useFaults } from "@/lib/api/operations";
import { useControlPlane } from "@/lib/use-control-plane";
import { PageHeader, Panel, StateMessage, StatusTag } from "@/components/ui";
import { useSmallViewport } from "@/lib/use-small-viewport";

const scenarios = [
  {
    id: "CHECKOUT_INST_B_FAILURE",
    title: "Checkout fails on Backend B",
    target: "checkout × inst-b",
    classification: "ROUTE_INSTANCE_FAILURE",
    detail:
      "The flagship scenario. Public, auth, and catalog on B remain healthy.",
  },
  {
    id: "INST_B_DOWN",
    title: "Backend B becomes unreachable",
    target: "all routes × inst-b",
    classification: "INSTANCE_DOWN",
    detail: "Direct probes and every B membership fail together.",
  },
  {
    id: "SHARED_CHECKOUT_FAILURE",
    title: "Checkout fails across all instances",
    target: "checkout × A/B/C",
    classification: "SHARED_ROUTE_FAILURE",
    detail: "A shared-route pattern must not mass-eject instances.",
  },
  {
    id: "UNKNOWN_CONFLICT",
    title: "Conflicting checkout evidence",
    target: "checkout × inst-b",
    classification: "UNKNOWN",
    detail: "Insufficient or contradictory evidence must never actuate.",
  },
];

export function LiveFaultLab() {
  const control = useControlPlane();
  const small = useSmallViewport();
  const faults = useFaults();
  const create = useCreateFault();
  const clear = useClearFault();
  const [selected, setSelected] = useState(scenarios[0].id);
  const [duration, setDuration] = useState(180);
  const active = faults.data?.items.find(
    (fault) => !["CLEARED", "EXPIRED", "FAILED"].includes(fault.status),
  );
  const role = control.session?.scopes[0]?.role;
  const authorized = ["RESEARCHER", "PROJECT_ADMIN", "SYSTEM_ADMIN"].includes(
    role ?? "",
  );
  const blocked = small || !authorized || Boolean(active) || create.isPending;

  if (faults.isLoading)
    return (
      <StateMessage state="loading" title="Reading LAB ground truth…">
        Fault resources are separate from controller evidence.
      </StateMessage>
    );
  if (faults.isError || !faults.data)
    return (
      <StateMessage state="failure" title="Fault Lab unavailable.">
        Fault injection is never exposed outside a reachable LAB control path.
      </StateMessage>
    );

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="LAB / Fault scenarios"
        title="Inject a bounded, auto-expiring failure"
        brief="Fault requests require a Researcher role, session authentication, CSRF, and an idempotency key. Backend fault endpoints remain private and ground truth never becomes classifier evidence."
        meta={
          <>
            <StatusTag tone="warning">LAB ONLY</StatusTag>
            <span>{role ?? "No role"}</span>
            <span>one active fault maximum</span>
          </>
        }
      />
      {small && (
        <div className="notice warning">
          <ShieldAlert size={16} />
          <span>
            <strong>Read-only on this viewport.</strong> Fault injection is
            disabled on mobile.
          </span>
        </div>
      )}
      {active && (
        <Panel
          title="Active ground truth"
          kicker="Independent fault lifecycle"
          action={<StatusTag tone="warning">{active.status}</StatusTag>}
        >
          <div className="active-fault">
            <FlaskConical size={22} />
            <div>
              <strong>{active.scenario}</strong>
              <p>
                {active.target.route ?? "all routes"} × {active.target.instance}{" "}
                · expires {new Date(active.expires_at).toLocaleTimeString()}
              </p>
              <code>{active.ground_truth_id}</code>
            </div>
            <button
              className="button danger"
              type="button"
              disabled={small || clear.isPending}
              onClick={() => clear.mutate(active)}
            >
              {clear.isPending ? "Requesting cleanup…" : "Clear fault"}
            </button>
          </div>
          {clear.isError && (
            <div className="notice warning">
              <AlertTriangle size={15} />
              <span>{clear.error.message}</span>
            </div>
          )}
        </Panel>
      )}
      <div
        className="fault-scenario-grid"
        role="radiogroup"
        aria-label="Bounded fault scenario"
      >
        {scenarios.map((scenario) => (
          <button
            type="button"
            role="radio"
            aria-checked={selected === scenario.id}
            className={selected === scenario.id ? "selected" : ""}
            onClick={() => setSelected(scenario.id)}
            key={scenario.id}
          >
            <span className="fault-radio">
              {selected === scenario.id && <Check size={12} />}
            </span>
            <span>
              <strong>{scenario.title}</strong>
              <code>{scenario.target}</code>
              <p>{scenario.detail}</p>
              <small>Expected class · {scenario.classification}</small>
            </span>
          </button>
        ))}
      </div>
      <Panel title="Run selected scenario" kicker="Explicit target and expiry">
        <div className="fault-run-controls">
          <label>
            Duration{" "}
            <select
              value={duration}
              onChange={(event) => setDuration(Number(event.target.value))}
              disabled={blocked}
            >
              <option value={90}>90 seconds</option>
              <option value={180}>3 minutes</option>
              <option value={300}>5 minutes</option>
            </select>
          </label>
          <button
            className="button primary"
            type="button"
            disabled={blocked}
            onClick={() =>
              create.mutate({ scenario: selected, durationSeconds: duration })
            }
          >
            {create.isPending ? "Requesting fault…" : "Inject selected fault"}
          </button>
        </div>
        {!authorized && (
          <p className="microcopy">Your role is read-only for LAB faults.</p>
        )}
        {create.isError && (
          <div className="notice warning">
            <AlertTriangle size={15} />
            <span>{create.error.message}</span>
          </div>
        )}
      </Panel>
      <Panel title="Recent ground-truth events" kicker="Not classifier input">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Scenario</th>
                <th>Target</th>
                <th>Applied</th>
                <th>Ground truth</th>
              </tr>
            </thead>
            <tbody>
              {faults.data.items.map((fault) => (
                <tr key={fault.id}>
                  <td>
                    <StatusTag
                      tone={
                        fault.status === "CLEARED" || fault.status === "EXPIRED"
                          ? "neutral"
                          : fault.status === "FAILED"
                            ? "danger"
                            : "warning"
                      }
                    >
                      {fault.status}
                    </StatusTag>
                  </td>
                  <td>
                    <strong>{fault.scenario}</strong>
                  </td>
                  <td>
                    <code>
                      {fault.target.route ?? "*"}/{fault.target.instance ?? "*"}
                    </code>
                  </td>
                  <td>
                    {fault.applied_at
                      ? new Date(fault.applied_at).toLocaleString()
                      : "Pending"}
                  </td>
                  <td>
                    <code>{fault.ground_truth_id}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

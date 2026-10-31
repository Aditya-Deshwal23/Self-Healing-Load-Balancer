"use client";

import { AlertTriangle, Check, FlaskConical, ShieldAlert, Timer } from "lucide-react";
import { useEffect, useState } from "react";
import { useClearFault, useCreateFault, useFaults, useOperationalSummary, useResetLab } from "@/lib/api/operations";
import { useControlPlane } from "@/lib/use-control-plane";
import { KeyValueGrid, PageHeader, Panel, StateMessage, StatusTag } from "@/components/ui";
import { useSmallViewport } from "@/lib/use-small-viewport";

const payloads = [
  {
    id: "P01_CHECKOUT_B",
    title: "Checkout failure · Backend B",
    scenarioKind: "route_failure",
    targetRoute: "checkout",
    targetInstance: "inst-b",
    target: "checkout × inst-b",
    classification: "ROUTE_INSTANCE_FAILURE",
    detail: "One route-instance cell fails while Backend B's other routes stay healthy.",
    controllerBehavior: "If samples, peer health, probes, and capacity guards agree, quarantine only checkout on inst-b.",
    recoveryBehavior: "After clear/expiry, require 3 passing probes, then restore through 5%, 20%, 50%, and 100%. Each stage needs healthy real samples and Runtime readback; failures return to the last verified stage.",
  },
  {
    id: "P02_AUTH_A",
    title: "Auth failure · Backend A",
    scenarioKind: "route_failure",
    targetRoute: "auth",
    targetInstance: "inst-a",
    target: "auth × inst-a",
    classification: "ROUTE_INSTANCE_FAILURE",
    detail: "Tests isolation of the auth route on Backend A.",
    controllerBehavior: "If evidence and capacity checks pass, quarantine only auth on inst-a; other routes on A remain in service.",
    recoveryBehavior: "After clear/expiry, require 3 passing probes, then restore through 5%, 20%, 50%, and 100%. Each stage needs healthy real samples and Runtime readback; failures return to the last verified stage.",
  },
  {
    id: "P03_CATALOG_C",
    title: "Catalog failure · Backend C",
    scenarioKind: "route_failure",
    targetRoute: "catalog",
    targetInstance: "inst-c",
    target: "catalog × inst-c",
    classification: "ROUTE_INSTANCE_FAILURE",
    detail: "Tests a different route and backend from the flagship case.",
    controllerBehavior: "If evidence and capacity checks pass, quarantine only catalog on inst-c; preserve its peers and other C routes.",
    recoveryBehavior: "After clear/expiry, require 3 passing probes, then restore through 5%, 20%, 50%, and 100%. Each stage needs healthy real samples and Runtime readback; failures return to the last verified stage.",
  },
  {
    id: "P04_PUBLIC_B",
    title: "Public route failure · Backend B",
    scenarioKind: "route_failure",
    targetRoute: "public",
    targetInstance: "inst-b",
    target: "public × inst-b",
    classification: "ROUTE_INSTANCE_FAILURE",
    detail: "Checks that a public-route failure stays scoped to one instance.",
    controllerBehavior: "If evidence and capacity checks pass, quarantine only public on inst-b; preserve its peers and other B routes.",
    recoveryBehavior: "After clear/expiry, require 3 passing probes, then restore through 5%, 20%, 50%, and 100%. Each stage needs healthy real samples and Runtime readback; failures return to the last verified stage.",
  },
  {
    id: "P05_SHARED_CHECKOUT",
    title: "Checkout failure · all backends",
    scenarioKind: "route_failure",
    targetRoute: "checkout",
    targetInstance: "all",
    target: "checkout × inst-a/b/c",
    classification: "SHARED_ROUTE_FAILURE",
    detail: "Tests the shared-route branch; the controller should avoid mass ejecting instances.",
    controllerBehavior: "Classify the route as a shared failure and take no automatic routing action, avoiding mass ejection.",
    recoveryBehavior: "No reintegration run is created because no membership was quarantined. Clear/expire the fault; healthy evidence resolves the incident.",
  },
  {
    id: "P06_INSTANCE_DOWN_A",
    title: "Backend A unreachable",
    scenarioKind: "instance_down",
    targetRoute: null,
    targetInstance: "inst-a",
    target: "all routes × inst-a",
    classification: "INSTANCE_DOWN",
    detail: "Simulates instance-wide failure across Backend A's routes.",
    controllerBehavior: "If direct probes, telemetry, and physical-capacity checks agree, quarantine all registered A memberships as one action.",
    recoveryBehavior: "Keep A quarantined until all four route probes pass 3 consecutive worker checks, then restore its baseline memberships and confirm HAProxy readback. Failed probes keep it quarantined.",
  },
  {
    id: "P07_INSTANCE_DOWN_B",
    title: "Backend B unreachable",
    scenarioKind: "instance_down",
    targetRoute: null,
    targetInstance: "inst-b",
    target: "all routes × inst-b",
    classification: "INSTANCE_DOWN",
    detail: "Simulates instance-wide failure across Backend B's routes.",
    controllerBehavior: "If direct probes, telemetry, and physical-capacity checks agree, quarantine all registered B memberships as one action.",
    recoveryBehavior: "Keep B quarantined until all four route probes pass 3 consecutive worker checks, then restore its baseline memberships and confirm HAProxy readback. Failed probes keep it quarantined.",
  },
  {
    id: "P08_GRAY_FAILURE_A",
    title: "Gray failure · Backend A",
    scenarioKind: "gray_failure",
    targetRoute: null,
    targetInstance: "inst-a",
    target: "all routes × inst-a",
    classification: "HEALTHY · shadow signal only",
    detail: "Adds latency and a low error rate while basic health remains reachable.",
    controllerBehavior: "The deterministic classifier remains authoritative. The fast-path latency signal is advisory only and cannot actuate by itself.",
    recoveryBehavior: "No quarantine or recovery run is expected from this profile alone. Clear/expire it and confirm latency/error evidence returns to baseline.",
  },
  {
    id: "P09_GRAY_FAILURE_C",
    title: "Gray failure · Backend C",
    scenarioKind: "gray_failure",
    targetRoute: null,
    targetInstance: "inst-c",
    target: "all routes × inst-c",
    classification: "HEALTHY · shadow signal only",
    detail: "Repeats the gray-failure profile on a different instance.",
    controllerBehavior: "The deterministic classifier remains authoritative. The fast-path latency signal is advisory only and cannot actuate by itself.",
    recoveryBehavior: "No quarantine or recovery run is expected from this profile alone. Clear/expire it and confirm latency/error evidence returns to baseline.",
  },
  {
    id: "UNKNOWN_CONFLICT",
    title: "Conflicting evidence · checkout B",
    scenarioKind: "unknown_conflict",
    targetRoute: "checkout",
    targetInstance: "inst-b",
    target: "checkout × inst-b",
    classification: "UNKNOWN",
    detail: "Tests conservative handling of contradictory evidence; automated actuation should not occur.",
    controllerBehavior: "Record UNKNOWN with the conflict reason and NO_ACTION; do not mutate HAProxy.",
    recoveryBehavior: "No reintegration run is created. Clear/expire the fault; once evidence is healthy the non-action incident resolves.",
  },
] as const;

export function LiveFaultLab() {
  const control = useControlPlane();
  const small = useSmallViewport();
  const faults = useFaults();
  const summary = useOperationalSummary();
  const create = useCreateFault();
  const clear = useClearFault();
  const resetLab = useResetLab();
  const [selected, setSelected] = useState<string>(payloads[0].id);
  const [duration, setDuration] = useState(180);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const active = faults.data?.items.find(
    (fault) => !["CLEARED", "EXPIRED", "FAILED"].includes(fault.status),
  );
  const activeIncidents = summary.data?.active_incidents ?? [];
  const role = control.session?.scopes[0]?.role;
  const authorized = ["RESEARCHER", "PROJECT_ADMIN", "SYSTEM_ADMIN"].includes(
    role ?? "",
  );
  const blocked = small || !authorized || !summary.data || Boolean(active) || activeIncidents.length > 0 || create.isPending || resetLab.isPending;
  const selectedPayload =
    payloads.find((payload) => payload.id === selected) ?? payloads[0];
  const requestBody = {
    scenario: selectedPayload.id,
    scenario_kind: selectedPayload.scenarioKind,
    target_route: selectedPayload.targetRoute,
    target_instance: selectedPayload.targetInstance,
    duration_seconds: duration,
  };

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
        brief="Choose from ten built-in payload scenarios, review the request and expected analysis, then inject one at a time. Faults are bounded and auto-expire; ground truth never becomes classifier evidence."
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
        <>
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
            {active.applied_at && (
              <div className="notice info">
                <Timer size={15} />
                <span>
                  <strong>MTTR counter:</strong>{" "}
                  {Math.max(0, Math.floor((now - new Date(active.applied_at).getTime()) / 1000))}s since fault activation.
                </span>
              </div>
            )}
            <button
              className="button danger"
              type="button"
              disabled={small || clear.isPending || active.status === "CLEAR_REQUESTED"}
              onClick={() => clear.mutate(active)}
            >
              {clear.isPending || active.status === "CLEAR_REQUESTED"
                ? "Reset requested · waiting for cleanup…"
                : "Reset scenario and restore traffic"}
            </button>
          </div>
          <p className="microcopy">
            Reset clears the injected backend fault. If the controller quarantined a route or instance, it restores traffic through its probe and staged verification gates. The incident and audit history remain available for review.
          </p>
          {clear.isError && (
            <div className="notice warning">
              <AlertTriangle size={15} />
              <span>{clear.error.message}</span>
            </div>
          )}
        </Panel>
        <Panel title="Autonomous decision timeline" kicker="Fast-path lifecycle">
          <ol className="event-timeline" aria-label="Autonomous decision timeline">
            {[
              ["ANOMALY_DETECTED", "HAProxy Runtime EWMA crossed the bounded threshold."],
              ["WEIGHT_ATTENUATED_TO_20%", "The worker recommends reversible attenuation after hysteresis."],
              ["STABILIZED", "Peer capacity and route error rate remain inside safety bounds."],
              ["CANARY_RECOVERY", "Recovery advances through staged weights after cooldown."],
            ].map(([label, detail], index) => (
              <li key={label} className={active && index === 0 ? "complete" : "neutral"}>
                <span className="timeline-dot" aria-hidden="true" />
                <time>{active ? (index === 0 ? "observed" : "pending") : "armed"}</time>
                <div><strong>{label}</strong><p>{detail}</p></div>
              </li>
            ))}
          </ol>
        </Panel>
        </>
      )}
      {activeIncidents.length > 0 && (
        <div className="notice warning">
          <AlertTriangle size={16} />
          <span>
            <strong>{activeIncidents.length} incident{activeIncidents.length === 1 ? " is" : "s are"} still active.</strong>{" "}
            The console pauses new injections while any incident is active. The worker may also defer actions during recovery or when a route failure still needs review. Resolve or reset the current state before the next scenario.
            <div className="fault-run-controls">
              <button
                className="button danger"
                type="button"
                disabled={!authorized || resetLab.isPending}
                onClick={() => resetLab.mutate()}
              >
                {resetLab.isPending ? "Reset requested…" : "Reset to all green"}
              </button>
            </div>
          </span>
        </div>
      )}
      {resetLab.isError && (
        <div className="notice warning"><AlertTriangle size={15} /><span>{resetLab.error.message}</span></div>
      )}
      {!summary.data && (
        <div className="notice warning">
          <AlertTriangle size={15} />
          <span>Waiting for current incident state before enabling injection. {summary.isError ? summary.error.message : ""}</span>
        </div>
      )}
      <div
        className="fault-scenario-grid"
        role="radiogroup"
        aria-label="Bounded fault scenario"
      >
        {payloads.map((scenario) => (
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
      <Panel title="Selected payload request" kicker="Recorded LAB API request">
        <p className="microcopy">
          This request is processed by the local Fault Lab and applied to the
          Compose demo backends. It does not send traffic to a public website.
        </p>
        <pre className="fault-payload-preview"><code>{JSON.stringify(requestBody, null, 2)}</code></pre>
      </Panel>
      <Panel title="Selected simulator details" kicker="Expected analysis and recovery">
        <KeyValueGrid
          items={[
            { label: "Payload ID", value: selectedPayload.id, mono: true },
            { label: "Fault type", value: selectedPayload.scenarioKind, mono: true },
            { label: "Expected classification", value: selectedPayload.classification },
            { label: "Controller response", value: selectedPayload.controllerBehavior },
            { label: "Recovery after clear / expiry", value: selectedPayload.recoveryBehavior },
          ]}
        />
      </Panel>
      <Panel title="Inject selected payload" kicker="Explicit target and expiry">
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
              create.mutate({
                scenario: selectedPayload.id,
                scenarioKind: selectedPayload.scenarioKind,
                targetRoute: selectedPayload.targetRoute,
                targetInstance: selectedPayload.targetInstance,
                durationSeconds: duration,
              })
            }
          >
            {create.isPending ? "Requesting fault…" : "Inject selected fault"}
          </button>
        </div>
        {!authorized && (
          <p className="microcopy">Your role is read-only for LAB faults.</p>
        )}
        {activeIncidents.length > 0 && (
          <p className="microcopy">Injection is paused because an incident is active. Use Reset to all green above, then wait for the incident count to clear.</p>
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
                <th>Fault type</th>
                <th>Target</th>
                <th>Applied</th>
                <th>Duration</th>
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
                    <code>{fault.scenario_kind}</code>
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
                  <td>{fault.duration_seconds}s</td>
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

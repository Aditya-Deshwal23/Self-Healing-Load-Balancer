"use client";

import Link from "next/link";
import {
  Check,
  CircleDashed,
  ExternalLink,
  FileDown,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useDecisionTrace, useIncidents, useRecovery } from "@/lib/api/operations";
import { buildIncidentAnalysisReport } from "@/lib/reports/incident-analysis-report";
import { downloadTextFile } from "@/lib/client-download";
import {
  KeyValueGrid,
  PageHeader,
  Panel,
  StateMessage,
  StatusTag,
} from "@/components/ui";

function tone(value: string) {
  if (["RESOLVED", "EFFECTIVE", "HEALTHY", "COMMITTED"].includes(value))
    return "success" as const;
  if (["FAILED", "HARMFUL", "ROLLBACK_FAILED"].includes(value))
    return "danger" as const;
  if (
    ["OPEN", "MITIGATING", "VERIFYING", "RECOVERING", "NEEDS_REVIEW"].includes(
      value,
    )
  )
    return "warning" as const;
  return "neutral" as const;
}

function short(value: string) {
  return value.slice(0, 8);
}
function formatJson(value: unknown) {
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

export function LiveIncidents({
  incidentId,
  traceOnly = false,
}: {
  incidentId?: string;
  traceOnly?: boolean;
}) {
  const list = useIncidents();
  const selectedId = incidentId ?? list.data?.items[0]?.id;
  const trace = useDecisionTrace(selectedId);
  const recoveryDetail = useRecovery(trace.data?.recovery?.id);
  const activeCount = (list.data?.items ?? []).filter((item) =>
    ["OPEN", "MITIGATING", "VERIFYING", "RECOVERING", "NEEDS_REVIEW"].includes(item.status),
  ).length;

  if (list.isLoading)
    return (
      <StateMessage state="loading" title="Loading durable incidents…">
        Reading classifications and evidence certificates from PostgreSQL.
      </StateMessage>
    );
  if (list.isError || !list.data)
    return (
      <StateMessage state="failure" title="Incidents are unavailable.">
        No fixture incidents were substituted.
      </StateMessage>
    );

  if (!selectedId || (!traceOnly && !incidentId)) {
    if (!list.data.items.length)
      return (
        <>
          <PageHeader
            eyebrow="Incidents"
            title="No incidents recorded"
            brief="The current LAB history is empty. Fault Lab scenarios create durable incidents when real evidence supports a classification."
          />
          <StateMessage state="empty" title="Healthy incident queue">
            Nothing requires review.
          </StateMessage>
        </>
      );
  }

  if (selectedId && (traceOnly || incidentId)) {
    if (trace.isLoading)
      return (
        <StateMessage state="loading" title="Building Decision Trace…">
          Joining evidence, classification, safety, action, readback,
          verification, and recovery records.
        </StateMessage>
      );
    if (trace.isError || !trace.data)
      return (
        <StateMessage state="failure" title="Decision Trace unavailable.">
          The selected durable incident could not be loaded.
          {trace.error instanceof Error ? ` API error: ${trace.error.message}` : ""}
        </StateMessage>
      );
    const data = trace.data;
    const classification = data.classifications.at(-1);
    const metricSnapshot = data.evidence?.metrics as {
      memberships?: Record<string, { samples?: number; errors?: number; error_rate?: number | null; status_codes?: Record<string, number>; p95_ms?: number | null }>;
    } | undefined;
    const membershipEvidence = metricSnapshot?.memberships ?? {};
    const probeSnapshot = data.evidence?.probes as Record<string, { reachable?: boolean; application_ok?: boolean; status?: number | null }> | undefined;
    const targetRoute = data.incident.target.route;
    const targetInstance = data.incident.target.instance;
    const targetKey = targetRoute && targetInstance ? `${targetRoute}/${targetInstance}` : null;
    const targetEvidence = targetKey ? membershipEvidence[targetKey] : undefined;
    const targetProbe = targetKey ? probeSnapshot?.[targetKey] : undefined;
    const classExplanation: Record<string, string> = {
      UNKNOWN: "The evidence is incomplete or conflicting. The controller retains the last confirmed routing state and cannot make a destructive change.",
      ROUTE_INSTANCE_DEGRADED: "This route/backend pair has elevated 5xx responses or a failed direct probe, but the independent evidence does not prove that isolating this one membership is safe.",
      ROUTE_INSTANCE_FAILURE: "Evidence isolates the failure to one route on one backend. The controller can consider changing that exact pool membership while checking that peers remain safe.",
      INSTANCE_DOWN: "Direct probes failed across every registered route on this physical instance. The controller scopes the response to this instance’s route memberships and checks capacity once.",
      SHARED_ROUTE_FAILURE: "The same route is failing across physical instances. The evidence does not support ejecting one backend as the cause, so broad removal is prohibited.",
      HEALTHY: "The latest evidence is within bounds and does not support an intervention.",
    };
    const targetErrorPercent = targetEvidence?.error_rate == null ? null : targetEvidence.error_rate * 100;
    const noActionCandidate = data.certificate?.candidate_actions.find((item) => item.unit === "NO_ACTION");
    const candidate = data.certificate?.candidate_actions ?? [];
    const confirmed = data.action?.attempts?.some((item) =>
      ["CONFIRMED", "ACKNOWLEDGEMENT_LOST_CONFIRMED"].includes(item.status),
    );
    const instanceRecoveryComplete =
      data.action?.kind === "INSTANCE_QUARANTINE" &&
      data.verification?.result === "EFFECTIVE" &&
      data.action.attempts.some(
        (item) =>
          item.operation === "restore_instance_after_probe_gate" &&
          item.status === "CONFIRMED",
      );
    const report = buildIncidentAnalysisReport(
      data,
      recoveryDetail.data ?? null,
    );
    const stages = [
      {
        name: "Evidence",
        ready: Boolean(data.evidence),
        summary: data.evidence
          ? `${Math.round(data.evidence.completeness * 100)}% complete · ${data.evidence.conflicts.length} conflicts`
          : "No complete window",
      },
      {
        name: "Scope",
        ready: Boolean(classification),
        summary: classification?.final_class ?? "Not classified",
      },
      {
        name: "Safety",
        ready: Boolean(data.certificate),
        summary: data.certificate
          ? "Capacity and preservation inputs captured"
          : "Not permitted",
      },
      {
        name: "Action",
        ready: Boolean(data.action),
        summary: data.action
          ? `${data.action.lifecycle} · ${data.action.target.backend}/${data.action.target.server}`
          : "No destructive action",
      },
      {
        name: "Readback",
        ready: Boolean(confirmed),
        summary: confirmed
          ? "Observed state confirmed"
          : "No confirmed Runtime mutation",
      },
      {
        name: "Verification",
        ready: Boolean(data.verification),
        summary: data.verification?.result ?? "Not started",
      },
      {
        name: "Recovery",
        ready: data.recovery?.status === "COMPLETED" || instanceRecoveryComplete,
        summary: data.recovery
          ? `${data.recovery.current_stage} · ${data.recovery.status}`
          : instanceRecoveryComplete
            ? "3 all-route probes passed · baseline restored · readback confirmed"
            : data.action?.kind === "INSTANCE_QUARANTINE"
              ? "Waiting for 3 consecutive healthy all-route probes"
              : "Not started",
      },
    ];
    return (
      <div className="page-stack live-trace-page">
        <PageHeader
          eyebrow="Incident / Decision Trace"
          title={data.incident.summary}
          brief={
            <>
              The trace distinguishes what the evidence supports from what the
              safety policy permitted. An unsupported or UNKNOWN scope never
              becomes a Runtime mutation.
            </>
          }
          meta={
            <>
              <StatusTag tone={tone(data.incident.status)}>
                {data.incident.status}
              </StatusTag>
              <span>
                {data.incident.target.route
                  ? `GET /${data.incident.target.route}`
                  : "All registered routes"}
                {data.incident.target.instance
                  ? ` × ${data.incident.target.instance}`
                  : " × all instances"}
              </span>
              <code>{short(data.incident.id)}</code>
              <span>{new Date(data.incident.opened_at).toLocaleString()}</span>
            </>
          }
          actions={
            <>
              <button
                className="button primary"
                type="button"
                disabled={Boolean(data.recovery && recoveryDetail.isLoading)}
                onClick={() =>
                  downloadTextFile(
                    report.filename,
                    report.content,
                    "text/markdown;charset=utf-8",
                  )
                }
              >
                <FileDown size={15} />
                {data.recovery && recoveryDetail.isLoading
                  ? "Loading recovery details…"
                  : "Download analysis report"}
              </button>
              <Link className="button secondary" href="/app/incidents">
                All incidents
              </Link>
            </>
          }
        />
        <ol className="trace-spine" aria-label="Evidence to recovery workflow">
          {stages.map((stage) => (
            <li className={stage.ready ? "ready" : "waiting"} key={stage.name}>
              {stage.ready ? <Check size={14} /> : <CircleDashed size={14} />}
              <span>
                <strong>{stage.name}</strong>
                <small>{stage.summary}</small>
              </span>
            </li>
          ))}
        </ol>
        <section className="decision-reading" aria-labelledby="decision-reading-title">
          <header>
            <span className="section-kicker">Plain-language decision</span>
            <h2 id="decision-reading-title">What the controller concluded</h2>
            <p>{classExplanation[classification?.final_class ?? "UNKNOWN"]}</p>
          </header>
          <div className="decision-reading-grid">
            <article>
              <span>Request evidence</span>
              <strong>{targetEvidence ? `${targetEvidence.errors ?? 0} errors / ${targetEvidence.samples ?? 0} requests` : "No single target membership"}</strong>
              <small>{targetErrorPercent === null ? "No target-specific error rate" : `${targetErrorPercent.toFixed(1)}% 5xx · p95 ${targetEvidence?.p95_ms?.toFixed(1) ?? "—"} ms`}</small>
            </article>
            <article>
              <span>Independent probe</span>
              <strong>{targetProbe ? targetProbe.application_ok ? "Passed" : "Failed" : "Not scoped"}</strong>
              <small>{targetProbe ? `${targetProbe.reachable ? "Reachable" : "Unreachable"}${targetProbe.status ? ` · HTTP ${targetProbe.status}` : ""}` : "Classification applies to multiple cells or probe evidence is unavailable."}</small>
            </article>
            <article>
              <span>Routing outcome</span>
              <strong>{data.action ? `${data.action.lifecycle} · ${data.action.target.backend}/${data.action.target.server}` : "No HAProxy change"}</strong>
              <small>{data.action ? String(data.action.expected_effect) : String(noActionCandidate?.reason ?? "No action was permitted for this classification.")}</small>
            </article>
          </div>
          <details>
            <summary>How to read the thresholds and scope checks</summary>
            <p>Request errors are counted per route × instance membership. Elevated errors above 10% create a warning. A route-only isolation decision needs at least 50% errors and 6 target samples, a failed target probe, healthy same-route peers, and healthy sibling routes on the same instance. Capacity and peer-queue checks run before any Runtime mutation. A physical instance shared by several pools is counted once for capacity, while each HAProxy membership remains independently changeable.</p>
          </details>
        </section>
        <div className="trace-grid">
          <Panel
            title="Evidence supports"
            kicker="Observed scope"
            className="evidence-supports"
          >
            {data.evidence ? (
              <>
                <KeyValueGrid
                  items={[
                    {
                      label: "Window",
                      value: `${new Date(data.evidence.started_at).toLocaleTimeString()}–${new Date(data.evidence.ended_at).toLocaleTimeString()}`,
                      mono: true,
                    },
                    {
                      label: "Completeness",
                      value: `${Math.round(data.evidence.completeness * 100)}%`,
                    },
                    {
                      label: "Conflicts",
                      value: String(data.evidence.conflicts.length),
                    },
                    {
                      label: "Fingerprint",
                      value: data.fingerprint
                        ? short(data.fingerprint.hash)
                        : "Unavailable",
                      mono: true,
                    },
                  ]}
                />
                <details>
                  <summary>Bounded evidence window</summary>
                  <pre>
                    {formatJson({
                      metrics: data.evidence.metrics,
                      probes: data.evidence.probes,
                      conflicts: data.evidence.conflicts,
                    })}
                  </pre>
                </details>
              </>
            ) : (
              <StateMessage state="unknown" title="No complete evidence window">
                Classification cannot authorize a mutation.
              </StateMessage>
            )}
          </Panel>
          <Panel
            title="Safety permitted"
            kicker="Independent action gate"
            className="safety-permitted"
          >
            {data.certificate ? (
              <>
                <KeyValueGrid
                  items={[
                    {
                      label: "Certificate",
                      value: short(data.certificate.hash),
                      mono: true,
                    },
                    {
                      label: "Controller class",
                      value: classification?.final_class ?? "—",
                      mono: true,
                    },
                    {
                      label: "Confidence",
                      value: classification?.confidence.toFixed(2) ?? "—",
                    },
                    {
                      label: "Completeness",
                      value: classification
                        ? `${Math.round(classification.completeness * 100)}%`
                        : "—",
                    },
                  ]}
                />
                <details open>
                  <summary>Candidate actions and rejection reasons</summary>
                  <ul className="candidate-list">
                    {candidate.map((item, index) => {
                      const row = item as Record<string, unknown>;
                      const allowed = Boolean(
                        row.selected ??
                        row.allowed ??
                        row.result === "selected",
                      );
                      return (
                        <li key={index}>
                          {allowed ? (
                            <ShieldCheck size={15} />
                          ) : (
                            <XCircle size={15} />
                          )}
                          <span>
                            <strong>
                              {String(
                                row.action ??
                                  row.kind ??
                                  row.unit ??
                                  "Candidate",
                              )}
                            </strong>
                            <small>
                              {String(
                                row.reason ??
                                  row.rejection_reason ??
                                  (allowed
                                    ? "Selected by deterministic policy"
                                    : "Rejected"),
                              )}
                            </small>
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </details>
              </>
            ) : (
              <StateMessage
                state="unknown"
                title="Safety did not permit an action"
              >
                This is the expected non-destructive result for UNKNOWN and
                unsupported evidence.
              </StateMessage>
            )}
          </Panel>
        </div>
        <Panel title="Endpoint and code context" kicker="Synthetic LAB handler">
          <KeyValueGrid
            items={[
              {
                label: "Endpoint",
                value: data.incident.target.route
                  ? `GET /${data.incident.target.route}`
                  : "GET /public, /auth, /catalog, /checkout",
                mono: true,
              },
              {
                label: "Backend instance",
                value: data.incident.target.instance ?? "All registered instances",
                mono: true,
              },
              { label: "Source file", value: "demo-backend/app.py · DemoHandler._serve" },
              {
                label: "Current LAB fault",
                value: data.lab_fault?.scenario ?? "No correlated fault record",
              },
            ]}
          />
          <pre><code>{`failed = self._fault_affects(route, fault)
gray = bool(fault and fault["kind"] == "gray_failure")
if gray:
    time.sleep(0.35)
    failed = random.random() < 0.025
status = (
    HTTPStatus.INTERNAL_SERVER_ERROR if failed and gray
    else HTTPStatus.SERVICE_UNAVAILABLE if failed
    else HTTPStatus.OK
)`}</code></pre>
          <p className="microcopy">
            This project code deliberately injects the LAB fault; it is not evidence of a bug in a real application endpoint. For these scenarios, clear the fault or use Reset to all green, then verify health and readback. The console can show real production source code only after a source repository is connected; it cannot safely invent a patch for code it cannot inspect.
          </p>
        </Panel>
        <Panel
          title="Durable action, readback, and outcome"
          kicker="Mutation is not success"
        >
          {data.action ? (
            <div className="trace-action-grid">
              <div>
                <span>Target</span>
                <strong>
                  <code>
                    {data.action.target.backend}/{data.action.target.server}
                  </code>
                </strong>
              </div>
              <div>
                <span>Lifecycle</span>
                <StatusTag tone={tone(data.action.lifecycle)}>
                  {data.action.lifecycle}
                </StatusTag>
              </div>
              <div>
                <span>Requested state</span>
                <strong>
                  {String(
                    data.action.requested_state.admin_state ??
                      data.action.requested_state.admin,
                  )}{" "}
                  · w {String(data.action.requested_state.weight)}
                </strong>
              </div>
              <div>
                <span>Runtime readback</span>
                <strong>{confirmed ? "Confirmed" : "Not confirmed"}</strong>
              </div>
              <div>
                <span>Verification</span>
                <StatusTag tone={tone(data.verification?.result ?? "PENDING")}>
                  {data.verification?.result ?? "COLLECTING"}
                </StatusTag>
              </div>
              <div>
                <span>Recovery</span>
                <strong>
                  {data.recovery
                    ? `${data.recovery.current_stage} · ${data.recovery.status}`
                    : instanceRecoveryComplete
                      ? "Probe gate passed · baseline restored"
                      : data.action?.kind === "INSTANCE_QUARANTINE"
                        ? "Waiting for 3 healthy probes on every route"
                        : "Not started"}
                </strong>
              </div>
              {data.recovery && (
                <Link href={`/app/reintegration?run=${data.recovery.id}`}>
                  Open staged recovery details <ExternalLink size={13} />
                </Link>
              )}
              <Link href={`/app/actions?action=${data.action.id}`}>
                Open attempts and exact readback <ExternalLink size={13} />
              </Link>
            </div>
          ) : (
            <div className="calm-empty">
              <CircleDashed size={18} />
              <div>
                <strong>No action selected</strong>
                <p>The controller retained the last confirmed routing state.</p>
              </div>
            </div>
          )}
        </Panel>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Incidents"
        title="Incident history"
        brief={
          activeCount
            ? `${activeCount} active incident${activeCount === 1 ? "" : "s"} require attention. Resolved incidents remain below as history.`
            : "No active incidents. Resolved incidents remain below as history; open one to inspect its decision and evidence."
        }
      />
      <section className="panel table-panel">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Classification</th>
                <th>Target endpoint</th>
                <th>Summary</th>
                <th>Opened</th>
                <th>Trace</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <StatusTag tone={tone(item.status)}>
                      {item.status}
                    </StatusTag>
                  </td>
                  <td>
                    <code>{item.classification}</code>
                  </td>
                  <td>
                    <code>
                      {item.target.route ? `GET /${item.target.route}` : "all routes"}
                      {item.target.instance ? ` × ${item.target.instance}` : " × all instances"}
                    </code>
                  </td>
                  <td>
                    <strong>{item.summary}</strong>
                    <small>
                      <code>{short(item.id)}</code> · {item.severity}
                    </small>
                  </td>
                  <td>
                    <time>{new Date(item.opened_at).toLocaleString()}</time>
                  </td>
                  <td>
                    <Link
                      className="inline-link"
                      href={`/app/incidents?incident=${item.id}&trace=1`}
                    >
                      Decision Trace
                      <ExternalLink size={13} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

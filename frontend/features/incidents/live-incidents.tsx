"use client";

import Link from "next/link";
import {
  Check,
  CircleDashed,
  ExternalLink,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useDecisionTrace, useIncidents } from "@/lib/api/operations";
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
        </StateMessage>
      );
    const data = trace.data;
    const classification = data.classifications.at(-1);
    const candidate = data.certificate?.candidate_actions ?? [];
    const confirmed = data.action?.attempts?.some((item) =>
      ["CONFIRMED", "ACKNOWLEDGEMENT_LOST_CONFIRMED"].includes(item.status),
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
        ready: data.recovery?.status === "COMPLETED",
        summary: data.recovery
          ? `${data.recovery.current_stage} · ${data.recovery.status}`
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
              <code>{short(data.incident.id)}</code>
              <span>{new Date(data.incident.opened_at).toLocaleString()}</span>
            </>
          }
          actions={
            <Link className="button secondary" href="/app/incidents">
              All incidents
            </Link>
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
                    : "Not started"}
                </strong>
              </div>
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
        title="Durable incident history"
        brief="Every item is generated from a bounded real evidence window. Open a row to inspect the controller’s exact reasoning and non-selected hypotheses."
      />
      <section className="panel table-panel">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Classification</th>
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

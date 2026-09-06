"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CircleDashed,
  Clock3,
  ShieldCheck,
} from "lucide-react";
import { LiveRouteMatrix } from "@/features/traffic/live-matrix";
import { useDecisionTrace, useOperationalSummary } from "@/lib/api/operations";
import {
  PageHeader,
  Panel,
  ProgressBar,
  StateMessage,
  StatusTag,
} from "@/components/ui";

function percent(value: number | null | undefined, digits = 1) {
  return value === null || value === undefined
    ? "Not connected"
    : `${(value * 100).toFixed(digits)}%`;
}

function time(value: string | null | undefined) {
  return value
    ? new Date(value).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "Unavailable";
}

export function LiveCommandCenter() {
  const summary = useOperationalSummary();
  const activeIncident = summary.data?.active_incidents[0];
  const trace = useDecisionTrace(activeIncident?.id);

  if (summary.isLoading)
    return (
      <StateMessage state="loading" title="Assembling the operating picture…">
        Reading current evidence, durable incidents, and HAProxy state.
      </StateMessage>
    );
  if (summary.isError || !summary.data)
    return (
      <StateMessage
        state="failure"
        title="The live control plane is unavailable."
      >
        No simulated values were substituted. Confirm the API and worker are
        healthy.
      </StateMessage>
    );

  const data = summary.data;
  const action = trace.data?.action ?? data.current_action;
  const actionConfirmed = Boolean(
    action?.attempts?.some((item) =>
      ["CONFIRMED", "ACKNOWLEDGEMENT_LOST_CONFIRMED"].includes(item.status),
    ),
  );
  const actionDisplayState =
    action && !actionConfirmed && ["COMMITTED", "VERIFYING"].includes(action.lifecycle)
      ? "CONFIRMING"
      : action?.lifecycle;
  const verification = trace.data?.verification;
  const recovery = trace.data?.recovery;
  const classification = trace.data?.classifications.at(-1);
  const verificationDisplayState =
    verification && action && !actionConfirmed
      ? "CONFIRMING"
      : verification?.result;
  const healthy = !activeIncident && !data.current_action;

  return (
    <div className="live-command-center page-stack">
      <PageHeader
        eyebrow="Current operating picture"
        title={
          healthy
            ? "Traffic is healthy and routing state is aligned."
            : activeIncident.summary
        }
        brief={
          healthy ? (
            "All twelve predeclared route memberships are eligible. The rules-only worker is observing real request outcomes, direct probes, and HAProxy Runtime state."
          ) : (
            <>
              The controller scoped this event to{" "}
              <strong>{activeIncident.classification}</strong>. Evidence, safety
              approval, Runtime readback, and recovery remain independently
              inspectable.
            </>
          )
        }
        meta={
          <>
            <span>
              Evidence window ended{" "}
              {time(data.freshness.evidence_window_ended_at)}
            </span>
            <span>Completeness {percent(data.freshness.completeness, 0)}</span>
            <span>
              HAProxy readback {time(data.freshness.observed_state_at)}
            </span>
          </>
        }
        actions={
          activeIncident ? (
            <Link
              className="button primary"
              href={`/app/incidents?incident=${activeIncident.id}&trace=1`}
            >
              Decision Trace
              <ArrowRight size={15} />
            </Link>
          ) : undefined
        }
      />

      <section className="operational-strip" aria-label="Live traffic status">
        <div className="operational-item neutral">
          <span>Admitted traffic</span>
          <strong>
            {data.traffic.admitted_rps === null
              ? "Not connected"
              : `${data.traffic.admitted_rps.toFixed(1)} req/s`}
          </strong>
          <small>bounded observation window</small>
        </div>
        <div
          className={`operational-item ${(data.traffic.success_ratio ?? 0) >= 0.99 ? "success" : data.traffic.success_ratio === null ? "neutral" : "danger"}`}
        >
          <span>Successful requests</span>
          <strong>{percent(data.traffic.success_ratio)}</strong>
          <small>all route memberships</small>
        </div>
        <div
          className={`operational-item ${(data.traffic.healthy_capacity_percent ?? 0) >= 0.66 ? "success" : "warning"}`}
        >
          <span>Eligible capacity</span>
          <strong>
            {data.traffic.healthy_capacity_percent === null
              ? "Not connected"
              : `${data.traffic.healthy_capacity_percent.toFixed(0)}%`}
          </strong>
          <small>physical capacity counted once</small>
        </div>
        <div
          className={`operational-item ${data.active_incidents.length ? "danger" : "success"}`}
        >
          <span>Active incidents</span>
          <strong>{data.active_incidents.length}</strong>
          <small>
            {data.active_incidents.length ? "requires attention" : "none open"}
          </small>
        </div>
      </section>

      <div className="command-primary-grid">
        <section
          className="panel matrix-command-panel"
          aria-label="Live route by instance matrix"
        >
          <LiveRouteMatrix compact />
        </section>
        <Panel
          title={activeIncident ? "Current decision" : "Control loop"}
          kicker={
            activeIncident ? "Decision Trace" : "Last complete reconciliation"
          }
          className="live-decision-panel"
          action={
            <StatusTag tone={activeIncident ? "warning" : "success"}>
              {activeIncident?.status ?? data.worker.status}
            </StatusTag>
          }
        >
          {activeIncident && trace.data ? (
            <>
              <div className="decision-class">
                <div>
                  <span>Operational class</span>
                  <strong>{activeIncident.classification}</strong>
                </div>
                <div className="decision-bounds">
                  <span>
                    <strong>
                      {classification?.confidence.toFixed(2) ?? "—"}
                    </strong>{" "}
                    rules confidence
                  </span>
                  <span>
                    <strong>
                      {classification
                        ? percent(classification.completeness, 0)
                        : "—"}
                    </strong>{" "}
                    complete
                  </span>
                </div>
              </div>
              <ol
                className="live-decision-chain"
                aria-label="Current healing workflow"
              >
                {[
                  [
                    "Evidence",
                    Boolean(trace.data.evidence),
                    "Window and direct probes",
                  ],
                  [
                    "Scope",
                    Boolean(classification),
                    activeIncident.classification,
                  ],
                  [
                    "Safety",
                    Boolean(trace.data.certificate),
                    trace.data.certificate
                      ? "Constraints evaluated"
                      : "Waiting",
                  ],
                  [
                    "Action",
                    Boolean(action),
                    actionDisplayState ?? "Not selected",
                  ],
                  [
                    "Readback",
                    Boolean(
                      action?.attempts?.some((item) =>
                        [
                          "CONFIRMED",
                          "ACKNOWLEDGEMENT_LOST_CONFIRMED",
                        ].includes(item.status),
                      ),
                    ),
                    "HAProxy observed",
                  ],
                  [
                    "Verification",
                    Boolean(verification),
                    verificationDisplayState ?? "Collecting",
                  ],
                  [
                    "Recovery",
                    recovery?.status === "COMPLETED",
                    recovery?.current_stage ?? "Not started",
                  ],
                ].map(([label, complete, detail]) => (
                  <li
                    className={complete ? "complete" : "pending"}
                    key={String(label)}
                  >
                    {complete ? (
                      <Check size={13} />
                    ) : (
                      <CircleDashed size={13} />
                    )}
                    <span>
                      <strong>{label}</strong>
                      <small>{detail}</small>
                    </span>
                  </li>
                ))}
              </ol>
              {verification && (
                <ProgressBar
                  value={verification.sample_count}
                  max={Math.max(verification.sample_count, 20)}
                  label={`Verification samples · ${verificationDisplayState}`}
                  tone={
                    verificationDisplayState === "EFFECTIVE" ? "success" : "warning"
                  }
                />
              )}
              <Link
                className="inline-link decision-open"
                href={`/app/incidents?incident=${activeIncident.id}&trace=1`}
              >
                Inspect evidence and rejected scopes
                <ArrowRight size={14} />
              </Link>
            </>
          ) : (
            <div className="healthy-loop-state">
              <ShieldCheck size={28} />
              <div>
                <strong>No active intervention</strong>
                <p>
                  Generation {data.worker.generation ?? "—"} is observing. The
                  most recent complete evidence window contains no actionable
                  failure.
                </p>
              </div>
              <dl>
                <div>
                  <dt>Worker</dt>
                  <dd>{data.worker.status}</dd>
                </div>
                <div>
                  <dt>Last heartbeat</dt>
                  <dd>{time(data.worker.last_heartbeat_at)}</dd>
                </div>
                <div>
                  <dt>Automation</dt>
                  <dd>
                    {data.environment.automation_frozen
                      ? "Frozen"
                      : data.environment.mode}
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </Panel>
      </div>

      <div className="command-secondary-grid">
        <Panel
          title="Current action and verification"
          kicker="Durable lifecycle"
        >
          {action ? (
            <div className="current-action-compact">
              <div>
                <span>Exact target</span>
                <strong>
                  <code>
                    {action.target.backend}/{action.target.server}
                  </code>
                </strong>
              </div>
              <div>
                <span>Lifecycle</span>
                <strong>{actionDisplayState}</strong>
              </div>
              <div>
                <span>Requested</span>
                <strong>
                  {String(action.requested_state.admin_state ?? action.requested_state.admin)} · w{" "}
                  {String(action.requested_state.weight)}
                </strong>
              </div>
              <div>
                <span>Verification</span>
                <strong>
                  {verificationDisplayState ??
                    (actionConfirmed
                      ? "Collecting real samples"
                      : "Confirming observed state")}
                </strong>
              </div>
              <Link href={`/app/actions?action=${action.id}`}>
                Open durable action <ArrowRight size={14} />
              </Link>
            </div>
          ) : (
            <div className="calm-empty">
              <Clock3 size={18} />
              <div>
                <strong>No action in progress</strong>
                <p>
                  The worker will persist intent before any Runtime mutation.
                </p>
              </div>
            </div>
          )}
        </Panel>
        <Panel title="What happens next" kicker="Recovery">
          {recovery ? (
            <div className="current-action-compact">
              <div>
                <span>Run</span>
                <strong>
                  <code>{recovery.id.slice(0, 8)}</code>
                </strong>
              </div>
              <div>
                <span>Stage</span>
                <strong>{recovery.current_stage}</strong>
              </div>
              <div>
                <span>Last verified</span>
                <strong>{recovery.last_verified_stage}</strong>
              </div>
              <div>
                <span>Status</span>
                <strong>{recovery.status}</strong>
              </div>
              <Link href={`/app/reintegration?run=${recovery.id}`}>
                Inspect staged recovery <ArrowRight size={14} />
              </Link>
            </div>
          ) : (
            <div className="calm-empty">
              <ShieldCheck size={18} />
              <div>
                <strong>No recovery run</strong>
                <p>
                  A quarantined membership progresses only after the fault
                  clears and each stage gathers real samples.
                </p>
              </div>
            </div>
          )}
        </Panel>
        {activeIncident?.classification === "UNKNOWN" && (
          <Panel title="Manual review" kicker="Non-destructive outcome">
            <div className="notice warning">
              <AlertTriangle size={16} />
              <span>
                <strong>Evidence is incomplete or conflicting.</strong> UNKNOWN
                never authorizes a routing mutation; the last confirmed state is
                retained.
              </span>
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}

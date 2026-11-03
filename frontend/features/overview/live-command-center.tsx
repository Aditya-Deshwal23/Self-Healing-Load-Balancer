"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CircleDashed,
  Clock3,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { LiveRouteMatrix } from "@/features/traffic/live-matrix";
import { TrafficHistoryCharts } from "@/features/overview/traffic-history-charts";
import { useDecisionTrace, useOperationalSummary, useResetLab } from "@/lib/api/operations";
import { useControlPlane } from "@/lib/use-control-plane";
import {
  PageHeader,
  Panel,
  ProgressBar,
  StateMessage,
  StatusTag,
  LiveConnectionStatus,
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
  const [statsAccessIsLocal, setStatsAccessIsLocal] = useState<boolean | null>(null);
  const control = useControlPlane();
  const summary = useOperationalSummary();
  const resetLab = useResetLab();
  useEffect(() => {
    const hostname = window.location.hostname.replace(/^\[|\]$/g, "").toLowerCase();
    setStatsAccessIsLocal(["localhost", "127.0.0.1", "::1"].includes(hostname));
  }, []);
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
  const verification = trace.data?.verification;
  const recovery = trace.data?.recovery;
  const classification = trace.data?.classifications.at(-1);
  const healthy = !activeIncident;
  const role = control.session?.scopes[0]?.role;
  const canResetLab = ["RESEARCHER", "PROJECT_ADMIN", "SYSTEM_ADMIN"].includes(role ?? "");
  const resetPending = resetLab.isPending || ["REQUESTED", "RUNNING"].includes(data.lab_reset?.status ?? "");

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
            <LiveConnectionStatus
              state={control.streamState}
              lastEventAt={control.lastEventAt}
            />
          </>
        }
        actions={
          <>
            {statsAccessIsLocal ? (
              <a
                className="button secondary"
                href="http://127.0.0.1:8404/stats"
                target="_blank"
                rel="noreferrer"
                title="Open HAProxy live statistics on this host."
              >
                HAProxy stats
                <ArrowRight size={15} />
              </a>
            ) : (
              <button
                className="button secondary"
                type="button"
                disabled
                title={statsAccessIsLocal === null
                  ? "Checking whether this browser is on the control host."
                  : "HAProxy stats are bound to 127.0.0.1 on the control host. Open this dashboard on that host to use the link."}
              >
                {statsAccessIsLocal === null ? "Checking HAProxy stats…" : "HAProxy stats · host-local"}
              </button>
            )}
            {data.environment.kind === "LAB" && (
              <button
                className="button secondary"
                type="button"
                disabled={!canResetLab || resetPending || control.state !== "live"}
                onClick={() => resetLab.mutate()}
                title="Clear LAB faults and restore all healthy memberships to their registered baseline after direct probes pass."
              >
                <RotateCcw size={15} />
                {resetPending ? "Resetting to baseline…" : "Reset to all green"}
              </button>
            )}
            {activeIncident && (
              <Link
                className="button primary"
                href={`/app/incidents?incident=${activeIncident.id}&trace=1`}
              >
                Decision Trace
                <ArrowRight size={15} />
              </Link>
            )}
          </>
        }
      />

      {data.environment.kind === "LAB" && !canResetLab && (
        <p className="microcopy">Reset is available to authorized LAB operator roles.</p>
      )}
      {resetLab.isError && (
        <div className="notice warning" role="alert">
          LAB reset could not be requested: {resetLab.error.message}
        </div>
      )}
      {data.lab_reset?.status === "NEEDS_REVIEW" && (
        <div className="notice warning" role="status">
          <div>
            LAB reset stopped at {String(data.lab_reset.result.phase ?? "a safety check")}.
            Direct probes or HAProxy readback did not pass, so traffic was not
            reported as restored. Fix the cause, then retry the reset.
            <details>
              <summary>Reset check details</summary>
              <pre>{JSON.stringify(data.lab_reset.result, null, 2)}</pre>
            </details>
          </div>
        </div>
      )}

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

      <TrafficHistoryCharts />

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
                    action?.lifecycle ?? "Not selected",
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
                    verification?.result ?? "Collecting",
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
                  label={`Verification samples · ${verification.result}`}
                  tone={
                    verification.result === "EFFECTIVE" ? "success" : "warning"
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
                <strong>{action.lifecycle}</strong>
              </div>
              <div>
                <span>Requested</span>
                <strong>
                  {String(action.requested_state.admin)} · w{" "}
                  {String(action.requested_state.weight)}
                </strong>
              </div>
              <div>
                <span>Verification</span>
                <strong>
                  {verification?.result ?? "Collecting real samples"}
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

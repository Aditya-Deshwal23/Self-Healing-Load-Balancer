"use client";

import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Ban,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDashed,
  FileCheck2,
  Filter,
  GitCompareArrows,
  History,
  LockKeyhole,
  Pause,
  Play,
  RotateCcw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Timer,
  Undo2,
} from "lucide-react";
import { useState } from "react";
import { useDemoSnapshot, type DemoSnapshot } from "@/lib/demo/provider";
import { csvRow, downloadTextFile } from "@/lib/client-download";
import { EvidenceChart } from "@/components/charts";
import {
  BlastRadiusMap,
  KeyValueGrid,
  PageHeader,
  Panel,
  ProgressBar,
  ReviewDialog,
  StateTriptych,
  StatusTag,
  Timeline,
} from "@/components/ui";
import type { ActionLifecycle, FailureClass } from "@/lib/types";

function classTone(value: FailureClass) {
  if (value === "HEALTHY") return "success" as const;
  if (value === "UNKNOWN") return "warning" as const;
  return "danger" as const;
}

function lifecycleTone(value: ActionLifecycle) {
  if (value === "COMMITTED") return "success" as const;
  if (["NEEDS_REVIEW", "RESULT_UNKNOWN", "ROLLING_BACK"].includes(value))
    return "danger" as const;
  if (["VERIFYING", "PREPARED", "APPLIED", "STATE_CONFIRMED"].includes(value))
    return "warning" as const;
  return "neutral" as const;
}

export function IncidentListPage() {
  const { incidents } = useDemoSnapshot();
  const [filter, setFilter] = useState("all");
  const rows = incidents.filter(
    (item) =>
      filter === "all" ||
      item.status === filter ||
      item.classification === filter,
  );
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Response queue"
        title="Incidents"
        brief={
          <>
            Two incidents remain open. The checkout incident is verifying a
            bounded action; stale auth telemetry is classified UNKNOWN and
            requires human review.
          </>
        }
        meta={
          <>
            <span>
              Ordered by review need, active harm, verification, then recency
            </span>
            <span>Snapshot 22:09 IST</span>
          </>
        }
        actions={
          <button
            className="button secondary"
            type="button"
            disabled
            title="Saved views require the control API"
          >
            <Filter size={15} />
            Saved filters
          </button>
        }
      />
      <div className="list-toolbar">
        <label className="search-field">
          <Search size={15} />
          <span className="sr-only">Search incidents</span>
          <input placeholder="Search ID, route, backend, or class" />
        </label>
        <label>
          <span>View</span>
          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          >
            <option value="all">All incidents</option>
            <option value="NEEDS_REVIEW">Needs review</option>
            <option value="VERIFYING">Verifying</option>
            <option value="UNKNOWN">Unknown / low evidence</option>
            <option value="RESOLVED">Resolved</option>
          </select>
          <ChevronDown size={13} />
        </label>
      </div>
      <section className="panel table-panel" aria-label="Incident list">
        <div className="table-scroll">
          <table className="data-table incident-table">
            <thead>
              <tr>
                <th>Incident</th>
                <th>Class and scope</th>
                <th>Status</th>
                <th>Evidence</th>
                <th>First seen</th>
                <th>Owner</th>
                <th>
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((item) => (
                <tr key={item.id}>
                  <td>
                    <Link href={`/app/incidents/${item.id}`}>
                      <code>{item.id}</code>
                      <strong>{item.title}</strong>
                    </Link>
                  </td>
                  <td>
                    <StatusTag tone={classTone(item.classification)}>
                      {item.classification}
                    </StatusTag>
                    <small>{item.scope}</small>
                  </td>
                  <td>
                    <StatusTag
                      tone={
                        item.status === "RESOLVED"
                          ? "success"
                          : item.status === "NEEDS_REVIEW"
                            ? "danger"
                            : "warning"
                      }
                    >
                      {item.status}
                    </StatusTag>
                  </td>
                  <td>
                    <div className="completeness-cell">
                      <span>
                        <strong>{item.completeness}%</strong> complete
                      </span>
                      <span>
                        <strong>{item.confidence}%</strong> confidence
                      </span>
                    </div>
                  </td>
                  <td>
                    <time>{item.openedAt}</time>
                  </td>
                  <td>{item.owner}</td>
                  <td>
                    <Link
                      className="icon-button"
                      aria-label={`Open ${item.id}`}
                      href={`/app/incidents/${item.id}`}
                    >
                      <ChevronRight size={16} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!rows.length && (
          <div className="table-empty">
            <Search size={19} />
            <strong>No incidents match this filter.</strong>
            <button type="button" onClick={() => setFilter("all")}>
              Show all incidents
            </button>
          </div>
        )}
      </section>
      <div className="notice neutral">
        <LockKeyhole size={15} />
        <span>
          Bulk resolve is intentionally unavailable. Resolution requires
          verified recovery or an explicit evidence-backed operator outcome.
        </span>
      </div>
    </div>
  );
}

export function IncidentDetailsPage({ incidentId }: { incidentId?: string }) {
  const { action, errorSeries, incident, incidents } = useDemoSnapshot();
  const selectedIncident =
    incidents.find((item) => item.id === (incidentId ?? incident.id)) ??
    incident;
  if (selectedIncident.id !== incident.id)
    return <BoundedIncidentDetails selectedIncident={selectedIncident} />;
  return (
    <div className="page-stack incident-details-page">
      <PageHeader
        eyebrow={`${incident.id} · opened ${incident.openedAt}`}
        title={incident.title}
        brief={incident.brief}
        meta={
          <>
            <StatusTag tone="danger">{incident.severity}</StatusTag>
            <StatusTag tone="warning">{incident.status}</StatusTag>
            <span>{incident.scope}</span>
            <span>Last observed {incident.lastObserved}</span>
          </>
        }
        actions={
          <>
            <button
              className="button secondary"
              type="button"
              disabled
              title="Incident acknowledgement begins in a later phase"
            >
              Acknowledge
            </button>
            <Link
              className="button primary"
              href={`/app/incidents/${incident.id}/decision-trace`}
            >
              Open Decision Trace
              <ArrowRight size={15} />
            </Link>
          </>
        }
      />
      <section className="incident-summary-strip">
        <div>
          <span>Classification</span>
          <strong>{incident.classification}</strong>
          <small>rules resolver v4</small>
        </div>
        <div>
          <span>Confidence</span>
          <strong>{incident.confidence}%</strong>
          <small>not a safety permission</small>
        </div>
        <div>
          <span>Completeness</span>
          <strong>{incident.completeness}%</strong>
          <small>1 missing source</small>
        </div>
        <div>
          <span>Owner</span>
          <strong>{incident.owner}</strong>
          <small>{incident.correlationId}</small>
        </div>
      </section>
      <div className="two-column-layout incident-main-grid">
        <Panel
          title="Symptom timeline"
          kicker="Affected route and peer control"
        >
          <EvidenceChart
            title="Checkout error family"
            summary="Checkout on Backend B diverged at 22:02. After the observed route-local drain, routed checkout traffic remained on healthy peers near 3%."
            data={errorSeries}
            unit="%"
            sampleCount={3428}
            yDomain={[0, 20]}
            actionAt="22:02"
            series={[
              { key: "value", label: "checkout/B", color: "var(--danger)" },
              {
                key: "peer",
                label: "checkout peers",
                color: "var(--accent-copper)",
                dashed: true,
              },
            ]}
          />
        </Panel>
        <Panel title="Scope evidence" kicker="Affected and preserved sets">
          <div className="scope-evidence-sets">
            <article className="affected">
              <span>Affected</span>
              <strong>
                <code>/checkout</code> × Backend B
              </strong>
              <p>
                Timeout and latency evidence diverged from aligned checkout
                peers.
              </p>
              <StatusTag tone="danger">428 pre-action samples</StatusTag>
            </article>
            <article className="preserved">
              <span>What stays healthy</span>
              <strong>
                <code>/public</code> · <code>/auth</code> ·{" "}
                <code>/catalog</code>
              </strong>
              <p>
                Same physical instance remained eligible and within aligned
                non-regression bounds.
              </p>
              <StatusTag tone="success">3 memberships preserved</StatusTag>
            </article>
          </div>
          <div className="notice warning">
            <AlertTriangle size={15} />
            <span>
              Auth telemetry on Backend C is stale. The conflict lowers
              completeness but does not erase healthy sibling evidence on
              Backend B.
            </span>
          </div>
        </Panel>
      </div>
      <Panel
        title="Decision summary"
        kicker="Evidence → scope → action → verification"
        action={
          <Link
            className="inline-link"
            href={`/app/incidents/${incident.id}/decision-trace`}
          >
            Explore full trace
            <ArrowRight size={14} />
          </Link>
        }
      >
        <div className="incident-decision-spine">
          <article>
            <Activity size={17} />
            <span>Evidence</span>
            <strong>6 bounded sources</strong>
            <small>freshness, samples, conflict retained</small>
          </article>
          <ArrowRight size={15} />
          <article>
            <GitCompareArrows size={17} />
            <span>Fingerprint</span>
            <strong>route-local divergence</strong>
            <small>same-instance routes counter wider scope</small>
          </article>
          <ArrowRight size={15} />
          <article>
            <ShieldCheck size={17} />
            <span>Safety</span>
            <strong>7/7 allowed</strong>
            <small>unique capacity +17 points above floor</small>
          </article>
          <ArrowRight size={15} />
          <article>
            <Check size={17} />
            <span>HAProxy readback</span>
            <strong>drain observed</strong>
            <small>state confirmed, effect not committed</small>
          </article>
          <ArrowRight size={15} />
          <article className="pending">
            <CircleDashed size={17} />
            <span>Verification</span>
            <strong>Track B collecting</strong>
            <small>124 samples remain</small>
          </article>
        </div>
        <div className="decision-language wide">
          <div>
            <span>Classifier suggested</span>
            <strong>ROUTE_INSTANCE_FAILURE · 0.82</strong>
          </div>
          <div>
            <span>Safety engine allowed</span>
            <strong>ROUTE_INSTANCE · 1 target</strong>
          </div>
          <div>
            <span>HAProxy observed</span>
            <strong>drain · weight 0</strong>
          </div>
          <div className="pending">
            <span>Verification confirmed</span>
            <strong>Not yet</strong>
          </div>
        </div>
      </Panel>
      <div className="two-column-layout">
        <Panel title="Action attempts" kicker="Durable saga">
          <StateTriptych
            previous={action.previous}
            requested={action.requested}
            observed={action.observed}
          />
          <div className="attempt-list">
            {action.attempts.map((attempt) => (
              <div key={attempt.number}>
                <span className="attempt-number">{attempt.number}</span>
                <div>
                  <strong>{attempt.operation}</strong>
                  <small>
                    {attempt.at} · {attempt.duration}
                  </small>
                </div>
                <span>
                  <StatusTag tone="success">{attempt.result}</StatusTag>
                  <code>{attempt.readback}</code>
                </span>
              </div>
            ))}
          </div>
          <Link
            className="button secondary compact"
            href={`/app/actions/${action.id}`}
          >
            Open complete action
            <ArrowRight size={14} />
          </Link>
        </Panel>
        <Panel title="Verification and recovery" kicker="Two-key invariant">
          <div className="verification-cards large">
            <article className="passed">
              <CheckCircle2 size={17} />
              <span>Affected-effect obligation</span>
              <strong>PASS</strong>
              <small>
                Error family returned to peer range with 428 real requests.
              </small>
            </article>
            <article className="collecting">
              <CircleDashed size={17} />
              <span>Preservation obligation</span>
              <strong>COLLECTING</strong>
              <small>
                176/300 real samples; success and p95 remain within bounds.
              </small>
            </article>
          </div>
          <div className="invariant-gate">
            <LockKeyhole size={17} />
            <span>
              <strong>Overall outcome: not yet decided</strong>No commit or
              staged reintegration advance before both obligations pass.
            </span>
          </div>
          <Link
            className="button secondary compact"
            href="/app/reintegration/reint-228"
          >
            Open linked recovery
            <ArrowRight size={14} />
          </Link>
        </Panel>
      </div>
      <Panel
        title="Classification revisions"
        kicker="History is not overwritten"
      >
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Revision</th>
                <th>Time</th>
                <th>Final class</th>
                <th>Confidence / completeness</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <code>cls_279</code>
                </td>
                <td>22:02:12</td>
                <td>
                  <StatusTag tone="warning">UNKNOWN</StatusTag>
                </td>
                <td>0.41 / 0.58</td>
                <td>Initial sample count below route-local threshold</td>
              </tr>
              <tr>
                <td>
                  <code>cls_281</code>
                </td>
                <td>22:02:14</td>
                <td>
                  <StatusTag tone="danger">ROUTE_INSTANCE_FAILURE</StatusTag>
                </td>
                <td>0.82 / 0.88</td>
                <td>Peer and sibling-route controls became sufficient</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

function BoundedIncidentDetails({
  selectedIncident,
}: {
  selectedIncident: DemoSnapshot["incidents"][number];
}) {
  const { classDescriptions } = useDemoSnapshot();
  const description = classDescriptions[selectedIncident.classification];
  const statusTone =
    selectedIncident.status === "RESOLVED"
      ? "success"
      : selectedIncident.status === "NEEDS_REVIEW"
        ? "danger"
        : "warning";
  return (
    <div className="page-stack incident-details-page">
      <PageHeader
        eyebrow={`${selectedIncident.id} · opened ${selectedIncident.openedAt}`}
        title={selectedIncident.title}
        brief={
          <>
            {description.plain} This is a bounded fixture record; no unrecorded
            action is inferred from the incident status.
          </>
        }
        meta={
          <>
            <StatusTag tone="danger">{selectedIncident.severity}</StatusTag>
            <StatusTag tone={statusTone}>{selectedIncident.status}</StatusTag>
            <span>{selectedIncident.scope}</span>
            <span>Owner {selectedIncident.owner}</span>
          </>
        }
        actions={
          <>
            <button
              className="button secondary"
              type="button"
              disabled
              title="Incident acknowledgement begins in a later phase"
            >
              Acknowledge
            </button>
            <Link className="button secondary" href="/app/incidents">
              <ArrowLeft size={15} />
              Incident list
            </Link>
          </>
        }
      />
      <section className="incident-summary-strip">
        <div>
          <span>Classification</span>
          <strong>{selectedIncident.classification}</strong>
          <small>fixture revision retained</small>
        </div>
        <div>
          <span>Confidence</span>
          <strong>{selectedIncident.confidence}%</strong>
          <small>advisory, not authority</small>
        </div>
        <div>
          <span>Completeness</span>
          <strong>{selectedIncident.completeness}%</strong>
          <small>
            {selectedIncident.classification === "UNKNOWN"
              ? "below actionable bound"
              : "bounded evidence"}
          </small>
        </div>
        <div>
          <span>Scope</span>
          <strong>{selectedIncident.scope}</strong>
          <small>minimum stated unit</small>
        </div>
      </section>
      <div className="two-column-layout">
        <Panel
          title="Evidence-bounded disposition"
          kicker="Last confirmed record"
        >
          <div
            className={`evidence-boundary-card ${selectedIncident.classification === "UNKNOWN" ? "warning" : ""}`}
          >
            <ShieldAlert size={18} />
            <div>
              <strong>
                {selectedIncident.classification === "UNKNOWN"
                  ? "Automatic destructive action is not allowed."
                  : "No broader routing state is implied."}
              </strong>
              <p>{description.action}</p>
            </div>
          </div>
          <KeyValueGrid
            items={[
              { label: "Incident", value: selectedIncident.id, mono: true },
              {
                label: "Operational class",
                value: selectedIncident.classification,
              },
              {
                label: "Evidence completeness",
                value: `${selectedIncident.completeness}%`,
                mono: true,
              },
              {
                label: "Classifier confidence",
                value: `${selectedIncident.confidence}%`,
                mono: true,
              },
              { label: "Owner", value: selectedIncident.owner },
              { label: "Observed status", value: selectedIncident.status },
            ]}
          />
        </Panel>
        <Panel title="Control-plane boundary" kicker="Explicitly unavailable">
          <div className="verification-cards large">
            <article
              className={
                selectedIncident.status === "RESOLVED" ? "passed" : "collecting"
              }
            >
              {selectedIncident.status === "RESOLVED" ? (
                <CheckCircle2 size={17} />
              ) : (
                <CircleDashed size={17} />
              )}
              <span>Recorded incident state</span>
              <strong>{selectedIncident.status}</strong>
              <small>Fixture status, not a live controller assertion.</small>
            </article>
            <article className="collecting">
              <CircleDashed size={17} />
              <span>HAProxy action</span>
              <strong>NO LINKED READBACK</strong>
              <small>
                This screen does not claim that a recommendation was applied.
              </small>
            </article>
          </div>
          <div className="notice warning">
            <AlertTriangle size={15} />
            <span>
              A complete Decision Trace is available only for{" "}
              <code>inc-1042</code>, whose evidence, action, and readback
              fixtures are linked end to end.
            </span>
          </div>
        </Panel>
      </div>
      <Panel title="Recorded timeline" kicker="No synthetic success">
        <Timeline
          items={[
            {
              at: selectedIncident.openedAt,
              label: "Incident record opened",
              detail: `${selectedIncident.classification} · ${selectedIncident.scope}`,
              state:
                selectedIncident.classification === "UNKNOWN"
                  ? "warning"
                  : "danger",
            },
            {
              at: "22:09 fixture",
              label: `Last recorded status: ${selectedIncident.status}`,
              detail:
                "No additional backend or action evidence is fabricated for this contract-complete detail view.",
              state:
                selectedIncident.status === "RESOLVED" ? "success" : "warning",
            },
          ]}
        />
      </Panel>
    </div>
  );
}

export function HealingActionsPage() {
  const { actionQueue } = useDemoSnapshot();
  const [filter, setFilter] = useState("all");
  const rows = actionQueue.filter(
    (item) => filter === "all" || item.lifecycle === filter,
  );
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Durable control history"
        title="Healing actions"
        brief={
          <>
            Every action remains a compensatable saga with an exact target,
            previous state, requested state, HAProxy readback, verification
            obligation, and rollback anchor.
          </>
        }
        meta={
          <>
            <span>1 verifying</span>
            <span>1 requires review</span>
            <span>1 result unknown</span>
          </>
        }
        actions={
          <button
            className="button secondary"
            type="button"
            onClick={() =>
              downloadTextFile(
                "shlb-action-audit-fixture.csv",
                [
                  csvRow([
                    "action",
                    "lifecycle",
                    "routing_unit",
                    "target",
                    "actor",
                    "approval",
                    "expiry",
                  ]),
                  ...actionQueue.map((item) =>
                    csvRow([
                      item.id,
                      item.lifecycle,
                      item.routingUnit,
                      item.target,
                      item.actor,
                      item.approval,
                      item.expiry,
                    ]),
                  ),
                ].join("\n"),
              )
            }
          >
            <History size={15} />
            Export audit view
          </button>
        }
      />
      <div className="list-toolbar">
        <label>
          <span>Lifecycle</span>
          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          >
            <option value="all">All lifecycle states</option>
            <option value="VERIFYING">Verifying</option>
            <option value="NEEDS_REVIEW">Needs review</option>
            <option value="RESULT_UNKNOWN">Result unknown</option>
            <option value="COMMITTED">Committed</option>
            <option value="ROLLED_BACK">Rolled back</option>
          </select>
          <ChevronDown size={13} />
        </label>
        <div className="toolbar-summary">
          <StatusTag tone="warning">No optimistic application</StatusTag>
          <span>State changes appear only after persisted readback.</span>
        </div>
      </div>
      <section className="panel table-panel">
        <div className="table-scroll">
          <table className="data-table action-table">
            <thead>
              <tr>
                <th>Action</th>
                <th>Lifecycle</th>
                <th>Routing unit and target</th>
                <th>Expected effect</th>
                <th>Actor / approval</th>
                <th>Expiry</th>
                <th>
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((item) => (
                <tr key={item.id}>
                  <td>
                    <Link href={`/app/actions/${item.id}`}>
                      <code>{item.id}</code>
                    </Link>
                  </td>
                  <td>
                    <StatusTag tone={lifecycleTone(item.lifecycle)}>
                      {item.lifecycle}
                    </StatusTag>
                  </td>
                  <td>
                    <strong>{item.routingUnit}</strong>
                    <code>{item.target}</code>
                  </td>
                  <td>{item.expectedEffect}</td>
                  <td>
                    <span>{item.actor}</span>
                    <small>{item.approval}</small>
                  </td>
                  <td>{item.expiry}</td>
                  <td>
                    <Link
                      className="icon-button"
                      href={`/app/actions/${item.id}`}
                      aria-label={`Open ${item.id}`}
                    >
                      <ChevronRight size={16} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <div className="state-explanation-grid">
        <div>
          <StatusTag tone="warning">RESULT_UNKNOWN</StatusTag>
          <p>
            Duplicate controls freeze while readback reconciles an ambiguous
            command outcome.
          </p>
        </div>
        <div>
          <StatusTag tone="danger">NEEDS_REVIEW</StatusTag>
          <p>
            Maximum attempts, drift, conflict, or insufficient evidence prevents
            automatic continuation.
          </p>
        </div>
        <div>
          <StatusTag tone="success">COMMITTED</StatusTag>
          <p>
            Observed state and both verification obligations passed. It does not
            claim root cause.
          </p>
        </div>
      </div>
    </div>
  );
}

export function ActionDetailsPage({ actionId }: { actionId?: string }) {
  const { action, actionQueue, scopeCandidates } = useDemoSnapshot();
  const [reviewOpen, setReviewOpen] = useState(false);
  const selectedAction =
    actionQueue.find((item) => item.id === (actionId ?? action.id)) ?? action;
  if (selectedAction.id !== action.id)
    return <BoundedActionDetails selectedAction={selectedAction} />;
  return (
    <div className="page-stack action-details-page">
      <PageHeader
        eyebrow={`${action.id} · generation ${action.controllerGeneration}`}
        title="Route-local checkout quarantine"
        brief={
          <>
            The action changed one logical membership and preserved three
            healthy memberships on the same physical instance. HAProxy readback
            matches the request; verification is still in progress.
          </>
        }
        meta={
          <>
            <StatusTag tone="warning">{action.lifecycle}</StatusTag>
            <span>{action.routingUnit}</span>
            <code>{action.target}</code>
            <span>Expires {action.expiry}</span>
          </>
        }
        actions={
          <>
            <button
              className="button secondary high-impact-control"
              type="button"
              onClick={() => setReviewOpen(true)}
            >
              <Undo2 size={15} />
              Preview rollback
            </button>
            <Link
              className="button primary"
              href="/app/incidents/inc-1042/decision-trace"
            >
              Decision Trace
              <ArrowRight size={15} />
            </Link>
          </>
        }
      />
      <Panel
        title="Previous, requested, observed"
        kicker="Three-way state diff"
        action={<StatusTag tone="success">Runtime readback matched</StatusTag>}
      >
        <StateTriptych
          previous={action.previous}
          requested={action.requested}
          observed={action.observed}
        />
        <p className="panel-explanation">
          <FileCheck2 size={15} />
          Requested uses durable intent; observed is HAProxy truth. Their match
          confirms control state, not the expected traffic effect.
        </p>
      </Panel>
      <div className="two-column-layout action-layout">
        <Panel title="Blast radius" kicker="Observed scope">
          <BlastRadiusMap mode="observed" />
          <details className="why-broader">
            <summary>Why not broader?</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Candidate</th>
                    <th>Targets</th>
                    <th>Healthy scope displaced</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {scopeCandidates.map((candidate) => (
                    <tr key={candidate.unit}>
                      <th>{candidate.unit}</th>
                      <td>{candidate.targets}</td>
                      <td>{candidate.healthyDisplaced}</td>
                      <td>{candidate.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </Panel>
        <Panel title="Action identity" kicker="Pinned transaction inputs">
          <KeyValueGrid
            items={[
              {
                label: "Controller generation",
                value: action.controllerGeneration,
                mono: true,
              },
              { label: "Target routing unit", value: action.routingUnit },
              { label: "Affected memberships", value: "1 of Backend B's 4" },
              {
                label: "Idempotency key",
                value: action.idempotencyKey,
                mono: true,
              },
              {
                label: "Rollback snapshot",
                value: action.rollbackSnapshot,
                mono: true,
              },
              { label: "Approval", value: action.approval },
              { label: "Actor", value: action.actor, mono: true },
              { label: "Reason", value: action.reason },
            ]}
          />
          <div className="expected-effect">
            <span>Expected technical effect</span>
            <p>{action.expectedEffect}</p>
          </div>
        </Panel>
      </div>
      <Panel title="Lifecycle" kicker="Durable state machine">
        <ol className="lifecycle-rail" aria-label="Action lifecycle">
          {[
            "PLANNED",
            "SAFETY_CHECKED",
            "PREPARED",
            "APPLIED",
            "STATE_CONFIRMED",
            "VERIFYING",
            "COMMITTED",
          ].map((stage, index) => {
            const complete = index < 5;
            const current = stage === "VERIFYING";
            return (
              <li
                className={
                  complete ? "complete" : current ? "current" : "pending"
                }
                key={stage}
              >
                <span>
                  {complete ? (
                    <Check size={12} />
                  ) : current ? (
                    <CircleDashed size={12} />
                  ) : (
                    index + 1
                  )}
                </span>
                <strong>{stage}</strong>
                <small>
                  {complete
                    ? "persisted"
                    : current
                      ? "collecting"
                      : "not entered"}
                </small>
              </li>
            );
          })}
        </ol>
      </Panel>
      <div className="two-column-layout">
        <Panel title="Attempt history" kicker="HAProxy adapter">
          <div className="attempt-list detailed">
            {action.attempts.map((attempt) => (
              <div key={attempt.number}>
                <span className="attempt-number">{attempt.number}</span>
                <div>
                  <strong>{attempt.operation}</strong>
                  <small>
                    {attempt.at} · {attempt.duration}
                  </small>
                </div>
                <div>
                  <StatusTag tone="success">{attempt.result}</StatusTag>
                  <code>{attempt.readback}</code>
                </div>
              </div>
            ))}
          </div>
          <div className="notice neutral">
            <CheckCircle2 size={15} />
            <span>
              No blind retry was issued. Readback completed in the same durable
              attempt.
            </span>
          </div>
        </Panel>
        <Panel
          title="Verification clock"
          kicker="Affected + preserved obligations"
        >
          <div className="verification-clock">
            <Timer size={20} />
            <div>
              <span>Deadline</span>
              <strong>00:48 cooldown · action window ends 22:12:14</strong>
              <small>Elapsed 07:28 · 176/300 preservation samples</small>
            </div>
          </div>
          <ProgressBar
            value={176}
            max={300}
            label="Real preservation samples"
            tone="warning"
          />
          <div className="verification-cards">
            <article className="passed">
              <CheckCircle2 size={16} />
              <span>Affected relief</span>
              <strong>PASS</strong>
            </article>
            <article className="collecting">
              <CircleDashed size={16} />
              <span>Unchanged capacity</span>
              <strong>COLLECTING</strong>
            </article>
          </div>
        </Panel>
      </div>
      <ReviewDialog
        open={reviewOpen}
        onClose={() => setReviewOpen(false)}
        title="Rollback checkout quarantine"
        intent="Preview restoration to the exact last verified state. The original action record will remain immutable; a rollback would create a linked action."
        actionLabel="Submit rollback"
      />
    </div>
  );
}

function BoundedActionDetails({
  selectedAction,
}: {
  selectedAction: DemoSnapshot["actionQueue"][number];
}) {
  return (
    <div className="page-stack action-details-page">
      <PageHeader
        eyebrow={`${selectedAction.id} · bounded fixture record`}
        title={`${selectedAction.routingUnit} action`}
        brief={
          <>
            This detail view exposes the durable lifecycle record without
            inventing readback, attempts, or verification evidence that is
            absent from the fixture.
          </>
        }
        meta={
          <>
            <StatusTag tone={lifecycleTone(selectedAction.lifecycle)}>
              {selectedAction.lifecycle}
            </StatusTag>
            <code>{selectedAction.target}</code>
            <span>{selectedAction.approval}</span>
            <span>Expiry {selectedAction.expiry}</span>
          </>
        }
        actions={
          <Link className="button secondary" href="/app/actions">
            <ArrowLeft size={15} />
            Action list
          </Link>
        }
      />
      <div className="two-column-layout action-layout">
        <Panel title="Pinned action identity" kicker="Durable summary">
          <KeyValueGrid
            items={[
              { label: "Action ID", value: selectedAction.id, mono: true },
              { label: "Lifecycle", value: selectedAction.lifecycle },
              { label: "Routing unit", value: selectedAction.routingUnit },
              {
                label: "Exact target",
                value: selectedAction.target,
                mono: true,
              },
              { label: "Actor", value: selectedAction.actor, mono: true },
              { label: "Approval", value: selectedAction.approval },
              {
                label: "Expected effect",
                value: selectedAction.expectedEffect,
              },
              { label: "Expiry", value: selectedAction.expiry, mono: true },
            ]}
          />
        </Panel>
        <Panel title="Observed-state boundary" kicker="No optimistic success">
          <div className="invariant-gate">
            <LockKeyhole size={17} />
            <span>
              <strong>
                {selectedAction.lifecycle === "RESULT_UNKNOWN"
                  ? "Result remains unknown"
                  : `Recorded lifecycle: ${selectedAction.lifecycle}`}
              </strong>
              {selectedAction.lifecycle === "RESULT_UNKNOWN"
                ? "Duplicate control remains frozen until reconciliation produces a trusted readback."
                : "This fixture has no linked three-way state snapshot; the UI does not infer one."}
            </span>
          </div>
          <div className="notice warning">
            <AlertTriangle size={15} />
            <span>
              Previous, requested, and observed state are shown only for{" "}
              <code>act-7719</code>, where all three records and the HAProxy
              readback are available.
            </span>
          </div>
        </Panel>
      </div>
      <Panel
        title="Lifecycle interpretation"
        kicker="State-specific operator meaning"
      >
        <div className="state-explanation-grid">
          <div>
            <StatusTag tone={lifecycleTone(selectedAction.lifecycle)}>
              {selectedAction.lifecycle}
            </StatusTag>
            <p>
              {selectedAction.lifecycle === "NEEDS_REVIEW"
                ? "Evidence or policy stopped automatic continuation; a human review cannot bypass deterministic safety."
                : selectedAction.lifecycle === "RESULT_UNKNOWN"
                  ? "The command outcome cannot be trusted. Reconciliation is required before any duplicate control."
                  : selectedAction.lifecycle === "ROLLED_BACK"
                    ? "A compensating action restored a recorded state; the original record remains immutable."
                    : selectedAction.lifecycle === "COMMITTED"
                      ? "Observed state and verification were recorded complete for this fixture summary."
                      : "The durable record remains available for audit."}
            </p>
          </div>
        </div>
      </Panel>
    </div>
  );
}

export function ReintegrationListPage() {
  const { reintegration, reintegrationStages } = useDemoSnapshot();
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Evidence-gated recovery"
        title="Reintegration"
        brief={
          <>
            Catalog on Backend C is holding at a requested 20% stage, but
            HAProxy still reports weight 5. Advancement is blocked until
            readback converges and 124 more real requests satisfy both recovery
            obligations.
          </>
        }
        meta={
          <>
            <span>1 active run</span>
            <span>1 flap in current run</span>
            <span>
              Percentages are configured weights, not promised traffic share
            </span>
          </>
        }
        actions={
          <Link className="button primary" href="/app/reintegration/reint-228">
            Open active run
            <ArrowRight size={15} />
          </Link>
        }
      />
      <Panel title="Recovery lanes" kicker="Current stage by target">
        <div className="reint-lanes">
          <div className="lane-head">
            {reintegrationStages.map((stage) => (
              <span key={stage.name}>{stage.name}</span>
            ))}
          </div>
          <Link className="lane-run" href="/app/reintegration/reint-228">
            <div className="lane-run-label">
              <strong>{reintegration.target}</strong>
              <code>{reintegration.id}</code>
              <small>last verified {reintegration.lastVerified}</small>
            </div>
            <div className="lane-track">
              {reintegrationStages.map((stage) => (
                <span className={stage.status} key={stage.name}>
                  {stage.status === "complete" ||
                  stage.status === "verified" ? (
                    <Check size={12} />
                  ) : stage.status === "current" ? (
                    <CircleDashed size={12} />
                  ) : (
                    ""
                  )}
                </span>
              ))}
            </div>
            <div className="lane-meta">
              <StatusTag tone="warning">requested 20 / observed 5</StatusTag>
              <span>
                {reintegration.samples}/{reintegration.requiredSamples} samples
              </span>
              <ChevronRight size={15} />
            </div>
          </Link>
        </div>
      </Panel>
      <div className="three-column-summary">
        <article>
          <span>Requested / observed</span>
          <strong>20 / 5</strong>
          <small>HAProxy differs from requested weight</small>
        </article>
        <article>
          <span>Probe evidence</span>
          <strong>{reintegration.probe}</strong>
          <small>synthetic evidence is not full recovery</small>
        </article>
        <article>
          <span>Next eligible transition</span>
          <strong>{reintegration.cooldown}</strong>
          <small>{reintegration.nextEligibleAt}</small>
        </article>
      </div>
      <div className="notice warning">
        <AlertTriangle size={15} />
        <span>
          Low or absent target traffic cannot pass real-traffic criteria. A
          stage holds or returns insufficient; it never turns healthy through
          silence.
        </span>
      </div>
    </div>
  );
}

export function ReintegrationDetailsPage() {
  const { reintegration, reintegrationStages } = useDemoSnapshot();
  const [review, setReview] = useState<{ title: string; label: string } | null>(
    null,
  );
  return (
    <div className="page-stack reint-details-page">
      <PageHeader
        eyebrow={`${reintegration.id} · route-specific recovery`}
        title={`${reintegration.target} is holding at 20%.`}
        brief={
          <>
            The relief obligation still passes, but requested and observed
            weight differ and 124 more real requests are required before 50% can
            be considered. Other routes on Backend C remain visible preservation
            controls.
          </>
        }
        meta={
          <>
            <StatusTag tone="warning">COLLECTING</StatusTag>
            <span>Last verified safe stage {reintegration.lastVerified}</span>
            <span>Flap count {reintegration.flapCount}</span>
            <span>Cooldown {reintegration.cooldown}</span>
          </>
        }
        actions={
          <div className="reint-controls">
            <button
              className="button secondary high-impact-control"
              type="button"
              onClick={() =>
                setReview({
                  title: "Pause staged reintegration",
                  label: "Submit pause",
                })
              }
            >
              <Pause size={15} />
              Pause
            </button>
            <button
              className="button secondary high-impact-control"
              type="button"
              disabled
              title="The run is not paused"
            >
              <Play size={15} />
              Resume
            </button>
            <button
              className="button secondary high-impact-control"
              type="button"
              onClick={() =>
                setReview({
                  title: "Roll back one verified stage",
                  label: "Submit stage rollback",
                })
              }
            >
              <RotateCcw size={15} />
              Rollback stage
            </button>
            <button
              className="button danger high-impact-control"
              type="button"
              onClick={() =>
                setReview({
                  title: "Quarantine catalog on Backend C",
                  label: "Submit quarantine",
                })
              }
            >
              <Ban size={15} />
              Quarantine
            </button>
            <button
              className="button secondary high-impact-control"
              type="button"
              onClick={() =>
                setReview({
                  title: "Require manual review",
                  label: "Submit review hold",
                })
              }
            >
              <ShieldAlert size={15} />
              Require review
            </button>
          </div>
        }
      />
      <section
        className="reintegration-journey"
        aria-label="Reintegration stages"
      >
        {reintegrationStages.map((stage, index) => (
          <article className={stage.status} key={stage.name}>
            <div className="stage-top">
              <span className="stage-index">
                {stage.status === "complete" || stage.status === "verified" ? (
                  <Check size={13} />
                ) : (
                  index + 1
                )}
              </span>
              <StatusTag
                tone={
                  stage.status === "verified"
                    ? "success"
                    : stage.status === "current"
                      ? "warning"
                      : stage.status === "complete"
                        ? "success"
                        : "neutral"
                }
              >
                {stage.status}
              </StatusTag>
            </div>
            <h2>{stage.name}</h2>
            <dl>
              <div>
                <dt>Requested</dt>
                <dd>{stage.requested}</dd>
              </div>
              <div>
                <dt>Observed</dt>
                <dd>{stage.observed ?? "—"}</dd>
              </div>
            </dl>
            <p>{stage.note}</p>
            {stage.status === "current" && (
              <div className="stage-drift">
                <GitCompareArrows size={13} />
                DRIFT
              </div>
            )}
          </article>
        ))}
      </section>
      <div className="two-column-layout">
        <Panel
          title="Current stage evidence"
          kicker="20% configured-weight stage"
        >
          <div className="requested-observed-block">
            <article>
              <span>Requested weight</span>
              <strong>20</strong>
              <small>durable reintegration intent</small>
            </article>
            <GitCompareArrows size={18} />
            <article className="mismatch">
              <span>Observed weight</span>
              <strong>5</strong>
              <small>last HAProxy readback · 5 s old</small>
            </article>
            <article>
              <span>Observed traffic share</span>
              <strong>{reintegration.observedShare}%</strong>
              <small>not the same as configured weight</small>
            </article>
          </div>
          <ProgressBar
            value={reintegration.samples}
            max={reintegration.requiredSamples}
            label="Real target samples"
            tone="warning"
          />
          <KeyValueGrid
            items={[
              { label: "Probe results", value: reintegration.probe },
              { label: "Target vs peers", value: "error +0.1 pp · p95 +6.4%" },
              { label: "Preservation", value: reintegration.preservation },
              { label: "Cooldown", value: reintegration.cooldown, mono: true },
              { label: "Next eligible", value: reintegration.nextEligibleAt },
            ]}
          />
        </Panel>
        <Panel
          title="Preservation controls"
          kicker="Same physical instance, other routes"
        >
          <div className="preservation-list">
            <div>
              <CheckCircle2 size={16} />
              <span>
                <strong>/public × Backend C</strong>
                <small>ready 100 · success −0.1 pp · p95 +1.2%</small>
              </span>
              <StatusTag tone="success">within bound</StatusTag>
            </div>
            <div>
              <CircleDashed size={16} />
              <span>
                <strong>/auth × Backend C</strong>
                <small>ready 100 · telemetry 94 s old</small>
              </span>
              <StatusTag tone="warning">unknown</StatusTag>
            </div>
            <div>
              <CheckCircle2 size={16} />
              <span>
                <strong>/checkout × Backend C</strong>
                <small>ready 100 · peer control · p95 326 ms</small>
              </span>
              <StatusTag tone="success">within bound</StatusTag>
            </div>
          </div>
          <div className="notice warning">
            <AlertTriangle size={15} />
            <span>
              Stale auth telemetry prevents the preserved cohort from being
              treated as fully complete.
            </span>
          </div>
        </Panel>
      </div>
      <Panel title="Stage history" kicker="Observed transitions only">
        <Timeline
          items={[
            {
              at: "20:55:02",
              label: "Quarantine confirmed",
              detail: "Observed weight 0; original catalog symptoms contained",
              state: "success",
            },
            {
              at: "21:06:44",
              label: "Probe gate passed",
              detail: "3 non-mutating synthetic probes over 18 seconds",
              state: "success",
            },
            {
              at: "21:09:10",
              label: "5% stage verified",
              detail:
                "Observed weight 5; both obligations passed with 112 requests",
              state: "success",
            },
            {
              at: "21:43:26",
              label: "20% requested",
              detail:
                "Durable desired state updated; HAProxy readback remains at 5",
              state: "warning",
            },
            {
              at: "22:09:42",
              label: "Stage held",
              detail:
                "124 samples remain and desired/observed drift is unresolved",
              state: "warning",
            },
          ]}
        />
      </Panel>
      <div className="desktop-only-control-note">
        <ShieldAlert size={15} />
        <span>
          High-impact recovery controls require desktop review, an operational
          reason, authorization, a fresh impact snapshot, and observed
          confirmation.
        </span>
      </div>
      <ReviewDialog
        open={review !== null}
        onClose={() => setReview(null)}
        title={review?.title ?? "Review recovery change"}
        intent="This recovery control affects one route membership. The impact review keeps all sibling memberships visible and uses the last verified stage as the rollback anchor."
        actionLabel={review?.label ?? "Submit command"}
      />
    </div>
  );
}

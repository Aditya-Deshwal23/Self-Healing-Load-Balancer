"use client";

import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Braces,
  Check,
  CheckCircle2,
  CircleDashed,
  Clock3,
  FileCheck2,
  Fingerprint,
  GitBranch,
  GitCompareArrows,
  LockKeyhole,
  Network,
  Scale,
  ShieldCheck,
  Target,
  Timer,
  Waypoints,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useDemoSnapshot } from "@/lib/demo/provider";
import { EvidenceChart } from "@/components/charts";
import {
  BlastRadiusMap,
  KeyValueGrid,
  PageHeader,
  ProgressBar,
  StateTriptych,
  StatusTag,
} from "@/components/ui";

const stageIcons = {
  evidence: Activity,
  fingerprint: Fingerprint,
  classification: GitBranch,
  confidence: Scale,
  safety: ShieldCheck,
  "routing-unit": Target,
  haproxy: Network,
  verification: GitCompareArrows,
  outcome: Waypoints,
} as const;

const chapterMap = [
  { label: "Observe", stages: ["evidence"] },
  {
    label: "Localize",
    stages: ["fingerprint", "classification", "confidence"],
  },
  { label: "Bound", stages: ["safety", "routing-unit"] },
  { label: "Act", stages: ["haproxy"] },
  { label: "Verify", stages: ["verification"] },
  { label: "Recover", stages: ["outcome"] },
];

export function DecisionTrace() {
  const { incident, traceStages } = useDemoSnapshot();
  const [selectedId, setSelectedId] = useState("verification");
  const [showRaw, setShowRaw] = useState(false);
  const selected =
    traceStages.find((stage) => stage.id === selectedId) ?? traceStages[0];
  const selectedIndex = traceStages.findIndex(
    (stage) => stage.id === selectedId,
  );
  const SelectedIcon = stageIcons[selected.id as keyof typeof stageIcons];
  const currentChapter = chapterMap.find((chapter) =>
    chapter.stages.includes(selectedId),
  );

  const inspectorContent = useMemo(() => {
    switch (selectedId) {
      case "evidence":
        return <EvidenceInspector />;
      case "fingerprint":
        return <FingerprintInspector />;
      case "classification":
      case "confidence":
        return <ClassificationInspector />;
      case "safety":
      case "routing-unit":
        return <ScopeInspector />;
      case "haproxy":
        return <ActionInspector />;
      case "verification":
        return <VerificationInspector />;
      default:
        return <OutcomeInspector />;
    }
  }, [selectedId]);

  return (
    <div className="decision-trace-page page-stack">
      <PageHeader
        eyebrow={`Incident ${incident.id} · explanatory trace`}
        title="Why checkout alone was removed from Backend B"
        brief={
          <>
            Evidence localized the divergence to one route membership.
            Deterministic safety allowed that minimum unit, HAProxy readback
            confirmed the requested drain, and the system is still proving that
            healthy sibling traffic remained preserved.
          </>
        }
        meta={
          <>
            <StatusTag tone="warning">{incident.status}</StatusTag>
            <span>{incident.scope}</span>
            <span>Evidence {incident.completeness}% complete</span>
            <span>{incident.correlationId}</span>
          </>
        }
        actions={
          <>
            <Link
              className="button secondary"
              href={`/app/incidents/${incident.id}`}
            >
              <ArrowLeft size={15} />
              Incident
            </Link>
            <button
              className="button secondary"
              type="button"
              onClick={() => setShowRaw((value) => !value)}
            >
              <Braces size={15} />
              {showRaw ? "Hide raw fields" : "Show raw fields"}
            </button>
          </>
        }
      />

      <nav className="trace-chapters" aria-label="Decision Trace chapters">
        {chapterMap.map((chapter) => {
          const state = chapter.stages.some(
            (id) =>
              traceStages.find((stage) => stage.id === id)?.status ===
              "current",
          )
            ? "current"
            : chapter.stages.every(
                  (id) =>
                    traceStages.find((stage) => stage.id === id)?.status ===
                    "complete",
                )
              ? "complete"
              : "pending";
          return (
            <button
              type="button"
              className={`${state} ${currentChapter?.label === chapter.label ? "selected" : ""}`}
              onClick={() => setSelectedId(chapter.stages[0])}
              key={chapter.label}
            >
              <span>
                {state === "complete" ? (
                  <Check size={13} />
                ) : (
                  chapterMap.indexOf(chapter) + 1
                )}
              </span>
              {chapter.label}
            </button>
          );
        })}
      </nav>

      <div className="trace-workspace">
        <section className="trace-canvas" aria-labelledby="trace-canvas-title">
          <div className="trace-canvas-heading">
            <div>
              <span className="section-kicker">Technical lineage</span>
              <h2 id="trace-canvas-title">Evidence → outcome</h2>
            </div>
            <span className="trace-window">
              <Clock3 size={14} />
              21:54–22:09 IST · immutable snapshot
            </span>
          </div>
          <ol className="trace-stage-list">
            {traceStages.map((stage, index) => {
              const Icon = stageIcons[stage.id as keyof typeof stageIcons];
              return (
                <li
                  className={`${stage.status} ${selectedId === stage.id ? "selected" : ""}`}
                  key={stage.id}
                >
                  <button
                    type="button"
                    onClick={() => setSelectedId(stage.id)}
                    aria-current={selectedId === stage.id ? "step" : undefined}
                  >
                    <span className="trace-stage-icon">
                      <Icon size={17} />
                    </span>
                    <span className="trace-stage-copy">
                      <small>{stage.label}</small>
                      <strong>{stage.result}</strong>
                      <span>{stage.reason}</span>
                      <code>{stage.at}</code>
                    </span>
                    <span className="trace-stage-status">
                      {stage.status === "complete" ? (
                        <>
                          <Check size={12} />
                          Complete
                        </>
                      ) : stage.status === "current" ? (
                        <>
                          <CircleDashed size={12} />
                          Current
                        </>
                      ) : stage.status === "blocked" ? (
                        <>
                          <LockKeyhole size={12} />
                          Blocked
                        </>
                      ) : (
                        "Pending"
                      )}
                    </span>
                  </button>
                  {index < traceStages.length - 1 && (
                    <span className="trace-connector" aria-hidden="true">
                      <ArrowDown size={15} />
                    </span>
                  )}
                </li>
              );
            })}
          </ol>
          <div
            className="trace-verification-branch"
            aria-label="Verification branches"
          >
            <div className="branch-origin">
              <GitCompareArrows size={16} />
              <span>Verification divides into equal obligations</span>
            </div>
            <article className="relief">
              <CheckCircle2 size={17} />
              <div>
                <span>Track A · affected cohort</span>
                <strong>Relief passed</strong>
                <small>checkout errors 18.2% → 3.1% · n=428</small>
              </div>
            </article>
            <article className="preservation">
              <CircleDashed size={17} />
              <div>
                <span>Track B · preserved cohort</span>
                <strong>Collecting</strong>
                <small>public/auth/catalog stable · n=176/300</small>
              </div>
            </article>
            <div className="branch-gate">
              <ShieldCheck size={17} />
              <div>
                <span>Dual-invariant gate</span>
                <strong>OPEN · no outcome committed</strong>
              </div>
            </div>
          </div>
        </section>

        <aside className="trace-inspector" aria-labelledby="inspector-title">
          <header>
            <div className={`trace-stage-icon ${selected.status}`}>
              <SelectedIcon size={18} />
            </div>
            <div>
              <span className="section-kicker">
                {currentChapter?.label} · selected stage
              </span>
              <h2 id="inspector-title">{selected.label}</h2>
            </div>
          </header>
          <div className="inspector-status">
            <StatusTag
              tone={
                selected.status === "complete"
                  ? "success"
                  : selected.status === "current"
                    ? "warning"
                    : "neutral"
              }
            >
              {selected.status}
            </StatusTag>
            <time>{selected.at}</time>
          </div>
          <p className="inspector-reason">{selected.reason}</p>
          <KeyValueGrid
            items={[
              { label: "Responsible engine", value: selected.engine },
              { label: "Result", value: selected.result },
              {
                label: "Input references",
                value: selected.refs.join(" · "),
                mono: true,
              },
            ]}
          />
          {inspectorContent}
          {showRaw && (
            <div className="raw-fields">
              <div className="raw-fields-title">
                <Braces size={14} />
                Typed raw fields
              </div>
              <pre>
                {JSON.stringify(
                  {
                    stage_id: selected.id,
                    status: selected.status,
                    occurred_at: selected.at,
                    engine: selected.engine,
                    result: selected.result,
                    refs: selected.refs,
                  },
                  null,
                  2,
                )}
              </pre>
            </div>
          )}
          <div className="inspector-nav">
            <button
              className="button secondary compact"
              type="button"
              disabled={selectedIndex === 0}
              onClick={() => setSelectedId(traceStages[selectedIndex - 1]?.id)}
            >
              <ArrowLeft size={14} />
              Previous
            </button>
            <button
              className="button secondary compact"
              type="button"
              disabled={selectedIndex === traceStages.length - 1}
              onClick={() => setSelectedId(traceStages[selectedIndex + 1]?.id)}
            >
              Next
              <ArrowRight size={14} />
            </button>
          </div>
        </aside>
      </div>

      <section
        className="trace-time-scrubber"
        aria-label="Shared evidence time window"
      >
        <span>21:54 pre-window</span>
        <div>
          <i className="incident-onset" style={{ left: "52%" }} />
          <i className="action-marker" style={{ left: "58%" }} />
          <i className="current-marker" style={{ left: "96%" }} />
          <span className="window-fill" />
        </div>
        <span>22:09 fixture</span>
        <div className="scrubber-labels">
          <span style={{ left: "48%" }}>incident</span>
          <span style={{ left: "56%" }}>action</span>
          <span style={{ left: "91%" }}>snapshot</span>
        </div>
      </section>
    </div>
  );
}

function EvidenceInspector() {
  const evidence = [
    {
      source: "HAProxy Runtime",
      result: "supports",
      detail: "membership state fresh · 2 s",
    },
    {
      source: "Proxy outcomes",
      result: "supports",
      detail: "428 checkout/B samples",
    },
    {
      source: "Same-route peers",
      result: "supports",
      detail: "A and C within aligned range",
    },
    {
      source: "Same-instance routes",
      result: "counter",
      detail: "public/auth/catalog healthy",
    },
    {
      source: "Direct probes",
      result: "supports",
      detail: "3 synthetic failures pre-action",
    },
    {
      source: "Auth/C telemetry",
      result: "missing",
      detail: "94 s old · visible conflict",
    },
  ];
  return (
    <section className="inspector-section">
      <h3>Evidence constellation</h3>
      <div className="evidence-constellation">
        {evidence.map((item) => (
          <div className={item.result} key={item.source}>
            <span>
              {item.result === "supports" ? (
                <Check size={12} />
              ) : item.result === "counter" ? (
                <GitCompareArrows size={12} />
              ) : (
                <AlertTriangle size={12} />
              )}
              {item.result}
            </span>
            <strong>{item.source}</strong>
            <small>{item.detail}</small>
          </div>
        ))}
      </div>
      <p className="limitation-note">
        <AlertTriangle size={14} />
        Missing sources stay present and lower completeness; absence is never
        converted to zero errors.
      </p>
    </section>
  );
}

function FingerprintInspector() {
  return (
    <section className="inspector-section">
      <h3>Affected and counter-evidence sets</h3>
      <div className="set-comparison">
        <article>
          <span>Affected</span>
          <code>route={"{checkout}"}</code>
          <code>instance={"{B}"}</code>
          <code>version={"{}"}</code>
        </article>
        <article>
          <span>Preserved controls</span>
          <code>same_instance={"{public,auth,catalog}"}</code>
          <code>same_route={"{A,C}"}</code>
        </article>
      </div>
      <details>
        <summary>Canonical signature</summary>
        <pre>
          route:checkout|instance:B|outcome:timeout|peer_delta:6.1|sibling_routes:stable|schema:2.1
        </pre>
      </details>
    </section>
  );
}

function ClassificationInspector() {
  return (
    <section className="inspector-section">
      <h3>Suggestion is not permission</h3>
      <div className="decision-separation">
        <article>
          <span>Classifier suggested</span>
          <strong>ROUTE_INSTANCE_FAILURE</strong>
          <code>shadow model probability 0.82</code>
          <p>Advisory classification evidence.</p>
        </article>
        <article>
          <span>Deterministic permission</span>
          <strong>Not decided here</strong>
          <code>continue to safety envelope</code>
          <p>Confidence cannot bypass constraints.</p>
        </article>
      </div>
      <div className="alternative-classes">
        <div>
          <span>INSTANCE_DEGRADED</span>
          <code>0.08</code>
          <small>Contradicted by healthy sibling routes</small>
        </div>
        <div>
          <span>SHARED_ROUTE_FAILURE</span>
          <code>0.05</code>
          <small>Contradicted by healthy checkout peers</small>
        </div>
        <div>
          <span>UNKNOWN</span>
          <code>0.05</code>
          <small>One missing source retained</small>
        </div>
      </div>
    </section>
  );
}

function ScopeInspector() {
  const { scopeCandidates } = useDemoSnapshot();
  return (
    <section className="inspector-section">
      <h3>Smallest supported safe action</h3>
      <div className="table-scroll">
        <table className="scope-table">
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Targets</th>
              <th>Healthy displaced</th>
              <th>Decision</th>
            </tr>
          </thead>
          <tbody>
            {scopeCandidates.map((candidate) => (
              <tr
                className={
                  candidate.result.includes("selected") ? "selected" : ""
                }
                key={candidate.unit}
              >
                <th>
                  {candidate.unit}
                  <small>{candidate.reason}</small>
                </th>
                <td>{candidate.targets}</td>
                <td>{candidate.healthyDisplaced}</td>
                <td>
                  <StatusTag
                    tone={
                      candidate.result.includes("selected")
                        ? "success"
                        : candidate.result.includes("Rejected")
                          ? "danger"
                          : "warning"
                    }
                  >
                    {candidate.result}
                  </StatusTag>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="capacity-calculation">
        <strong>Physical remaining-capacity calculation</strong>
        <code>3 unique instances × 100 = 300 units</code>
        <code>checkout peers after action = 200 / 300 = 67%</code>
        <code>policy floor = 50% · margin = +17 points</code>
      </div>
    </section>
  );
}

function ActionInspector() {
  const { action } = useDemoSnapshot();
  return (
    <section className="inspector-section">
      <h3>Observable action saga</h3>
      <StateTriptych
        previous={action.previous}
        requested={action.requested}
        observed={action.observed}
      />
      <KeyValueGrid
        items={[
          {
            label: "Controller generation",
            value: action.controllerGeneration,
            mono: true,
          },
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
          { label: "Attempt", value: "1 · acknowledged · readback matched" },
        ]}
      />
      <p className="limitation-note">
        <FileCheck2 size={14} />
        Observed state confirms the HAProxy change. It does not prove the
        traffic effect.
      </p>
    </section>
  );
}

function VerificationInspector() {
  const { errorSeries } = useDemoSnapshot();
  return (
    <section className="inspector-section verification-inspector">
      <h3>Two obligations, one verdict</h3>
      <EvidenceChart
        title="Affected checkout error rate"
        summary="Checkout errors on Backend B fell after the route membership drain; peer error rate stayed near 3%."
        data={errorSeries}
        unit="%"
        sampleCount={428}
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
      <div className="verification-cards">
        <article className="passed">
          <CheckCircle2 size={16} />
          <span>Track A · relief</span>
          <strong>PASS</strong>
          <small>18.2% → 3.1% · 428 real requests</small>
        </article>
        <article className="collecting">
          <CircleDashed size={16} />
          <span>Track B · preservation</span>
          <strong>COLLECTING</strong>
          <small>176/300 samples · unique reserve +17 points</small>
        </article>
      </div>
      <ProgressBar
        value={176}
        max={300}
        label="Preserved cohort samples"
        tone="warning"
      />
      <div className="invariant-gate">
        <LockKeyhole size={17} />
        <span>
          <strong>Outcome gate remains open</strong>No EFFECTIVE verdict until
          both fresh obligations pass.
        </span>
      </div>
    </section>
  );
}

function OutcomeInspector() {
  return (
    <section className="inspector-section">
      <h3>Recovery is blocked by verification</h3>
      <div className="outcome-state">
        <Timer size={18} />
        <div>
          <span>Current result</span>
          <strong>Not yet decided</strong>
          <p>
            Reintegration may begin only after a persisted EFFECTIVE verdict.
            UNKNOWN or no traffic cannot advance recovery.
          </p>
        </div>
      </div>
      <BlastRadiusMap mode="observed" />
      <Link
        className="button secondary full"
        href="/app/reintegration/reint-228"
      >
        Open linked reintegration run
        <ArrowRight size={15} />
      </Link>
    </section>
  );
}

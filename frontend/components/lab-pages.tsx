"use client";

import Link from "next/link";
import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  Beaker,
  Check,
  ChevronDown,
  CircleDashed,
  Download,
  FlaskConical,
  LockKeyhole,
  ShieldAlert,
  Square,
} from "lucide-react";
import { useState } from "react";
import { useDemoSnapshot } from "@/lib/demo/provider";
import { downloadTextFile } from "@/lib/client-download";
import { useSmallViewport } from "@/lib/use-small-viewport";
import { IntervalPlot } from "@/components/charts";
import {
  KeyValueGrid,
  PageHeader,
  Panel,
  ProgressBar,
  StatusTag,
  Timeline,
} from "@/components/ui";

const faultScenarios = [
  {
    id: "route-local",
    title: "Route-instance failure",
    target: "/checkout × Backend B",
    effect: "Known timeout signature on one registered route",
    duration: "180 s",
    risk: "1 route membership",
  },
  {
    id: "slow-instance",
    title: "Slow physical instance",
    target: "Backend B",
    effect: "Bounded latency across populated routes",
    duration: "180 s",
    risk: "4 route memberships",
  },
  {
    id: "shared-route",
    title: "Shared-route dependency",
    target: "/checkout dependency",
    effect: "Same bounded failure across all checkout peers",
    duration: "180 s",
    risk: "complete route",
  },
  {
    id: "overload",
    title: "Offered traffic overload",
    target: "/catalog",
    effect: "Open-loop load above declared capacity",
    duration: "300 s",
    risk: "route queue",
  },
];

export function FaultLabPage() {
  const [scenario, setScenario] = useState(faultScenarios[0]);
  const [step, setStep] = useState<"configure" | "confirm">("configure");
  const [typed, setTyped] = useState("");
  const smallViewport = useSmallViewport();
  return (
    <div className="page-stack fault-lab-page">
      <div className="lab-hazard-banner" role="alert">
        <AlertOctagon size={18} />
        <div>
          <strong>ISOLATED RESEARCH LAB · SYNTHETIC TARGETS ONLY</strong>
          <span>
            Fault execution must be absent outside a LAB environment and is not
            part of the Phase 2 registry foundation.
          </span>
        </div>
      </div>
      <PageHeader
        eyebrow="Research capability · LAB authorized"
        title="Fault Lab"
        brief={
          <>
            Prepare deterministic, expiring fault scenarios against registered
            synthetic targets. Every injection requires an experiment link,
            exact blast radius, automatic cleanup, and two-step confirmation.
          </>
        }
        meta={
          <>
            <span>Environment Local traffic lab</span>
            <span>Researcher capability fixture</span>
            <span>No public execution route</span>
          </>
        }
      />
      {smallViewport && (
        <div className="notice warning" role="status">
          <ShieldAlert size={15} />
          <span>Fault review and injection are disabled below 768px.</span>
        </div>
      )}
      <div className="fault-layout">
        <section
          className="fault-catalog"
          aria-labelledby="fault-catalog-title"
        >
          <span className="section-kicker">Scenario catalog</span>
          <h2 id="fault-catalog-title">Choose a bounded fault</h2>
          {faultScenarios.map((item) => (
            <button
              type="button"
              className={scenario.id === item.id ? "active" : ""}
              onClick={() => {
                setScenario(item);
                setStep("configure");
                setTyped("");
              }}
              key={item.id}
            >
              <FlaskConical size={16} />
              <span>
                <strong>{item.title}</strong>
                <small>{item.effect}</small>
              </span>
              <code>{item.risk}</code>
            </button>
          ))}
        </section>
        <section
          className="panel fault-config"
          aria-labelledby="fault-config-title"
        >
          <div className="panel-heading">
            <div>
              <span className="section-kicker">
                {step === "configure" ? "Step 1 · scope" : "Step 2 · confirm"}
              </span>
              <h2 id="fault-config-title">{scenario.title}</h2>
            </div>
            <StatusTag tone="danger">HAZARD</StatusTag>
          </div>
          {step === "configure" ? (
            <>
              <div className="policy-form">
                <label>
                  Exact target
                  <input value={scenario.target} readOnly />
                </label>
                <label>
                  Experiment link
                  <select defaultValue="exp-031">
                    <option value="exp-031">
                      exp-031 · scoped-failure pilot
                    </option>
                  </select>
                  <ChevronDown size={13} />
                </label>
                <label>
                  Fault duration
                  <input value={scenario.duration} readOnly />
                </label>
                <label>
                  Cleanup deadline
                  <input value="duration + 30 s watchdog" readOnly />
                </label>
              </div>
              <div className="fault-impact">
                <strong>Blast-radius preview</strong>
                <p>
                  This injection affects <code>{scenario.target}</code>. Cleanup
                  verifies routes, weights, queues, incidents, locks, and target
                  health before the rig becomes reusable.
                </p>
                <dl>
                  <div>
                    <dt>Ground-truth target</dt>
                    <dd>{scenario.risk}</dd>
                  </div>
                  <div>
                    <dt>Customer data</dt>
                    <dd>None · synthetic only</dd>
                  </div>
                  <div>
                    <dt>Automatic expiry</dt>
                    <dd>{scenario.duration}</dd>
                  </div>
                </dl>
              </div>
              <button
                className="button danger"
                type="button"
                disabled={smallViewport}
                title={
                  smallViewport
                    ? "Fault review is unavailable below 768px"
                    : undefined
                }
                onClick={() => setStep("confirm")}
              >
                Review hazardous injection
                <ArrowRight size={15} />
              </button>
            </>
          ) : (
            <>
              <div className="fault-confirm">
                <ShieldAlert size={21} />
                <div>
                  <strong>Confirm isolated fault scope</strong>
                  <p>
                    The fault runner would record independent ground truth and
                    start an expiry watchdog. No controller classification can
                    alter the declared target.
                  </p>
                </div>
              </div>
              <KeyValueGrid
                items={[
                  { label: "Scenario", value: scenario.title },
                  { label: "Exact target", value: scenario.target, mono: true },
                  { label: "Duration", value: scenario.duration },
                  { label: "Experiment", value: "exp-031", mono: true },
                  {
                    label: "Automatic cleanup",
                    value: "Required + 30 s watchdog",
                  },
                ]}
              />
              <label htmlFor="fault-confirmation">
                Type <code>INJECT LOCAL LAB</code> to continue
              </label>
              <input
                id="fault-confirmation"
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
              />
              <div className="notice warning">
                <AlertTriangle size={15} />
                <span>
                  The execution API is intentionally absent in Phase 2. Matching
                  the confirmation phrase will not inject a fault.
                </span>
              </div>
              <div className="button-row">
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => setStep("configure")}
                >
                  Back
                </button>
                <button className="button danger" type="button" disabled>
                  Inject fault
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

export function ExperimentsPage() {
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Versioned research manifests"
        title="Experiments"
        brief={
          <>
            Matched baseline and fault trials preserve seeds, images, policy
            revisions, truth ledgers, exclusions, and artifact hashes. Completed
            raw data cannot be cherry-picked away.
          </>
        }
        meta={
          <>
            <span>1 active pilot</span>
            <span>1 draft</span>
            <span>960-run confirmatory design</span>
          </>
        }
        actions={
          <button className="button primary" type="button" disabled>
            <Beaker size={15} />
            New experiment
          </button>
        }
      />
      <section className="panel table-panel">
        <div className="table-scroll">
          <table className="data-table experiment-table">
            <thead>
              <tr>
                <th>Experiment</th>
                <th>Status</th>
                <th>Design</th>
                <th>Progress</th>
                <th>Validity</th>
                <th>Owner</th>
                <th>
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <Link href="/app/lab/experiments/exp-031">
                    <code>exp-031</code>
                    <strong>Scoped-failure pilot</strong>
                  </Link>
                </td>
                <td>
                  <StatusTag tone="warning">RUNNING FIXTURE</StatusTag>
                </td>
                <td>4 baselines × 8 faults × 5 pilot blocks</td>
                <td>
                  <ProgressBar
                    value={92}
                    max={160}
                    label="Runs"
                    tone="warning"
                  />
                </td>
                <td>
                  <span>89 valid</span>
                  <small>3 invalid · declared reasons</small>
                </td>
                <td>A. Deshwal</td>
                <td>
                  <Link
                    className="icon-button"
                    href="/app/lab/experiments/exp-031"
                  >
                    <ArrowRight size={15} />
                  </Link>
                </td>
              </tr>
              <tr>
                <td>
                  <code>exp-032</code>
                  <strong>Confirmatory matched blocks</strong>
                </td>
                <td>
                  <StatusTag tone="neutral">DRAFT</StatusTag>
                </td>
                <td>4 baselines × 8 faults × 30 blocks</td>
                <td>
                  <ProgressBar value={0} max={960} label="Runs" />
                </td>
                <td>Not started</td>
                <td>Research team</td>
                <td>
                  <span>—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <div className="notice neutral">
        <LockKeyhole size={15} />
        <span>
          Stopping an experiment affects pending trials only. Completed raw data
          and validity records remain immutable.
        </span>
      </div>
    </div>
  );
}

export function ExperimentDetailsPage() {
  const { experimentScenarios } = useDemoSnapshot();
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="exp-031 · manifest revision 4"
        title="Scoped-failure pilot"
        brief={
          <>
            This pilot estimates variance, validates fault cleanup, and freezes
            verification windows before confirmatory trials. Its results are
            exploratory and excluded from the final hypothesis test.
          </>
        }
        meta={
          <>
            <StatusTag tone="warning">RUNNING FIXTURE</StatusTag>
            <span>seed block 20260721</span>
            <span>92 / 160 runs complete</span>
            <span>3 invalid trials</span>
          </>
        }
        actions={
          <>
            <button className="button secondary" type="button" disabled>
              <Square size={14} />
              Stop pending trials
            </button>
            <button
              className="button secondary"
              type="button"
              onClick={() =>
                downloadTextFile(
                  "exp-031-fixture-manifest.json",
                  JSON.stringify(
                    {
                      fixture: true,
                      experiment: "exp-031",
                      revision: 4,
                      seedBlock: 20260721,
                      baselines: [
                        "round-robin",
                        "haproxy-health",
                        "static-wide",
                        "ebmsh",
                      ],
                      completed: 92,
                      valid: 89,
                      invalid: 3,
                      notice:
                        "Illustrative frontend fixture; raw run artifacts are unavailable.",
                    },
                    null,
                    2,
                  ),
                  "application/json",
                )
              }
            >
              <Download size={14} />
              Fixture manifest
            </button>
          </>
        }
      />
      <section className="experiment-progress">
        <article>
          <span>Completed</span>
          <strong>92</strong>
          <small>89 valid · 3 invalid</small>
        </article>
        <article>
          <span>Running</span>
          <strong>1</strong>
          <small>route-instance · EBMSH</small>
        </article>
        <article>
          <span>Queued</span>
          <strong>67</strong>
          <small>randomized Latin-square order</small>
        </article>
        <article>
          <span>Elapsed</span>
          <strong>11 h 42 m</strong>
          <small>fixture estimate</small>
        </article>
      </section>
      <div className="two-column-layout">
        <Panel title="Manifest" kicker="Pinned inputs">
          <KeyValueGrid
            items={[
              {
                label: "Baselines",
                value: "4 · RR / HAProxy / static-wide / EBMSH",
              },
              { label: "Faults", value: "8 required scenarios" },
              { label: "Pilot blocks", value: 5, mono: true },
              { label: "Load profile", value: "open-loop · low/nominal/high" },
              {
                label: "Images",
                value: "sha256 manifest 4a91…e7cc",
                mono: true,
              },
              { label: "Policy", value: "revision 12", mono: true },
              { label: "Truth ledger", value: "independent fault-runner v2" },
            ]}
          />
        </Panel>
        <Panel title="Run validity" kicker="No silent exclusion">
          <div className="validity-list">
            <div>
              <Check size={15} />
              <span>
                <strong>89 valid runs</strong>
                <small>
                  cleanup, truth, traffic, and artifact checks passed
                </small>
              </span>
            </div>
            <div>
              <AlertTriangle size={15} />
              <span>
                <strong>2 host-contention invalid</strong>
                <small>resource interference exceeded frozen bound</small>
              </span>
            </div>
            <div>
              <AlertTriangle size={15} />
              <span>
                <strong>1 cleanup invalid</strong>
                <small>rig quarantined before next trial</small>
              </span>
            </div>
          </div>
        </Panel>
      </div>
      <Panel title="Scenario × baseline progress" kicker="Matched trial matrix">
        <div className="experiment-matrix">
          <div className="experiment-matrix-head">
            <span>Scenario</span>
            {["Round Robin", "HAProxy checks", "Static-wide", "EBMSH"].map(
              (item) => (
                <span key={item}>{item}</span>
              ),
            )}
          </div>
          {experimentScenarios.map((scenario, row) => (
            <div className="experiment-matrix-row" key={scenario}>
              <strong>{scenario}</strong>
              {[0, 1, 2, 3].map((column) => {
                const complete = row < 4 || (row === 4 && column < 2);
                return (
                  <span
                    className={
                      complete
                        ? "complete"
                        : row === 4 && column === 2
                          ? "running"
                          : "pending"
                    }
                    key={column}
                  >
                    {complete ? (
                      <Check size={13} />
                    ) : row === 4 && column === 2 ? (
                      <CircleDashed size={13} />
                    ) : (
                      "—"
                    )}
                    <small>
                      {complete
                        ? "5/5"
                        : row === 4 && column === 2
                          ? "3/5"
                          : "0/5"}
                    </small>
                  </span>
                );
              })}
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Recent run transitions" kicker="Experiment event trail">
        <Timeline
          items={[
            {
              at: "22:06:12",
              label: "run-0092 completed",
              detail: "EBMSH · route-instance · seed 4912 · valid",
              state: "success",
            },
            {
              at: "22:06:42",
              label: "Cleanup confirmed",
              detail:
                "routes, weights, queues, locks, and fault target returned to baseline",
              state: "success",
            },
            {
              at: "22:07:01",
              label: "run-0093 started",
              detail: "Static-wide · traffic overload · seed 4913",
              state: "warning",
            },
          ]}
        />
      </Panel>
    </div>
  );
}

export function BaselineComparisonPage() {
  const { experimentBaselines } = useDemoSnapshot();
  const [metric, setMetric] = useState("Healthy capacity preserved");
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Matched trial distributions"
        title="Baseline comparison"
        brief={
          <>
            The research view prioritizes distributions, intervals, paired
            effects, excluded trials, and configuration parity. Pilot fixture
            values are illustrative and cannot be presented as a completed
            product claim.
          </>
        }
        meta={
          <>
            <span>Pilot fixture · not confirmatory</span>
            <span>30 illustrative matched trials per baseline</span>
            <span>3 excluded trials shown separately</span>
          </>
        }
        actions={
          <label className="compact-select">
            <span>Metric</span>
            <select
              value={metric}
              onChange={(event) => setMetric(event.target.value)}
            >
              <option>Healthy capacity preserved</option>
              <option>Successful requests</option>
              <option>Retry amplification</option>
              <option>False actions</option>
            </select>
            <ChevronDown size={13} />
          </label>
        }
      />
      <Panel title={metric} kicker="Distribution and interval">
        <IntervalPlot data={experimentBaselines} />
        <div className="notice warning">
          <AlertTriangle size={15} />
          <span>
            Illustrative typed fixture. No statistical or customer claim should
            be inferred from this frontend dataset.
          </span>
        </div>
      </Panel>
      <div className="two-column-layout">
        <Panel
          title="Paired effect summary"
          kicker="Proposed vs declared baselines"
        >
          <div className="effect-table">
            <div>
              <span>vs Plain Round Robin</span>
              <strong>+26 points</strong>
              <small>illustrative interval +19 to +32</small>
            </div>
            <div>
              <span>vs HAProxy health checks</span>
              <strong>+22 points</strong>
              <small>illustrative interval +16 to +29</small>
            </div>
            <div>
              <span>vs Static backend-wide</span>
              <strong>+35 points</strong>
              <small>illustrative interval +28 to +41</small>
            </div>
          </div>
          <p className="limitation-note">
            <ShieldAlert size={14} />
            Final analysis requires predeclared Friedman and Holm-adjusted
            paired comparisons with effect sizes and uncertainty.
          </p>
        </Panel>
        <Panel title="Baseline parity" kicker="Only policy differs">
          <div className="parity-list">
            {[
              "Backend images and route pools",
              "Workload seed and request mix",
              "Capacity and timeout values",
              "Fault target, intensity, and timing",
              "Retry contract and observation windows",
            ].map((item) => (
              <div key={item}>
                <Check size={14} />
                <span>{item}</span>
                <StatusTag tone="success">matched</StatusTag>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel title="Excluded and invalid trials" kicker="Visible by default">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Run</th>
                <th>Baseline</th>
                <th>Scenario</th>
                <th>Reason</th>
                <th>Decision</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <code>run-0041</code>
                </td>
                <td>HAProxy checks</td>
                <td>Slow instance</td>
                <td>Host contention exceeded frozen CPU bound</td>
                <td>
                  <StatusTag tone="warning">
                    excluded before outcome review
                  </StatusTag>
                </td>
              </tr>
              <tr>
                <td>
                  <code>run-0068</code>
                </td>
                <td>EBMSH</td>
                <td>Flapping recovery</td>
                <td>Cleanup watchdog did not confirm baseline state</td>
                <td>
                  <StatusTag tone="warning">rig quarantined</StatusTag>
                </td>
              </tr>
              <tr>
                <td>
                  <code>run-0072</code>
                </td>
                <td>Static-wide</td>
                <td>Overload</td>
                <td>Load generator lost open-loop schedule</td>
                <td>
                  <StatusTag tone="warning">invalid</StatusTag>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}

"use client";

import {
  ArrowRight,
  AlertTriangle,
  Check,
  CircleDashed,
  GitCompareArrows,
  X,
} from "lucide-react";
import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { useMatrix, type MatrixCell } from "@/lib/api/operations";
import { StateMessage, StatusTag } from "@/components/ui";

const routes = ["public", "auth", "catalog", "checkout"];
const instances = ["inst-a", "inst-b", "inst-c"];

function cellState(cell: MatrixCell): { label: string; className: string } {
  if (!cell.observed) return { label: "Unknown", className: "unknown" };
  if (cell.drift) return { label: "Drift", className: "drift" };
  if (cell.desired.admin === "drain" && cell.desired.weight === 0)
    return { label: "Quarantined", className: "quarantined" };
  if ((cell.desired.weight ?? 100) > 0 && (cell.desired.weight ?? 100) < 100)
    return { label: "Reintegrating", className: "reintegrating" };
  if ((cell.evidence.error_rate ?? 0) >= 0.5)
    return { label: "Failing", className: "failing" };
  if ((cell.evidence.error_rate ?? 0) > 0.1)
    return { label: "Elevated 5xx", className: "failing" };
  if ((cell.evidence.samples ?? 0) === 0)
    return { label: "No samples", className: "unknown" };
  return { label: "Healthy", className: "healthy" };
}

function StateIcon({ state }: { state: string }) {
  if (state === "healthy") return <Check size={13} aria-hidden="true" />;
  if (state === "unknown") return <CircleDashed size={13} aria-hidden="true" />;
  if (state === "drift")
    return <GitCompareArrows size={13} aria-hidden="true" />;
  return <AlertTriangle size={13} aria-hidden="true" />;
}

function percent(value?: number | null) {
  return value === null || value === undefined
    ? "—"
    : `${(value * 100).toFixed(1)}%`;
}
function latency(value?: number | null) {
  return value === null || value === undefined ? "—" : `${value.toFixed(1)} ms`;
}

function memberError(cell?: MatrixCell) {
  if (!cell) return "No current evidence";
  const rate = percent(cell.evidence.error_rate);
  const count = cell.evidence.errors ?? 0;
  const samples = cell.evidence.samples ?? 0;
  return `${rate} · ${count}/${samples} errors`;
}

function comparisonHealthy(cell?: MatrixCell) {
  return Boolean(
    cell &&
    (cell.evidence.samples ?? 0) >= 3 &&
    (cell.evidence.error_rate ?? 1) <= 0.1 &&
    cell.direct_probe?.application_ok === true,
  );
}

function MembershipExplanation({
  cell,
  lookup,
}: {
  cell: MatrixCell;
  lookup: Map<string, MatrixCell>;
}) {
  const samples = cell.evidence.samples ?? 0;
  const errors = cell.evidence.errors ?? 0;
  const rate = cell.evidence.error_rate ?? 0;
  const probe = cell.direct_probe;
  const routePeers = instances.filter((item) => item !== cell.instance).map((instance) => ({
    label: `${cell.route} × ${instance}`,
    cell: lookup.get(`${cell.route}/${instance}`),
  }));
  const instanceSiblings = routes.filter((item) => item !== cell.route).map((route) => ({
    label: `${route} × ${cell.instance}`,
    cell: lookup.get(`${route}/${cell.instance}`),
  }));
  const peersHealthy = routePeers.every((peer) => comparisonHealthy(peer.cell));
  const siblingsHealthy = instanceSiblings.every((sibling) => comparisonHealthy(sibling.cell));
  const conditions = [
    { label: "Error threshold ≥50%", pass: rate >= 0.5, actual: `${(rate * 100).toFixed(1)}%` },
    { label: "At least 6 target samples", pass: samples >= 6, actual: `${samples} samples` },
    { label: "Direct endpoint probe fails", pass: probe?.application_ok === false, actual: probe?.application_ok === true ? "probe passed" : probe?.application_ok === false ? `probe failed${probe.status ? ` · HTTP ${probe.status}` : ""}` : "probe unavailable" },
    { label: "Both route peers healthy", pass: peersHealthy, actual: peersHealthy ? "both pass" : "not confirmed" },
    { label: "Sibling routes on this instance healthy", pass: siblingsHealthy, actual: siblingsHealthy ? "all pass" : "not confirmed" },
  ];
  const eligibleToConsider = conditions.every((item) => item.pass);
  const statusCodes = Object.entries(cell.evidence.status_codes ?? {}).sort(([a], [b]) => a.localeCompare(b));
  const successful = Math.max(0, samples - errors);
  const probeDescription = probe?.application_ok === true
    ? `Passed${probe.status ? ` · HTTP ${probe.status}` : ""}`
    : probe?.application_ok === false
      ? `Failed${probe.status ? ` · HTTP ${probe.status}` : ""}`
      : "Unavailable";

  return (
    <section className="membership-explanation" aria-label="How to read this membership">
      <div>
        <span className="section-kicker">What this means</span>
        <h3>{cellState(cell).className === "failing" ? "The request path is impaired, but isolation is not yet proven." : "This is one route membership on a shared physical instance."}</h3>
        <p>
          {cell.route} is the logical pool; {cell.instance} is the physical backend. This row is only <code>{cell.haproxy_backend}/{cell.haproxy_server}</code>. Desired and observed state agree, so HAProxy is still sending traffic to this member.
        </p>
        <p>
          The current window recorded <strong>{errors} errors from {samples} requests</strong> ({(rate * 100).toFixed(1)}%). That is the request error rate, separate from the direct probe below. p95 is the latency at or below which 95% of measured requests completed.
        </p>
      </div>
      <div className="membership-breakdown">
        <div>
          <h3>Response breakdown</h3>
          <ul>
            <li><span>Successful / non-5xx</span><strong>{successful}</strong></li>
            {statusCodes.map(([code, count]) => <li key={code}><span>HTTP {code}</span><strong>{count}</strong></li>)}
            {!statusCodes.length && <li><span>HTTP status counts</span><strong>Unavailable</strong></li>}
          </ul>
        </div>
        <div>
          <h3>Independent endpoint probe</h3>
          <p><strong>{probeDescription}</strong></p>
          <p className="microcopy">A passing probe can coexist with request errors; it checks endpoint reachability and application health independently.</p>
        </div>
      </div>
      <div className="membership-peer-groups">
        <div>
          <h3>Same route on other instances</h3>
          <ul>{routePeers.map((peer) => <li key={peer.label}><code>{peer.label}</code><span>{memberError(peer.cell)}{peer.cell?.direct_probe ? ` · probe ${peer.cell.direct_probe.application_ok ? "pass" : "fail"}` : ""}</span></li>)}</ul>
        </div>
        <div>
          <h3>Other routes on this instance</h3>
          <ul>{instanceSiblings.map((sibling) => <li key={sibling.label}><code>{sibling.label}</code><span>{memberError(sibling.cell)}{sibling.cell?.direct_probe ? ` · probe ${sibling.cell.direct_probe.application_ok ? "pass" : "fail"}` : ""}</span></li>)}</ul>
        </div>
      </div>
      <div className="membership-rule-explanation">
        <h3>{eligibleToConsider ? "Isolation evidence passed" : "Why the controller has not quarantined this member"}</h3>
        <p>A route-only quarantine is considered only when the target has at least 50% errors with 6 or more samples, its direct probe fails, both route peers and all sibling routes on the instance stay healthy, and the capacity/queue safety checks pass.</p>
        <ul className="membership-gates">{conditions.map((item) => <li className={item.pass ? "passed" : "not-passed"} key={item.label}><span aria-hidden="true">{item.pass ? "✓" : "•"}</span><span>{item.label}</span><strong>{item.actual}</strong></li>)}</ul>
        <p>{eligibleToConsider ? "Evidence supports evaluating this smallest scope; the controller still checks remaining capacity, peer queues, and Runtime readback before changing it." : "The controller records this as a warning and preserves the current HAProxy state until the missing isolation evidence is available."}</p>
        {cell.incident_id && <a className="inline-link" href={`/app/incidents?incident=${cell.incident_id}&trace=1`}>Open the full decision trace <ArrowRight size={14} /></a>}
      </div>
    </section>
  );
}

export function LiveRouteMatrix({ compact = false }: { compact?: boolean }) {
  const query = useMatrix();
  const [selected, setSelected] = useState<MatrixCell | null>(null);
  const [active, setActive] = useState("0-0");
  const refs = useRef(new Map<string, HTMLButtonElement>());
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const lookup = useMemo(
    () =>
      new Map(
        (query.data?.cells ?? []).map((cell) => [
          `${cell.route}/${cell.instance}`,
          cell,
        ]),
      ),
    [query.data?.cells],
  );

  useEffect(() => {
    const dialog = dialogRef.current;
    if (selected && dialog && !dialog.open) dialog.showModal();
    if (!selected && dialog?.open) dialog.close();
  }, [selected]);

  function closeDetails() {
    if (dialogRef.current?.open) dialogRef.current.close();
    setSelected(null);
    window.setTimeout(() => triggerRef.current?.focus(), 0);
  }

  function move(
    event: KeyboardEvent<HTMLButtonElement>,
    row: number,
    column: number,
  ) {
    let nextRow = row;
    let nextColumn = column;
    if (event.key === "ArrowRight") nextColumn += 1;
    else if (event.key === "ArrowLeft") nextColumn -= 1;
    else if (event.key === "ArrowDown") nextRow += 1;
    else if (event.key === "ArrowUp") nextRow -= 1;
    else if (event.key === "Home") nextColumn = 0;
    else if (event.key === "End") nextColumn = instances.length - 1;
    else return;
    event.preventDefault();
    nextRow = Math.max(0, Math.min(routes.length - 1, nextRow));
    nextColumn = Math.max(0, Math.min(instances.length - 1, nextColumn));
    const coordinate = `${nextRow}-${nextColumn}`;
    setActive(coordinate);
    refs.current.get(coordinate)?.focus();
  }

  if (query.isLoading)
    return (
      <StateMessage state="loading" title="Reading HAProxy membership state…">
        The matrix waits for observed Runtime state and Prometheus evidence.
      </StateMessage>
    );
  if (query.isError || !query.data)
    return (
      <StateMessage state="failure" title="The live matrix is unavailable.">
        No fixture fallback was used. Check the API and worker status.
      </StateMessage>
    );

  return (
    <div className={`live-matrix ${compact ? "compact" : ""}`}>
      <div className="live-matrix-heading">
        <div>
          <span className="section-kicker">Route × physical instance</span>
          <h2>Desired boundary, observed interior</h2>
        </div>
        <span>
          Readback{" "}
          {query.data.observed_at
            ? new Date(query.data.observed_at).toLocaleTimeString()
            : "unavailable"}
        </span>
      </div>
      {!compact && (
        <div className="notice info">
          HTTP 5xx counts are shown per route/backend over the current evidence window. A degraded incident needs at least 6 real samples, 2 errors, and an error rate above 10%; automatic drain needs at least 50% errors, a failed direct probe, healthy comparison peers, and safe remaining capacity.
        </div>
      )}
      <div className="matrix-scroll">
        <table className="live-matrix-table">
          <caption className="sr-only">
            Live route by instance membership state. Arrow keys navigate cells
            and Enter opens evidence details.
          </caption>
          <thead>
            <tr>
              <th scope="col">Route</th>
              {instances.map((instance) => (
                <th scope="col" key={instance}>
                  <strong>{instance}</strong>
                  <small>capacity 100</small>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {routes.map((route, row) => (
              <tr key={route}>
                <th scope="row">
                  <code>/{route}</code>
                  <small>
                    {lookup.get(`${route}/inst-a`)?.criticality.toLowerCase()}
                  </small>
                </th>
                {instances.map((instance, column) => {
                  const cell = lookup.get(`${route}/${instance}`);
                  if (!cell)
                    return (
                      <td key={instance}>
                        <span className="matrix-missing">No record</span>
                      </td>
                    );
                  const state = cellState(cell);
                  const coordinate = `${row}-${column}`;
                  const description = `${route} on ${instance}: ${state.label}, desired ${cell.desired.admin} weight ${cell.desired.weight}, observed ${cell.observed?.admin_state ?? "unknown"} weight ${cell.observed?.weight ?? "unknown"}, error ${percent(cell.evidence.error_rate)}, p95 ${latency(cell.evidence.p95_ms)}, ${cell.evidence.samples ?? 0} samples`;
                  return (
                    <td
                      className={`desired-${cell.desired.admin} observed-${state.className}`}
                      key={instance}
                    >
                      <button
                        ref={(node) => {
                          if (node) refs.current.set(coordinate, node);
                          else refs.current.delete(coordinate);
                        }}
                        tabIndex={active === coordinate ? 0 : -1}
                        type="button"
                        aria-label={description}
                        onFocus={() => setActive(coordinate)}
                        onKeyDown={(event) => move(event, row, column)}
                        onClick={(event) => {
                          triggerRef.current = event.currentTarget;
                          setSelected(cell);
                        }}
                      >
                        <span className="live-cell-state">
                          <StateIcon state={state.className} />
                          <strong>{state.label}</strong>
                        </span>
                        <span className="live-cell-weight">
                          w {cell.observed?.weight ?? "—"}
                        </span>
                        {!compact && (
                          <span className="live-cell-metrics">
                            <code>{percent(cell.evidence.error_rate)} err</code>
                            {Boolean(cell.evidence.status_codes?.["500"]) && (
                              <code>HTTP 500 × {cell.evidence.status_codes?.["500"]}</code>
                            )}
                            <code>{latency(cell.evidence.p95_ms)}</code>
                            <code>n {cell.evidence.samples ?? 0}</code>
                          </span>
                        )}
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="matrix-legend">
        <span>
          <i className="legend-outline" />
          Outer edge = desired
        </span>
        <span>
          <i className="legend-fill" />
          Interior = observed
        </span>
        <span>
          <i className="legend-drift" />
          Diagonal = drift
        </span>
        <span>Arrow keys move · Enter opens detail</span>
      </div>
      {selected && (
        <dialog
          ref={dialogRef}
          className="live-membership-sheet"
          aria-labelledby="live-membership-title"
          onCancel={(event) => {
            event.preventDefault();
            closeDetails();
          }}
        >
          <header>
            <div>
              <span className="section-kicker">Exact HAProxy membership</span>
              <h2 id="live-membership-title">
                <code>{selected.route}</code> × {selected.instance}
              </h2>
            </div>
            <button
              className="icon-button"
              type="button"
              onClick={closeDetails}
              aria-label="Close membership details"
            >
              <X size={18} />
            </button>
          </header>
          <div className="membership-sheet-state">
            <StatusTag
              tone={
                cellState(selected).className === "healthy"
                  ? "success"
                  : cellState(selected).className === "failing"
                    ? "danger"
                    : "warning"
              }
            >
              {cellState(selected).label}
            </StatusTag>
            {selected.incident_id && (
              <code>incident {selected.incident_id.slice(0, 8)}</code>
            )}
          </div>
          <dl className="live-definition-grid">
            <div>
              <dt>Desired</dt>
              <dd>
                {selected.desired.admin} · weight{" "}
                {selected.desired.weight ?? "—"}
              </dd>
            </div>
            <div>
              <dt>Observed</dt>
              <dd>
                {selected.observed
                  ? `${selected.observed.admin_state} · weight ${selected.observed.weight}`
                  : "No Runtime readback"}
              </dd>
            </div>
            <div>
              <dt>HAProxy target</dt>
              <dd>
                <code>
                  {selected.haproxy_backend}/{selected.haproxy_server}
                </code>
              </dd>
            </div>
            <div>
              <dt>Direct evidence</dt>
              <dd>
                {percent(selected.evidence.error_rate)} errors ·{" "}
                {latency(selected.evidence.p95_ms)}
              </dd>
            </div>
            <div>
              <dt>HTTP 5xx in window</dt>
              <dd>
                {Object.entries(selected.evidence.status_codes ?? {})
                  .filter(([code]) => code.startsWith("5"))
                  .map(([code, count]) => `HTTP ${code}: ${count}`)
                  .join(" · ") || "None observed"}
              </dd>
            </div>
            <div>
              <dt>Real samples</dt>
              <dd>{selected.evidence.samples ?? 0}</dd>
            </div>
            <div>
              <dt>Queue / sessions</dt>
              <dd>
                {selected.observed
                  ? `${selected.observed.queue} / ${selected.observed.sessions}`
                  : "No Runtime readback"}
              </dd>
            </div>
            <div>
              <dt>Direct endpoint probe</dt>
              <dd>
                {selected.direct_probe?.application_ok === true
                  ? `Passed${selected.direct_probe.status ? ` · HTTP ${selected.direct_probe.status}` : ""}`
                  : selected.direct_probe?.application_ok === false
                    ? `Failed${selected.direct_probe.status ? ` · HTTP ${selected.direct_probe.status}` : ""}`
                    : "Unavailable"}
              </dd>
            </div>
          </dl>
          <p className="microcopy membership-window-note">
            Request metrics are from the evidence window ending {query.data.evidence_window_ended_at ? new Date(query.data.evidence_window_ended_at).toLocaleTimeString() : "at an unavailable time"}. Runtime readback is timestamped separately above.
          </p>
          <MembershipExplanation cell={selected} lookup={lookup} />
          {selected.drift && (
            <div className="notice warning">
              <GitCompareArrows size={15} />
              <span>
                Desired and observed state do not align. Automatic advancement
                is blocked.
              </span>
            </div>
          )}
        </dialog>
      )}
    </div>
  );
}

"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronDown,
  CircleDashed,
  Eye,
  Filter,
  Gauge,
  GitCompareArrows,
  Grid3X3,
  List,
  RotateCcw,
  Search,
  ShieldAlert,
  Timer,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { instances, matrixCells, routes } from "@/lib/fixtures";
import type { MatrixCellData, MembershipState } from "@/lib/types";
import { KeyValueGrid, StatusTag } from "@/components/ui";

type Density = "overview" | "operational" | "forensic";
type MatrixMode = "matrix" | "table";

const stateLabel: Record<MembershipState, string> = {
  healthy: "Ready",
  degraded: "Degraded",
  failing: "Failing",
  quarantined: "Quarantined",
  verifying: "Verifying",
  reintegrating: "Reintegrating",
  unknown: "Unknown",
  "no-membership": "Not in pool",
};

function stateIcon(cell: MatrixCellData) {
  if (cell.state === "healthy") return <Check size={13} aria-hidden="true" />;
  if (cell.state === "unknown") return <CircleDashed size={13} aria-hidden="true" />;
  if (cell.state === "no-membership") return <span aria-hidden="true">—</span>;
  if (cell.marker === "drift") return <GitCompareArrows size={13} aria-hidden="true" />;
  return <AlertTriangle size={13} aria-hidden="true" />;
}

function formatPercent(value: number | null) {
  return value === null ? "—" : `${value.toFixed(1)}%`;
}

function formatLatency(value: number | null) {
  return value === null ? "—" : `${value} ms`;
}

function formatRouting(state: MatrixCellData["desired"]) {
  if (state.admin === "none") return "No membership";
  if (state.admin === "unavailable") return "Unavailable";
  return `${state.admin} · ${state.weight ?? "—"}`;
}

function MatrixCell({
  cell,
  density,
  row,
  column,
  register,
  onMove,
  onSelect,
  active,
  onActivate,
}: {
  cell: MatrixCellData;
  density: Density;
  row: number;
  column: number;
  register: (element: HTMLButtonElement | null, row: number, column: number) => void;
  onMove: (event: KeyboardEvent<HTMLButtonElement>, row: number, column: number) => void;
  onSelect: (cell: MatrixCellData) => void;
  active: boolean;
  onActivate: () => void;
}) {
  const drift = cell.desired.admin !== cell.observed.admin || cell.desired.weight !== cell.observed.weight;
  const route = routes.find((item) => item.id === cell.routeId)!;
  const instance = instances.find((item) => item.id === cell.instanceId)!;
  const fullLabel = `${route.label}, ${instance.label}, ${stateLabel[cell.state]}, desired ${formatRouting(cell.desired)}, observed ${formatRouting(cell.observed)}, effective weight ${cell.effectiveWeight ?? "not applicable"}, error rate ${formatPercent(cell.errorRate)}, p95 latency ${formatLatency(cell.p95Ms)}, ${cell.sampleCount} samples, ${cell.freshnessSeconds === null ? "no telemetry" : `${cell.freshnessSeconds} seconds old`}`;
  return (
    <button
      ref={(element) => register(element, row, column)}
      className={`matrix-cell-button state-${cell.state} ${cell.marker ? `marker-${cell.marker}` : ""} ${drift ? "has-drift" : ""} density-${density}`}
      type="button"
      tabIndex={active ? 0 : -1}
      aria-label={fullLabel}
      onFocus={onActivate}
      onKeyDown={(event) => onMove(event, row, column)}
      onClick={() => onSelect(cell)}
    >
      <span className="desired-frame" aria-hidden="true" />
      <span className="observed-fill" aria-hidden="true" />
      <span className="cell-primary"><span>{stateIcon(cell)}{stateLabel[cell.state]}</span>{drift && <em>DRIFT</em>}</span>
      <span className="cell-weight">{cell.effectiveWeight === null ? "—" : cell.marker === "reintegration" ? `${cell.effectiveWeight}% stage` : `w ${cell.effectiveWeight}`}</span>
      <span className="cell-deviation">{cell.deviation}</span>
      {density !== "overview" && <span className="cell-operational"><span>{formatPercent(cell.errorRate)} err</span><span>{formatLatency(cell.p95Ms)}</span><span>n {cell.sampleCount}</span></span>}
      {density === "forensic" && <span className="cell-forensic"><span>D {formatRouting(cell.desired)}</span><span>O {formatRouting(cell.observed)}</span><span>{cell.freshnessSeconds === null ? "no evidence" : `${cell.freshnessSeconds}s old`}</span></span>}
      <span className="matrix-hover-card" role="tooltip">
        <strong>{route.label} × {instance.label}</strong>
        <span>{cell.note}</span>
        <span className="hover-metrics"><code>{formatPercent(cell.errorRate)} errors</code><code>{formatLatency(cell.p95Ms)} p95</code><code>n={cell.sampleCount}</code></span>
        <small>Press Enter for comparisons and state details.</small>
      </span>
    </button>
  );
}

function MembershipSheet({ cell, onClose }: { cell: MatrixCellData; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const route = routes.find((item) => item.id === cell.routeId)!;
  const instance = instances.find((item) => item.id === cell.instanceId)!;
  const sameRoute = matrixCells.filter((item) => item.routeId === cell.routeId && item.instanceId !== cell.instanceId);
  const sameInstance = matrixCells.filter((item) => item.instanceId === cell.instanceId && item.routeId !== cell.routeId);
  const drift = cell.desired.admin !== cell.observed.admin || cell.desired.weight !== cell.observed.weight;

  useEffect(() => {
    const dialog = dialogRef.current;
    triggerRef.current = document.activeElement as HTMLElement | null;
    if (dialog && !dialog.open) dialog.showModal();
    window.setTimeout(() => closeRef.current?.focus(), 0);
    return () => {
      if (dialog?.open) dialog.close();
    };
  }, []);

  function closeSheet() {
    if (dialogRef.current?.open) dialogRef.current.close();
    onClose();
    window.setTimeout(() => triggerRef.current?.focus(), 0);
  }

  return (
    <dialog className="matrix-sheet" ref={dialogRef} onCancel={(event) => { event.preventDefault(); closeSheet(); }} aria-labelledby="membership-title">
      <header><div><span className="section-kicker">Logical membership</span><h2 id="membership-title"><code>{route.label}</code> × {instance.label}</h2></div><button ref={closeRef} className="icon-button" type="button" onClick={closeSheet} aria-label="Close membership details"><X size={18} /></button></header>
      <div className={`sheet-state-summary state-${cell.state}`}><span className="summary-icon">{stateIcon(cell)}</span><div><strong>{stateLabel[cell.state]}{drift ? " · desired and observed differ" : ""}</strong><p>{cell.note}</p></div></div>

      <section className="sheet-section"><h3>Desired and observed</h3><div className="comparison-pair"><article><span>Desired state</span><strong>{formatRouting(cell.desired)}</strong><small>Durable controller intent</small></article><ArrowRight size={16} aria-hidden="true" /><article className={drift ? "mismatch" : "match"}><span>Observed state</span><strong>{formatRouting(cell.observed)}</strong><small>{drift ? "HAProxy differs from intent" : "Runtime readback matches"}</small></article></div></section>

      <section className="sheet-section"><h3>Evidence</h3><KeyValueGrid items={[
        { label: "Effective weight", value: cell.effectiveWeight ?? "Not applicable", mono: true },
        { label: "Error rate", value: formatPercent(cell.errorRate), mono: true },
        { label: "p95 latency", value: formatLatency(cell.p95Ms), mono: true },
        { label: "Real samples", value: cell.sampleCount.toLocaleString(), mono: true },
        { label: "Freshness", value: cell.freshnessSeconds === null ? "No telemetry" : `${cell.freshnessSeconds} s`, mono: true },
        { label: "Evidence state", value: cell.evidence },
      ]} /></section>

      <section className="sheet-section"><h3>Same-route peers</h3><div className="peer-list">{sameRoute.map((peer) => { const peerInstance = instances.find((item) => item.id === peer.instanceId)!; return <div key={peer.instanceId}><span><strong>{peerInstance.label}</strong><small>{stateLabel[peer.state]}</small></span><code>{formatPercent(peer.errorRate)} · {formatLatency(peer.p95Ms)}</code></div>; })}</div></section>
      <section className="sheet-section"><h3>Same instance, other routes</h3><div className="peer-list">{sameInstance.map((peer) => { const peerRoute = routes.find((item) => item.id === peer.routeId)!; return <div key={peer.routeId}><span><strong>{peerRoute.label}</strong><small>{stateLabel[peer.state]}</small></span><code>w {peer.effectiveWeight ?? "—"}</code></div>; })}</div></section>

      <footer>{cell.incidentId ? <Link className="button primary" href={`/app/incidents/${cell.incidentId}/decision-trace`}>Open Decision Trace<ArrowRight size={15} /></Link> : <Link className="button secondary" href="/app/incidents/inc-1042/decision-trace">Compare with active trace</Link>}<span className="microcopy">Selection never changes traffic.</span></footer>
    </dialog>
  );
}

export function RouteInstanceMatrix({ compact = false }: { compact?: boolean }) {
  const [density, setDensity] = useState<Density>(compact ? "overview" : "operational");
  const [mode, setMode] = useState<MatrixMode>("matrix");
  const [selected, setSelected] = useState<MatrixCellData | null>(null);
  const [routeFilter, setRouteFilter] = useState("all");
  const [stateFilter, setStateFilter] = useState("all");
  const [versionFilter, setVersionFilter] = useState("all");
  const [criticalityFilter, setCriticalityFilter] = useState("all");
  const [freshnessFilter, setFreshnessFilter] = useState("all");
  const [incidentOnly, setIncidentOnly] = useState(false);
  const [activeCoordinate, setActiveCoordinate] = useState("0-0");
  const refs = useRef(new Map<string, HTMLButtonElement>());

  const visibleInstances = useMemo(() => instances.filter((instance) => versionFilter === "all" || instance.version === versionFilter), [versionFilter]);
  const visibleRoutes = useMemo(() => routes.filter((route) => {
    if (routeFilter !== "all" && route.id !== routeFilter) return false;
    if (criticalityFilter !== "all" && route.criticality !== criticalityFilter) return false;
    if (incidentOnly && route.id !== "checkout") return false;
    if (stateFilter !== "all" && !matrixCells.some((cell) => cell.routeId === route.id && cell.state === stateFilter)) return false;
    if (freshnessFilter === "stale" && !matrixCells.some((cell) => cell.routeId === route.id && (cell.evidence === "stale" || cell.evidence === "missing"))) return false;
    return true;
  }), [criticalityFilter, freshnessFilter, incidentOnly, routeFilter, stateFilter]);

  const hiddenCritical = matrixCells.filter((cell) => (cell.state === "quarantined" || cell.marker === "drift") && (!visibleRoutes.some((route) => route.id === cell.routeId) || !visibleInstances.some((instance) => instance.id === cell.instanceId))).length;

  useEffect(() => {
    setActiveCoordinate("0-0");
  }, [visibleInstances, visibleRoutes]);

  useEffect(() => {
    const requestedRoute = new URLSearchParams(window.location.search).get("route");
    if (requestedRoute && routes.some((route) => route.id === requestedRoute)) setRouteFilter(requestedRoute);
  }, []);

  function register(element: HTMLButtonElement | null, row: number, column: number) {
    const key = `${row}-${column}`;
    if (element) refs.current.set(key, element);
    else refs.current.delete(key);
  }

  function move(event: KeyboardEvent<HTMLButtonElement>, row: number, column: number) {
    let nextRow = row;
    let nextColumn = column;
    if (event.key === "ArrowRight") nextColumn += 1;
    else if (event.key === "ArrowLeft") nextColumn -= 1;
    else if (event.key === "ArrowDown") nextRow += 1;
    else if (event.key === "ArrowUp") nextRow -= 1;
    else if (event.key === "Home") nextColumn = 0;
    else if (event.key === "End") nextColumn = visibleInstances.length - 1;
    else return;
    event.preventDefault();
    nextRow = Math.max(0, Math.min(visibleRoutes.length - 1, nextRow));
    nextColumn = Math.max(0, Math.min(visibleInstances.length - 1, nextColumn));
    setActiveCoordinate(`${nextRow}-${nextColumn}`);
    refs.current.get(`${nextRow}-${nextColumn}`)?.focus();
  }

  function resetFilters() {
    setRouteFilter("all");
    setStateFilter("all");
    setVersionFilter("all");
    setCriticalityFilter("all");
    setFreshnessFilter("all");
    setIncidentOnly(false);
  }

  if (compact) {
    return (
      <div className="matrix-compact-wrap">
        <div className="matrix-compact-header"><div><span className="section-kicker">Route × physical instance</span><h2>Logical membership state</h2></div><Link className="inline-link" href="/app/traffic/matrix">Open matrix<ArrowRight size={14} /></Link></div>
        <div className="matrix-scroll"><MatrixTable density={density} mode="matrix" visibleRoutes={routes.slice(0, 4)} visibleInstances={instances} register={register} move={move} onSelect={setSelected} activeCoordinate={activeCoordinate} onActivate={setActiveCoordinate} /></div>
        <div className="matrix-legend"><span><i className="legend-outline" />Outline = desired</span><span><i className="legend-fill" />Fill = observed</span><span><i className="legend-drift" />Diagonal = drift</span><span><i className="legend-hatch" />Hatch = no membership</span></div>
        {selected && <MembershipSheet cell={selected} onClose={() => setSelected(null)} />}
      </div>
    );
  }

  return (
    <div className="matrix-page-body">
      <div className="matrix-toolbar" aria-label="Matrix controls">
        <div className="matrix-filter-row">
          <label><span>Route</span><select value={routeFilter} onChange={(event) => setRouteFilter(event.target.value)}><option value="all">All routes</option>{routes.map((route) => <option value={route.id} key={route.id}>{route.label}</option>)}</select><ChevronDown size={13} /></label>
          <label><span>State</span><select value={stateFilter} onChange={(event) => setStateFilter(event.target.value)}><option value="all">All states</option><option value="quarantined">Quarantined</option><option value="reintegrating">Reintegrating</option><option value="unknown">Unknown</option><option value="healthy">Ready</option></select><ChevronDown size={13} /></label>
          <label><span>Version</span><select value={versionFilter} onChange={(event) => setVersionFilter(event.target.value)}><option value="all">All versions</option><option value="demo-v1">demo-v1</option><option value="demo-v2">demo-v2</option></select><ChevronDown size={13} /></label>
          <label><span>Criticality</span><select value={criticalityFilter} onChange={(event) => setCriticalityFilter(event.target.value)}><option value="all">All criticality</option><option value="critical">Critical</option><option value="high">High</option><option value="standard">Standard</option></select><ChevronDown size={13} /></label>
          <label><span>Freshness</span><select value={freshnessFilter} onChange={(event) => setFreshnessFilter(event.target.value)}><option value="all">All freshness</option><option value="stale">Stale or missing</option></select><ChevronDown size={13} /></label>
          <button className={`filter-toggle ${incidentOnly ? "active" : ""}`} type="button" aria-pressed={incidentOnly} onClick={() => setIncidentOnly((value) => !value)}><ShieldAlert size={14} />Active incident</button>
          <button className="icon-button" type="button" onClick={resetFilters} aria-label="Reset filters" title="Reset filters"><RotateCcw size={15} /></button>
        </div>
        <div className="matrix-view-controls">
          <div className="segmented-control" aria-label="Matrix density">{(["overview", "operational", "forensic"] as const).map((item) => <button type="button" aria-pressed={density === item} className={density === item ? "active" : ""} onClick={() => setDensity(item)} key={item}>{item[0].toUpperCase() + item.slice(1)}</button>)}</div>
          <div className="segmented-control icon-segments" aria-label="Matrix presentation"><button type="button" className={mode === "matrix" ? "active" : ""} aria-pressed={mode === "matrix"} onClick={() => setMode("matrix")}><Grid3X3 size={14} />Matrix</button><button type="button" className={mode === "table" ? "active" : ""} aria-pressed={mode === "table"} onClick={() => setMode("table")}><List size={14} />Table</button></div>
        </div>
      </div>
      {hiddenCritical > 0 && <div className="hidden-critical-notice" role="status"><AlertTriangle size={15} /><span>{hiddenCritical} quarantined or drifting {hiddenCritical === 1 ? "cell is" : "cells are"} hidden by filters.</span><button type="button" onClick={resetFilters}>Show all</button></div>}
      {!visibleRoutes.length || !visibleInstances.length ? <div className="matrix-empty"><Search size={22} /><strong>No memberships match these filters.</strong><button type="button" onClick={resetFilters}>Reset filters</button></div> : <div className="matrix-scroll full"><MatrixTable density={density} mode={mode} visibleRoutes={visibleRoutes} visibleInstances={visibleInstances} register={register} move={move} onSelect={setSelected} activeCoordinate={activeCoordinate} onActivate={setActiveCoordinate} /></div>}
      <div className="matrix-footer"><div className="matrix-legend"><span><i className="legend-outline" />Desired frame</span><span><i className="legend-fill" />Observed interior</span><span><i className="legend-drift" />Desired / observed drift</span><span><i className="legend-hatch" />No membership</span><span><i className="legend-dots" />Missing telemetry</span></div><span className="keyboard-hint">Arrow keys move · Enter opens details · Home/End move across row</span></div>
      {selected && <MembershipSheet cell={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

function MatrixTable({
  density,
  mode,
  visibleRoutes,
  visibleInstances,
  register,
  move,
  onSelect,
  activeCoordinate,
  onActivate,
}: {
  density: Density;
  mode: MatrixMode;
  visibleRoutes: typeof routes;
  visibleInstances: typeof instances;
  register: (element: HTMLButtonElement | null, row: number, column: number) => void;
  move: (event: KeyboardEvent<HTMLButtonElement>, row: number, column: number) => void;
  onSelect: (cell: MatrixCellData) => void;
  activeCoordinate: string;
  onActivate: (coordinate: string) => void;
}) {
  if (mode === "table") {
    return (
      <table className="accessible-matrix-table">
        <caption className="sr-only">Route membership desired and observed state</caption>
        <thead><tr><th>Route</th><th>Physical instance</th><th>State</th><th>Desired</th><th>Observed</th><th>Weight</th><th>Error</th><th>p95</th><th>Samples</th><th>Freshness</th></tr></thead>
        <tbody>{visibleRoutes.flatMap((route) => visibleInstances.map((instance) => { const cell = matrixCells.find((item) => item.routeId === route.id && item.instanceId === instance.id)!; return <tr key={`${route.id}-${instance.id}`}><th><code>{route.label}</code></th><td>{instance.label}</td><td><button type="button" className="table-state-button" onClick={() => onSelect(cell)}>{stateIcon(cell)}{stateLabel[cell.state]}</button></td><td className="mono">{formatRouting(cell.desired)}</td><td className="mono">{formatRouting(cell.observed)}</td><td className="mono">{cell.effectiveWeight ?? "—"}</td><td className="mono">{formatPercent(cell.errorRate)}</td><td className="mono">{formatLatency(cell.p95Ms)}</td><td className="mono">{cell.sampleCount}</td><td className="mono">{cell.freshnessSeconds === null ? "none" : `${cell.freshnessSeconds}s`}</td></tr>; }))}</tbody>
      </table>
    );
  }
  return (
    <table className={`route-matrix density-${density}`}>
      <caption className="sr-only">Route by physical backend instance matrix. Desired state is the cell outline and observed state is the cell interior.</caption>
      <thead><tr><th className="route-axis"><span>Logical route</span><small>criticality · retry</small></th>{visibleInstances.map((instance) => <th key={instance.id} scope="col"><div className="instance-header"><div><strong>{instance.label}</strong><code>{instance.server}</code></div><StatusTag tone={instance.probe === "passing" ? "success" : instance.probe === "degraded" ? "warning" : "neutral"}>{instance.probe}</StatusTag><span><code>{instance.version}</code> · capacity {instance.capacity}</span><div className="capacity-line"><i style={{ width: `${instance.utilization}%` }} /><small>{instance.utilization}% physical load</small></div>{instance.id === "inst-b" && <em>1 of 4 memberships quarantined</em>}</div></th>)}</tr></thead>
      <tbody>{visibleRoutes.map((route, row) => <tr key={route.id}><th scope="row"><div className="route-header"><code>{route.label}</code><span>{route.criticality}</span><small>{route.requestsPerSecond} req/s</small><small>{route.retryPolicy}</small></div></th>{visibleInstances.map((instance, column) => { const cell = matrixCells.find((item) => item.routeId === route.id && item.instanceId === instance.id)!; const coordinate = `${row}-${column}`; return <td key={instance.id}><MatrixCell cell={cell} density={density} row={row} column={column} register={register} onMove={move} onSelect={onSelect} active={activeCoordinate === coordinate} onActivate={() => onActivate(coordinate)} /></td>; })}</tr>)}</tbody>
    </table>
  );
}

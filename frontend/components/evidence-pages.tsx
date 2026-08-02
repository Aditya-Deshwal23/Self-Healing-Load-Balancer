"use client";

import {
  AlertTriangle,
  ChevronDown,
  CircleDashed,
  Clock3,
  Download,
  Filter,
  Search,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react";
import { useMemo, useState } from "react";
import { errorSeries, logRows, trafficSeries } from "@/lib/fixtures";
import { csvRow, downloadTextFile } from "@/lib/client-download";
import { EvidenceChart } from "@/components/charts";
import { PageHeader, Panel, StateMessage, StatusTag } from "@/components/ui";

export function MetricsPage() {
  const [dashboard, setDashboard] = useState("Data-plane health");
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Curated Prometheus evidence" title="Metrics" brief={<>The browser consumes authorized API projections, not Prometheus directly. Every panel names its unit, aggregation, timezone, sample count, evidence window, and missing intervals.</>} meta={<><span>Fixture source · Prometheus unavailable in Phase 2</span><span>Asia/Kolkata</span><span>15 minute window</span></>} actions={<><button className="button secondary" type="button" onClick={() => downloadTextFile("shlb-metrics-fixture.csv", [csvRow(["time", "request_rate", "public_rate", "checkout_b_error", "checkout_peer_error"]), ...trafficSeries.map((point, index) => csvRow([point.time, point.value ?? "", point.peer ?? "", errorSeries[index]?.value ?? "", errorSeries[index]?.peer ?? ""]))].join("\n"))}><Download size={15} />Export visible data</button></>} />
      <div className="dashboard-toolbar"><label><span>Dashboard</span><select value={dashboard} onChange={(event) => setDashboard(event.target.value)}><option>Data-plane health</option><option>Scope and decision quality</option><option>Control-loop safety</option><option>Recovery</option></select><ChevronDown size={13} /></label><label className="prom-query"><span>Prometheus expression · Operator/Researcher only</span><input disabled placeholder="Server-owned templates in Viewer mode" /></label></div>
      <div className="chart-grid"><Panel title="Request rate" kicker="shlb_http_requests_total"><EvidenceChart title="Original requests" summary="Environment traffic remained between 151 and 171 requests per second in the selected fixture window." data={trafficSeries} unit=" req/s" sampleCount={18442} yDomain={[0, 200]} actionAt="22:02" series={[{ key: "value", label: "environment", color: "var(--accent-copper)" }, { key: "peer", label: "/public", color: "var(--neutral)", dashed: true }]} /></Panel><Panel title="Checkout error family" kicker="shlb_http_errors_total"><EvidenceChart title="Errors by selected cohort" summary="Checkout on Backend B diverged while its peers stayed near three percent. The affected target stops receiving new requests after the action marker." data={errorSeries} unit="%" sampleCount={3428} yDomain={[0, 20]} actionAt="22:02" series={[{ key: "value", label: "checkout/B", color: "var(--danger)" }, { key: "peer", label: "checkout peers", color: "var(--accent-copper)", dashed: true }]} /></Panel></div>
      <div className="metric-panel-grid"><MetricPanel title="Control-loop lag" value="4 s" unit="seconds" samples="180 iterations" state="fixture" bars={[22, 28, 24, 31, 27, 33, 30, 26]} /><MetricPanel title="Retry amplification" value="1.03×" unit="attempts / request" samples="18,442 requests" state="complete" bars={[30, 31, 30, 34, 33, 31, 30, 31]} /><MetricPanel title="Eligible capacity" value="83%" unit="route-weight capacity" samples="15 memberships" state="complete" bars={[84, 84, 83, 67, 80, 82, 83, 83]} /><MetricPanel title="Auth/C evidence" value="Unknown" unit="route-member window" samples="0 fresh samples" state="missing" bars={[42, 48, 44, 0, 0, 0, 0, 0]} /></div>
      <StateMessage state="stale" title="One series has a missing interval.">Auth on Backend C is 94 seconds old. The last confirmed value is retained with its time; the gap is not interpolated and does not count as healthy.</StateMessage>
    </div>
  );
}

function MetricPanel({ title, value, unit, samples, state, bars }: { title: string; value: string; unit: string; samples: string; state: string; bars: number[] }) {
  return <article className={`metric-panel ${state}`}><div><span>{title}</span><StatusTag tone={state === "missing" ? "warning" : state === "complete" ? "success" : "neutral"}>{state}</StatusTag></div><strong>{value}</strong><small>{unit} · {samples} · IST · 15 min</small><div className="metric-spark-bars" aria-hidden="true">{bars.map((value, index) => <i style={{ height: `${value}%` }} key={index} />)}</div><details><summary>Accessible summary</summary><p>{title}: {value} {unit}, based on {samples}, in the 15 minute fixture window.</p></details></article>;
}

export function LogsPage() {
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [selected, setSelected] = useState<(typeof logRows)[number] | null>(null);
  const rows = useMemo(() => logRows.filter((row) => (source === "all" || row.source === source) && `${row.event} ${row.route} ${row.member} ${row.correlation}`.toLowerCase().includes(query.toLowerCase())), [query, source]);
  return (
    <div className="page-stack logs-page">
      <PageHeader eyebrow="Bounded structured events" title="Logs" brief={<>Inspect safe, project-scoped event fields and pivot by correlation. Request or response bodies, cookies, authorization values, raw queries, and user identifiers are unavailable by design.</>} meta={<><span>5 fixture events</span><span>21 Jul 2026 · IST</span><span>redaction policy v3</span></>} actions={<button className="button secondary" type="button" onClick={() => downloadTextFile("shlb-structured-events-fixture.csv", [csvRow(["time", "source", "event", "route", "member", "result", "duration", "correlation"]), ...rows.map((row) => csvRow([row.at, row.source, row.event, row.route, row.member, row.result, row.duration, row.correlation]))].join("\n"))}><Download size={15} />Bounded export</button>} />
      <div className="log-histogram" aria-label="Event count by minute"><div className="histogram-bars" aria-hidden="true">{[28, 32, 24, 48, 61, 38, 44, 56, 72, 49, 34, 42, 31, 28, 35].map((value, index) => <i style={{ height: `${value}%` }} key={index} />)}</div><div><span>21:54</span><span>Action 22:02</span><span>22:09</span></div></div>
      <div className="list-toolbar"><label className="search-field"><Search size={15} /><span className="sr-only">Search structured events</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter event, route, member, or correlation ID" /></label><label><span>Source</span><select value={source} onChange={(event) => setSource(event.target.value)}><option value="all">All sources</option><option value="haproxy">HAProxy</option><option value="nginx">NGINX</option><option value="controller">Controller</option><option value="worker">Worker</option></select><ChevronDown size={13} /></label><button className="button secondary compact" type="button" disabled title="Server-owned safe-field templates require the control API"><Filter size={14} />Safe field filter</button></div>
      <div className={`logs-layout ${selected ? "with-inspector" : ""}`}><section className="panel table-panel"><div className="table-scroll"><table className="data-table log-table"><thead><tr><th>Time</th><th>Source</th><th>Event</th><th>Route / member</th><th>Result</th><th>Duration</th><th>Correlation</th></tr></thead><tbody>{rows.map((row) => <tr className={selected === row ? "selected" : ""} key={`${row.at}-${row.correlation}`} onClick={() => setSelected(row)}><td><time>{row.at}</time></td><td><StatusTag tone="neutral">{row.source}</StatusTag></td><td><button type="button" onClick={() => setSelected(row)}>{row.event}</button></td><td><code>{row.route}</code><small>{row.member}</small></td><td><StatusTag tone={row.result === "2xx" ? "success" : row.result.includes("gap") || row.result.includes("drift") ? "warning" : "neutral"}>{row.result}</StatusTag></td><td className="mono">{row.duration}</td><td><code>{row.correlation}</code></td></tr>)}</tbody></table></div>{!rows.length && <StateMessage state="empty" title="No structured events match.">Change the safe filters; raw payload search is intentionally unavailable.</StateMessage>}</section>{selected && <aside className="log-inspector" aria-labelledby="log-inspector-title"><div><span className="section-kicker">Structured event</span><h2 id="log-inspector-title">{selected.event}</h2><button className="icon-button" type="button" onClick={() => setSelected(null)} aria-label="Close event inspector">×</button></div><dl><dt>@timestamp</dt><dd><code>2026-07-21T{selected.at}+05:30</code></dd><dt>source_component</dt><dd><code>{selected.source}</code></dd><dt>route_id</dt><dd><code>{selected.route}</code></dd><dt>backend_id</dt><dd><code>{selected.member}</code></dd><dt>outcome</dt><dd><code>{selected.result}</code></dd><dt>duration</dt><dd><code>{selected.duration}</code></dd><dt>correlation_id</dt><dd><code>{selected.correlation}</code></dd><dt>schema_version</dt><dd><code>3</code></dd></dl><div className="redaction-list"><strong><ShieldCheck size={14} />Redacted / unavailable</strong><span>authorization</span><span>cookie</span><span>query values</span><span>request body</span><span>response body</span><span>client identity</span></div></aside>}</div>
      <div className="notice neutral"><TerminalSquare size={15} /><span>Kibana may remain an admin-only deep link in a full lab. Incident-linked evidence and safe fields stay owned by this console.</span></div>
    </div>
  );
}

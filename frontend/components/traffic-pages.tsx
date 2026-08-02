"use client";

import Link from "next/link";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronDown,
  ChevronRight,
  CircleDashed,
  DatabaseZap,
  GitCompareArrows,
  Network,
  Search,
  Server,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import { errorSeries, instances, matrixCells, routes, trafficSeries } from "@/lib/fixtures";
import { EvidenceChart } from "@/components/charts";
import { LiveTopology } from "@/components/topology";
import { RouteInstanceMatrix } from "@/components/matrix";
import { KeyValueGrid, PageHeader, Panel, StateMessage, StatusTag, Timeline } from "@/components/ui";

export function TopologyPage() {
  return (
    <div className="page-stack topology-page">
      <PageHeader eyebrow="Stable request graph" title="Live topology" brief={<>NGINX forwards application traffic directly to HAProxy. Four route-specific pools share three physical instances; Backend B remains one machine even though its checkout membership is quarantined.</>} meta={<><span>Observed fixture 22:09 IST</span><span>159 req/s</span><span>300 unique physical capacity units</span><span>1 route-local quarantine</span></>} actions={<Link className="button secondary" href="/app/traffic/matrix">Route matrix<ArrowRight size={15} /></Link>} />
      <Panel title="Request and dependency path" kicker="Client → NGINX → HAProxy → logical pool → physical instance → dependency" className="full-topology-panel"><LiveTopology /></Panel>
      <div className="three-column-summary"><article><span>Edge and data plane</span><strong>NGINX → HAProxy</strong><small>Control API is not in the application request path.</small></article><article><span>Logical memberships</span><strong>14 configured</strong><small>One route membership can change independently.</small></article><article><span>Physical capacity</span><strong>3 × 100 units</strong><small>Never multiplied by route membership count.</small></article></div>
    </div>
  );
}

export function MatrixPage() {
  return (
    <div className="page-stack matrix-page">
      <PageHeader eyebrow="Primary isolation view" title="Route × instance matrix" brief={<>Rows are logical route groups; columns are physical instances. The outline is durable desired state, the interior is observed HAProxy state, and diagonal treatment identifies drift.</>} meta={<><span>5 route groups</span><span>3 physical instances</span><span>14 populated memberships</span><span>1 no-membership topology fact</span></>} actions={<Link className="button secondary" href="/app/incidents/inc-1042/decision-trace">Active Decision Trace<ArrowRight size={15} /></Link>} />
      <section className="panel matrix-primary-panel"><RouteInstanceMatrix /></section>
    </div>
  );
}

export function BackendInventoryPage() {
  const [query, setQuery] = useState("");
  const rows = instances.filter((item) => `${item.label} ${item.version} ${item.server}`.toLowerCase().includes(query.toLowerCase()));
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Physical capacity ledger" title="Backend inventory" brief={<>Each physical backend appears once. Route membership state is independent, but utilization and configured capacity remain attributes of the physical instance.</>} meta={<><span>3 registered instances</span><span>300 capacity units</span><span>1 active route-local incident</span></>} />
      <div className="list-toolbar"><label className="search-field"><Search size={15} /><span className="sr-only">Search backends</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search backend, server alias, or version" /></label><label><span>Group by</span><select defaultValue="version"><option value="version">Deployment version</option><option value="service">Service</option><option value="none">No grouping</option></select><ChevronDown size={13} /></label></div>
      <section className="panel table-panel"><div className="table-scroll"><table className="data-table backend-table"><thead><tr><th>Physical instance</th><th>Version</th><th>Aggregate state</th><th>Route memberships</th><th>Physical capacity</th><th>Probe / last traffic</th><th>Incident</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{rows.map((instance) => <tr key={instance.id}><td><Link href={`/app/backends/${instance.id}`}><Server size={15} /><span><strong>{instance.label}</strong><code>{instance.server}</code><small>{instance.addressAlias}</small></span></Link></td><td><code>{instance.version}</code></td><td><StatusTag tone={instance.id === "inst-b" ? "warning" : instance.probe === "unknown" ? "neutral" : "success"}>{instance.id === "inst-b" ? "ROUTE-LOCAL ISSUE" : instance.probe === "unknown" ? "PARTIAL EVIDENCE" : "READY"}</StatusTag></td><td><strong>{instance.id === "inst-c" ? "4" : "5"}</strong><small>{instance.id === "inst-b" ? "1 quarantined · 4 eligible" : instance.id === "inst-c" ? "1 no membership" : "all eligible"}</small></td><td><div className="capacity-table-cell"><span><i style={{ width: `${instance.utilization}%` }} /></span><code>{instance.utilization}% / {instance.capacity}</code></div></td><td><StatusTag tone={instance.probe === "passing" ? "success" : instance.probe === "degraded" ? "warning" : "neutral"}>{instance.probe}</StatusTag><small>{instance.lastTrafficSeconds}s ago</small></td><td>{instance.id === "inst-b" ? <Link href="/app/incidents/inc-1042"><code>inc-1042</code></Link> : "—"}</td><td><Link className="icon-button" href={`/app/backends/${instance.id}`} aria-label={`Open ${instance.label}`}><ChevronRight size={16} /></Link></td></tr>)}</tbody></table></div>{!rows.length && <StateMessage state="empty" title="No backend matches this search.">Clear the query to return to the physical inventory.</StateMessage>}</section>
      <div className="notice neutral"><DatabaseZap size={15} /><span>Addresses are fixture aliases. A Viewer may receive redacted endpoint data under the future RBAC contract.</span></div>
    </div>
  );
}

export function BackendDetailsPage({ backendId = "inst-b" }: { backendId?: string }) {
  const [tab, setTab] = useState("Overview");
  const selectedInstance = instances.find((item) => item.id === backendId) ?? instances[1];
  if (selectedInstance.id !== "inst-b") return <BoundedBackendDetails instance={selectedInstance} />;
  const tabs = ["Overview", "Route memberships", "Traffic", "Evidence", "Action history", "Configuration"];
  return (
    <div className="page-stack backend-details-page">
      <PageHeader eyebrow="Physical instance inst-b" title="Backend B" brief={<>Backend B is physically reachable and continues serving public, auth, catalog, and recommendations. Only its checkout membership is quarantined; the machine is not globally down.</>} meta={<><StatusTag tone="warning">ROUTE-LOCAL ISSUE</StatusTag><code>demo-v1</code><span>capacity 100</span><span>54% physical utilization</span></>} actions={<><Link className="button secondary" href="/app/backends"><ArrowLeft size={15} />Inventory</Link><Link className="button primary" href="/app/traffic/matrix">Inspect memberships<ArrowRight size={15} /></Link></>} />
      <div className="tab-list" role="tablist" aria-label="Backend details sections">{tabs.map((item) => <button type="button" role="tab" aria-selected={tab === item} className={tab === item ? "active" : ""} onClick={() => setTab(item)} key={item}>{item}</button>)}</div>
      {tab === "Overview" ? <BackendOverview /> : tab === "Route memberships" ? <BackendMemberships /> : tab === "Traffic" ? <Panel title="Cross-route traffic" kicker="Physical load, counted once"><EvidenceChart title="Requests selected on Backend B" summary="Cross-route requests remain active after the checkout membership quarantine; the physical instance is not globally removed." data={trafficSeries} unit=" req/s" sampleCount={5842} yDomain={[0, 190]} actionAt="22:02" series={[{ key: "value", label: "All routes on B", color: "var(--accent-copper)" }, { key: "peer", label: "Public on B", color: "var(--neutral)", dashed: true }]} /></Panel> : tab === "Evidence" ? <Panel title="Evidence sources" kicker="Freshness and trust"><div className="source-health-list"><div><Check size={15} /><span><strong>HAProxy Runtime</strong><small>Complete membership state · 2 s old</small></span><StatusTag tone="success">fresh</StatusTag></div><div><Check size={15} /><span><strong>Proxy outcomes</strong><small>5,842 bounded samples · 4 s old</small></span><StatusTag tone="success">fresh</StatusTag></div><div><CircleDashed size={15} /><span><strong>Backend probe</strong><small>Checkout probe failed; general healthz passed</small></span><StatusTag tone="warning">mixed</StatusTag></div></div></Panel> : tab === "Action history" ? <Panel title="Immutable action history" kicker="Recent state changes"><Timeline items={[{ at: "22:02:15", label: "Checkout membership drain observed", detail: "act-7719 · route-local target only", state: "warning" }, { at: "19:44:01", label: "Baseline desired state reconciled", detail: "All memberships ready at weight 100", state: "success" }]} /></Panel> : <Panel title="Registered configuration" kicker="Read-only fixture"><KeyValueGrid items={[{ label: "Stable ID", value: "inst-b", mono: true }, { label: "HAProxy server alias", value: "srv_inst_b", mono: true }, { label: "Endpoint alias", value: "backend-b.internal:8080", mono: true }, { label: "Deployment version", value: "demo-v1", mono: true }, { label: "Physical capacity", value: 100, mono: true }, { label: "Probe profile", value: "registered-http-safe-v1" }]} /></Panel>}
    </div>
  );
}

function BoundedBackendDetails({ instance }: { instance: (typeof instances)[number] }) {
  const memberships = routes.map((route) => ({ route, cell: matrixCells.find((cell) => cell.routeId === route.id && cell.instanceId === instance.id)! }));
  const populated = memberships.filter(({ cell }) => cell.state !== "no-membership");
  const uncertain = memberships.filter(({ cell }) => cell.state === "unknown" || cell.evidence === "stale").length;
  return (
    <div className="page-stack backend-details-page">
      <PageHeader eyebrow={`Physical instance ${instance.id}`} title={instance.label} brief={<>This physical instance is counted once at {instance.capacity} capacity units. Its route memberships retain independent desired, observed, and evidence states.</>} meta={<><StatusTag tone={instance.probe === "passing" ? "success" : "neutral"}>{instance.probe === "passing" ? "READY" : "PARTIAL EVIDENCE"}</StatusTag><code>{instance.version}</code><span>capacity {instance.capacity}</span><span>{instance.utilization}% physical utilization</span></>} actions={<><Link className="button secondary" href="/app/backends"><ArrowLeft size={15} />Inventory</Link><Link className="button primary" href="/app/traffic/matrix">Inspect memberships<ArrowRight size={15} /></Link></>} />
      <section className="backend-overview-strip"><article><span>Physical reachability</span><strong>{instance.probe}</strong><small>fixture probe · {instance.lastTrafficSeconds} s old</small></article><article><span>Cross-route utilization</span><strong>{instance.utilization}%</strong><small>{instance.utilization} / {instance.capacity} capacity units</small></article><article><span>Populated memberships</span><strong>{populated.length} of {routes.length}</strong><small>capacity is not multiplied</small></article><article><span>Uncertain evidence</span><strong>{uncertain}</strong><small>UNKNOWN remains explicit</small></article></section>
      <div className="two-column-layout">
        <Panel title="Physical identity" kicker="Single capacity ledger"><KeyValueGrid items={[{ label: "Stable ID", value: instance.id, mono: true }, { label: "HAProxy server alias", value: instance.server, mono: true }, { label: "Endpoint alias", value: instance.addressAlias, mono: true }, { label: "Deployment version", value: instance.version, mono: true }, { label: "Configured capacity", value: instance.capacity, mono: true }, { label: "Last routed traffic", value: `${instance.lastTrafficSeconds} s`, mono: true }]} /><div className="notice neutral"><ShieldCheck size={15} /><span>Route-local symptoms never promote this instance to globally unhealthy without cross-route supporting evidence.</span></div></Panel>
        <Panel title="Route memberships" kicker="Desired and observed state"><div className="membership-list compact">{memberships.map(({ route, cell }) => { const unavailable = cell.state === "no-membership"; const unknown = cell.state === "unknown"; return <div className={unavailable || unknown ? "unknown" : "ready"} key={route.id}><span className="membership-state-icon">{unavailable || unknown ? <CircleDashed size={15} /> : <Check size={15} />}</span><span><code>{route.label}</code><small>{route.backend}/{instance.server}</small></span><div><strong>{unavailable ? "not in pool" : `${cell.observed.admin} · weight ${cell.observed.weight}`}</strong><small>{unavailable ? "topology fact" : `${cell.sampleCount} samples · ${cell.evidence}`}</small></div><StatusTag tone={unavailable ? "muted" : unknown ? "warning" : "success"}>{unavailable ? "no membership" : unknown ? "unknown" : "eligible"}</StatusTag></div>; })}</div></Panel>
      </div>
      <Panel title="Evidence boundary" kicker="No inferred recovery"><StateMessage state={uncertain ? "unknown" : "empty"} title={uncertain ? "One membership lacks fresh evidence." : "No active incident is linked."}>{uncertain ? "Last confirmed HAProxy state is retained, but missing route telemetry cannot be interpreted as healthy traffic." : "The fixture shows observed routing state and route samples without fabricating a controller action or recovery outcome."}</StateMessage></Panel>
    </div>
  );
}

function BackendOverview() {
  return <><div className="backend-overview-strip"><article><span>Physical reachability</span><strong>Passing</strong><small><Check size={13} />healthz responded</small></article><article><span>Cross-route utilization</span><strong>54%</strong><small>54 / 100 capacity units</small></article><article><span>Eligible memberships</span><strong>4 of 5</strong><small>checkout isolated</small></article><article><span>Observed freshness</span><strong>2 s</strong><small>fixture reference</small></article></div><div className="two-column-layout"><Panel title="Instance-wide evidence" kicker="Physical scope"><div className="evidence-boundary-card"><ShieldCheck size={18} /><div><strong>No instance-wide failure is supported.</strong><p>General reachability is passing and three high-volume sibling routes remain within their aligned ranges.</p></div></div><KeyValueGrid items={[{ label: "Connection failures", value: "0.1%", mono: true }, { label: "Aggregate p95", value: "142 ms", mono: true }, { label: "Queue depth", value: "4 requests", mono: true }, { label: "Physical utilization", value: "54%", mono: true }]} /></Panel><Panel title="Route-local evidence" kicker="Independent memberships"><BackendMemberships compact /></Panel></div></>;
}

function BackendMemberships({ compact = false }: { compact?: boolean }) {
  return <div className={`membership-list ${compact ? "compact" : ""}`}>{routes.map((route) => { const checkout = route.id === "checkout"; return <div className={checkout ? "quarantined" : "ready"} key={route.id}><span className="membership-state-icon">{checkout ? <CircleDashed size={15} /> : <Check size={15} />}</span><span><code>{route.label}</code><small>{route.backend}/srv_inst_b</small></span><div><strong>{checkout ? "drain · weight 0" : "ready · weight 100"}</strong><small>{checkout ? "route-local quarantine" : `${route.requestsPerSecond} req/s route total`}</small></div>{checkout ? <StatusTag tone="warning">quarantined</StatusTag> : <StatusTag tone="success">eligible</StatusTag>}</div>; })}</div>;
}

export function TrafficAnalysisPage() {
  const [range, setRange] = useState("15m");
  return (
    <div className="page-stack">
      <PageHeader eyebrow="Correlated evidence windows" title="Traffic analysis" brief={<>Request rate remains stable overall. Checkout error evidence diverged on Backend B at 22:02; queue, retry amplification, and preserved physical capacity stayed within configured guardrails after isolation.</>} meta={<><span>Time zone Asia/Kolkata</span><span>Missing interval: auth/C telemetry after 22:07</span><span>Action marker 22:02:14</span></>} actions={<label className="compact-select"><span>Range</span><select value={range} onChange={(event) => setRange(event.target.value)}><option value="15m">Last 15 minutes</option><option value="1h">Last hour</option><option value="6h">Last 6 hours</option></select><ChevronDown size={13} /></label>} />
      <div className="analysis-filter-band" aria-label="Applied fixture filters"><span>Compare</span><span className="filter-chip active">route: checkout</span><span className="filter-chip">instance: all</span><span className="filter-chip">version: all</span><span className="filter-chip">event: inc-1042</span></div>
      <div className="chart-grid"><Panel title="Request rate" kicker="Original client requests"><EvidenceChart title="Environment request rate" summary="Offered traffic varied from 151 to 171 requests per second during the bounded window." data={trafficSeries} unit=" req/s" sampleCount={18442} yDomain={[0, 200]} actionAt="22:02" series={[{ key: "value", label: "all routes", color: "var(--accent-copper)" }, { key: "peer", label: "public", color: "var(--neutral)", dashed: true }]} /></Panel><Panel title="Error families" kicker="Route-member outcomes"><EvidenceChart title="Checkout errors" summary="Checkout on Backend B rose to 18.2%, while the same route on peers held near 3%." data={errorSeries} unit="%" sampleCount={3428} yDomain={[0, 20]} actionAt="22:02" series={[{ key: "value", label: "checkout/B", color: "var(--danger)" }, { key: "peer", label: "checkout peers", color: "var(--accent-copper)", dashed: true }]} /></Panel></div>
      <div className="small-multiple-grid"><MetricSmallMultiple title="Latency distribution" value="p95 318 ms" detail="checkout peers · n=933" bars={[38, 52, 61, 72, 54, 43]} /><MetricSmallMultiple title="Queue depth" value="4 requests" detail="peak 18 at 22:02" bars={[18, 22, 45, 76, 42, 24]} /><MetricSmallMultiple title="Retry amplification" value="1.03×" detail="ambiguous POST retry suppressed" bars={[28, 30, 31, 34, 31, 30]} /><MetricSmallMultiple title="Eligible capacity" value="83% aggregate" detail="checkout route 67%" bars={[82, 83, 83, 67, 82, 83]} /></div>
      <div className="notice warning"><CircleDashed size={15} /><span>Auth/C samples after 22:07 are missing and are not interpolated. Charts retain the gap and lower evidence completeness.</span></div>
    </div>
  );
}

function MetricSmallMultiple({ title, value, detail, bars }: { title: string; value: string; detail: string; bars: number[] }) {
  return <article className="small-multiple"><div><span>{title}</span><strong>{value}</strong><small>{detail}</small></div><div className="micro-bars" aria-hidden="true">{bars.map((bar, index) => <i style={{ height: `${bar}%` }} key={index} />)}</div><details><summary>Data summary</summary><p>{title}: {value}. {detail}. Six bounded intervals are shown without smoothing.</p></details></article>;
}
